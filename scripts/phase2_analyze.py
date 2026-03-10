"""
阶段二脚本：聚类分析
从Chroma加载 → 聚类分析 → 根因统计 → 可视化
"""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from src.clustering.analyzer import ClusterAnalyzer
from src.config.manager import ConfigManager
from src.core.models import ClusteringResult
from src.storage.chroma_manager import ChromaManager


class Phase2Analyze:
    """阶段二：聚类分析"""

    def __init__(self, config: ConfigManager):
        self.config = config
        self.chroma_manager = ChromaManager(
            persist_directory="./data/chroma",
            collection_name="fault_embeddings",
        )
        self.cluster_analyzer = ClusterAnalyzer(
            algorithm=config.clustering.algorithm,
            min_cluster_size=config.clustering.min_cluster_size,
            min_samples=config.clustering.min_samples,
            metric=config.clustering.metric,
        )

    def load_embeddings(self) -> tuple[list[list[float]], list[dict[str, Any]]]:
        """从Chroma加载所有向量"""
        collection = self.chroma_manager.get_or_create_collection()

        result = collection.get(include=["embeddings", "metadatas", "documents"])

        embeddings = result.get("embeddings", [])
        metadatas = result.get("metadatas", [])
        documents = result.get("documents", [])

        if not embeddings:
            logger.warning("Chroma中没有向量数据")
            return [], []

        enriched_metadata = []
        for i, meta in enumerate(metadatas):
            enriched = dict(meta) if meta else {}
            enriched["document"] = documents[i] if i < len(documents) else ""
            enriched_metadata.append(enriched)

        logger.info(f"从Chroma加载 {len(embeddings)} 个向量")
        return embeddings, enriched_metadata

    def run_clustering(
        self,
        embeddings: list[list[float]],
        algorithm: str | None = None,
        **kwargs,
    ) -> ClusteringResult:
        """执行聚类分析"""
        if algorithm:
            self.cluster_analyzer = ClusterAnalyzer(
                algorithm=algorithm,
                min_cluster_size=kwargs.get("min_cluster_size", 5),
                min_samples=kwargs.get("min_samples", 3),
                metric=kwargs.get("metric", "cosine"),
            )

        result = self.cluster_analyzer.fit(embeddings)
        logger.info(
            f"聚类完成: {result.n_clusters} 个聚类, "
            f"{result.n_noise} 个噪声点, "
            f"轮廓系数: {result.silhouette_score:.3f}"
        )
        return result

    def analyze_clusters(
        self,
        labels: list[int],
        metadatas: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """分析聚类结果"""
        cluster_stats: dict[int, dict[str, Any]] = {}

        for i, label in enumerate(labels):
            if label == -1:
                continue

            if label not in cluster_stats:
                cluster_stats[label] = {
                    "count": 0,
                    "task_ids": [],
                    "violations": 0,
                    "actionable": 0,
                    "root_causes": [],
                }

            cluster_stats[label]["count"] += 1
            meta = metadatas[i] if i < len(metadatas) else {}
            cluster_stats[label]["task_ids"].append(meta.get("task_id", f"task_{i}"))

            if meta.get("is_violation"):
                cluster_stats[label]["violations"] += 1
            if meta.get("is_actionable"):
                cluster_stats[label]["actionable"] += 1
            if meta.get("root_cause"):
                cluster_stats[label]["root_causes"].append(meta.get("root_cause"))

        violation_count = sum(1 for m in metadatas if m.get("is_violation"))
        actionable_count = sum(1 for m in metadatas if m.get("is_actionable"))

        return {
            "total_tasks": len(labels),
            "total_clusters": len(cluster_stats),
            "noise_count": labels.count(-1),
            "violation_count": violation_count,
            "actionable_count": actionable_count,
            "clusters": cluster_stats,
        }

    def generate_report(
        self,
        clustering_result: ClusteringResult,
        analysis_result: dict[str, Any],
        output_path: str = "./output/cluster_report.md",
    ) -> str:
        """生成聚类分析报告"""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        lines = [
            "# 故障聚类分析报告",
            "",
            "## 一、聚类概况",
            "",
            f"- **总故障数**: {analysis_result['total_tasks']}",
            f"- **聚类数量**: {analysis_result['total_clusters']}",
            f"- **噪声点数**: {analysis_result['noise_count']}",
            f"- **轮廓系数**: {clustering_result.silhouette_score:.3f}",
            f"- **使用算法**: {clustering_result.algorithm}",
            "",
            "## 二、违规与可落地性统计",
            "",
            f"- **检测到违规**: {analysis_result['violation_count']} 个",
            f"- **根因可落地**: {analysis_result['actionable_count']} 个",
            "",
            "## 三、聚类详情",
            "",
        ]

        for cluster_id, stats in sorted(analysis_result["clusters"].items()):
            lines.append(f"### 聚类 {cluster_id}")
            lines.append("")
            lines.append(f"- **故障数量**: {stats['count']}")
            lines.append(f"- **违规数**: {stats['violations']}")
            lines.append(f"- **可落地数**: {stats['actionable']}")
            lines.append(f"- **任务单ID**: {', '.join(stats['task_ids'][:10])}")
            if len(stats["task_ids"]) > 10:
                lines.append(f"  (共 {len(stats['task_ids'])} 个)")
            lines.append("")

        report_content = "\n".join(lines)

        Path(output_path).write_text(report_content, encoding="utf-8")

        logger.info(f"报告已生成: {output_path}")
        return report_content

    def run(
        self,
        algorithm: str | None = None,
        output_path: str = "./output/cluster_report.md",
        **kwargs,
    ) -> dict[str, Any]:
        """运行阶段二分析"""
        embeddings, metadatas = self.load_embeddings()

        if not embeddings:
            logger.error("没有向量数据，请先运行阶段一")
            return {}

        clustering_result = self.run_clustering(embeddings, algorithm, **kwargs)

        analysis_result = self.analyze_clusters(clustering_result.labels, metadatas)

        self.generate_report(clustering_result, analysis_result, output_path)

        return {
            "clustering": clustering_result.model_dump(),
            "analysis": analysis_result,
        }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="阶段二：聚类分析")
    parser.add_argument(
        "--algorithm",
        type=str,
        default="hdbscan",
        choices=["hdbscan", "kmeans", "hierarchical"],
        help="聚类算法",
    )
    parser.add_argument(
        "--min-cluster-size",
        type=int,
        default=5,
        help="最小聚类大小",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=3,
        help="最小样本数",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="./output/cluster_report.md",
        help="报告输出路径",
    )
    args = parser.parse_args()

    config = ConfigManager().load()

    phase2 = Phase2Analyze(config)

    result = phase2.run(
        algorithm=args.algorithm,
        min_cluster_size=args.min_cluster_size,
        min_samples=args.min_samples,
        output_path=args.output,
    )

    if result:
        logger.info("阶段二分析完成")


if __name__ == "__main__":
    main()
