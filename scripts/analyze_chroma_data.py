#!/usr/bin/env python
"""分析ChromaDB中存储的故障数据结构和内容

Usage:
    python scripts/analyze_chroma_data.py [--count N] [--collection NAME]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger

from src.storage.chroma_manager import ChromaManager


def analyze_metadata_field(key: str, value: any) -> str:
    """分析metadata字段的类型和内容"""
    if value is None:
        return f"{key}: null"
    if isinstance(value, list):
        return f"{key}: list[{len(value)} items]"
    if isinstance(value, dict):
        return f"{key}: dict[{len(value)} keys]"
    if isinstance(value, str):
        preview = value[:50] + "..." if len(value) > 50 else value
        return f"{key}: str = '{preview}'"
    return f"{key}: {type(value).__name__} = {value}"


def analyze_embedding_data(
    manager: ChromaManager,
    collection_name: str = "fault_embeddings",
    sample_count: int = 5,
) -> dict:
    """分析ChromaDB中的数据结构和内容"""
    collection = manager.get_or_create_collection(collection_name)

    # 获取集合统计信息
    stats = {
        "collection_name": collection.name,
        "total_count": collection.count(),
        "metadata": collection.metadata,
    }

    logger.info(f"集合统计: {stats}")

    if stats["total_count"] == 0:
        logger.warning("集合为空，没有数据可分析")
        return stats

    # 获取样本数据
    limit = min(sample_count, stats["total_count"])
    logger.info(f"获取 {limit} 个样本进行详细分析...")

    # 使用get获取所有数据
    result = collection.get(
        limit=limit,
        include=["metadatas", "documents", "embeddings"],
    )

    samples = []
    for i in range(len(result["ids"])):
        sample = {
            "id": result["ids"][i],
            "document": result["documents"][i] if result["documents"] else "",
            "metadata": result["metadatas"][i] if result["metadatas"] else {},
            "embedding": result["embeddings"][i] if result["embeddings"] else [],
        }
        samples.append(sample)

    # 详细分析每个样本
    detailed_analysis = []
    for idx, sample in enumerate(samples):
        analysis = analyze_single_sample(idx, sample)
        detailed_analysis.append(analysis)

    stats["samples"] = detailed_analysis
    return stats


def analyze_single_sample(index: int, sample: dict) -> dict:
    """分析单个样本的详细结构"""
    sample_id = sample["id"]
    document = sample["document"]
    metadata = sample["metadata"]
    embedding = sample["embedding"]

    logger.info(f"\n{'='*80}")
    logger.info(f"样本 #{index + 1}: {sample_id}")
    logger.info(f"{'='*80}")

    # 1. 分析embedding维度
    embedding_dim = len(embedding) if embedding else 0
    logger.info(f"\n【Embedding维度】")
    logger.info(f"  维度: {embedding_dim}")
    if embedding_dim > 0:
        logger.info(f"  前5个值: {embedding[:5]}")

    # 2. 分析document内容
    doc_length = len(document) if document else 0
    logger.info(f"\n【Document内容】")
    logger.info(f"  长度: {doc_length} 字符")
    if doc_length > 0:
        preview = document[:500] + "..." if doc_length > 500 else document
        logger.info(f"  内容预览:\n{preview}")

    # 3. 分析metadata字段
    logger.info(f"\n【Metadata字段】")
    logger.info(f"  字段数量: {len(metadata)}")

    metadata_details = {}
    for key, value in metadata.items():
        field_info = analyze_metadata_field(key, value)
        logger.info(f"  - {field_info}")

        # 记录详细信息
        metadata_details[key] = {
            "type": type(value).__name__,
            "value_preview": str(value)[:200] if value is not None else None,
        }

    return {
        "id": sample_id,
        "embedding_dim": embedding_dim,
        "document_length": doc_length,
        "metadata_fields": list(metadata.keys()),
        "metadata_details": metadata_details,
    }


def main():
    parser = argparse.ArgumentParser(description="分析ChromaDB中的故障数据结构")
    parser.add_argument(
        "--count", "-n", type=int, default=5, help="要分析的样本数量 (默认: 5)"
    )
    parser.add_argument(
        "--collection", "-c", type=str, default="fault_embeddings", help="集合名称 (默认: fault_embeddings)"
    )
    parser.add_argument(
        "--output", "-o", type=str, help="输出JSON文件路径"
    )
    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("ChromaDB 数据结构分析工具")
    logger.info("=" * 80)

    # 初始化ChromaManager
    from src.config.manager import ConfigManager

    config = ConfigManager()
    persist_dir = config.get("storage", {}).get("chroma_path", "./data/chroma")

    logger.info(f"ChromaDB 持久化路径: {persist_dir}")

    manager = ChromaManager(persist_directory=persist_dir)

    # 列出所有集合
    collections = manager.list_collections()
    logger.info(f"\n现有集合: {collections}")

    # 分析数据
    stats = analyze_embedding_data(
        manager,
        collection_name=args.collection,
        sample_count=args.count,
    )

    # 输出到文件
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        logger.info(f"\n结果已保存到: {args.output}")

    # 生成结构总结
    logger.info("\n" + "=" * 80)
    logger.info("数据结构总结")
    logger.info("=" * 80)

    total_count = stats.get("total_count", 0)
    samples = stats.get("samples", [])

    if samples:
        first_sample = samples[0]
        logger.info(f"\n样本数据结构示例 (ID: {first_sample['id']}):")
        logger.info(f"  - Embedding 维度: {first_sample['embedding_dim']}")
        logger.info(f"  - Document 长度: {first_sample['document_length']} 字符")
        logger.info(f"  - Metadata 字段: {first_sample['metadata_fields']}")

        # 检查metadata是否包含分析字段
        all_fields = set()
        for s in samples:
            all_fields.update(s.get("metadata_fields", []))

        analysis_fields = [
            "root_cause",
            "improvement_measures",
            "violation_type",
            "violation_category",
            "cluster_label",
        ]
        found_analysis = [f for f in analysis_fields if f in all_fields]
        missing_analysis = [f for f in analysis_fields if f not in all_fields]

        logger.info(f"\n分析相关字段:")
        logger.info(f"  已存在: {found_analysis if found_analysis else '无'}")
        logger.info(f"  缺失: {missing_analysis if missing_analysis else '无'}")

    logger.info("\n" + "=" * 80)


if __name__ == "__main__":
    main()
