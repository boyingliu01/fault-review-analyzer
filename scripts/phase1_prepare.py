"""
阶段一脚本：数据准备
提取数据 → 违规检测 → 代码变更分析 → 根因分析 → 根因验证 → 多模态向量化 → 存储到Chroma
"""

import asyncio
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from loguru import logger

from src.analysis.code_change_analyzer import CodeChangeAnalyzer
from src.analysis.enhanced_llm_analyzer import EnhancedLLMAnalyzer
from src.api.client import APIClient
from src.config.manager import ConfigManager
from src.core.models import EmbeddingResult
from src.embedding.generator import EmbeddingGenerator
from src.knowledge.manager import StandardsManager
from src.storage.chroma_manager import ChromaManager


class Phase1Prepare:
    """阶段一：数据准备"""

    def __init__(self, config: ConfigManager):
        self.config = config
        self.standards_manager = StandardsManager()
        self.enhanced_analyzer = EnhancedLLMAnalyzer(self.standards_manager)
        self.code_change_analyzer = CodeChangeAnalyzer()
        self.embedding_gen = EmbeddingGenerator(
            provider=config.embedding.provider,
            model=config.embedding.model,
            api_key=config.embedding.api_key,
            base_url=config.embedding.base_url,
        )
        self.chroma_manager = ChromaManager(
            persist_directory="./data/chroma",
            collection_name="fault_embeddings",
        )
        self.api_client: APIClient | None = None

    def init_api_client(
        self, base_url: str, token: str, timeout: int, api_path_prefix: str
    ) -> None:
        self.api_client = APIClient(
            base_url=base_url,
            token=token,
            timeout=timeout,
            api_path_prefix=api_path_prefix,
        )

    async def fetch_task_info(self, task_id: str) -> dict[str, Any] | None:
        """获取任务单详细信息"""
        if self.api_client is None:
            logger.warning("API客户端未初始化")
            return None

        try:
            async with self.api_client as client:
                task_info = await client.get_task(int(task_id))
                return task_info.model_dump() if task_info else None
        except Exception as e:
            logger.error(f"获取任务单 {task_id} 失败: {e}")
            return None

    def prepare_fault_info(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """准备故障信息用于分析"""
        development = task_data.get("development", {})
        commits = development.get("commits", [])

        code_snippet = ""
        if commits:
            for commit in commits[:3]:
                code_snippet += commit.get("diff", "") + "\n"

        return {
            "task_id": str(task_data.get("task_id", "")),
            "title": task_data.get("title", ""),
            "description": task_data.get("description", ""),
            "code_snippet": code_snippet[:2000],
            "development": development,
            "production": task_data.get("production", {}),
            "requirement": task_data.get("requirement", {}),
            "design": task_data.get("design", {}),
            "testing": task_data.get("testing", {}),
        }

    async def process_single_task(
        self, task_id: str, use_llm: bool = False
    ) -> EmbeddingResult | None:
        """处理单个任务单"""
        logger.info(f"处理任务单: {task_id}, use_llm={use_llm}")

        task_data = await self.fetch_task_info(task_id)
        if not task_data:
            logger.warning(f"任务单 {task_id} 数据为空，跳过")
            return None

        fault_info = self.prepare_fault_info(task_data)

        llm_result = self.enhanced_analyzer.analyze(fault_info)

        text_for_embedding = self._build_embedding_text(task_data, llm_result)

        try:
            embedding = await self.embedding_gen.embed_text(text_for_embedding)
        except Exception as e:
            logger.error(f"向量化失败: {e}")
            embedding = [0.0] * 2048

        result = EmbeddingResult(
            task_id=task_id,
            embedding=embedding,
            text=text_for_embedding[:500],
            media_type="text",
            metadata={
                "title": fault_info.get("title", "")[:100],
                "is_violation": llm_result.violation_detection.is_violation,
                "violation_type": llm_result.violation_detection.violation_type or "",
                "is_actionable": llm_result.root_cause_validation.is_actionable,
                "root_cause": llm_result.root_cause[:200],
            },
        )

        self.chroma_manager.add_embedding(result)

        logger.info(
            f"任务单 {task_id} 处理完成 - "
            f"违规: {llm_result.violation_detection.is_violation}, "
            f"可落地: {llm_result.root_cause_validation.is_actionable}"
        )

        return result

    def _build_embedding_text(self, task_data: dict[str, Any], llm_result: Any) -> str:
        """构建用于向量化的文本"""
        parts = [
            f"标题: {task_data.get('title', '')}",
            f"描述: {task_data.get('description', '')}",
            f"根因: {llm_result.root_cause}",
        ]

        if llm_result.violation_detection.is_violation:
            parts.append(f"违规类型: {llm_result.violation_detection.violation_type}")

        if llm_result.code_changes:
            for change in llm_result.code_changes[:2]:
                parts.append(f"代码变更: {change.message}")

        return "\n".join(parts)

    async def run(
        self,
        task_ids: list[str],
        use_llm: bool = False,
    ) -> list[EmbeddingResult]:
        """运行阶段一处理"""
        results = []

        for task_id in task_ids:
            try:
                result = await self.process_single_task(task_id, use_llm)
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(f"处理任务单 {task_id} 失败: {e}")
                continue

        logger.info(f"阶段一完成，共处理 {len(results)} 个任务单")
        return results


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="阶段一：数据准备")
    parser.add_argument(
        "--task-ids",
        type=str,
        required=True,
        help="任务单ID列表，逗号分隔",
    )
    parser.add_argument(
        "--excel",
        type=str,
        help="Excel文件路径，从中读取任务单ID",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="是否使用LLM进行深度分析",
    )
    args = parser.parse_args()

    config = ConfigManager().load()

    phase1 = Phase1Prepare(config)

    if config.api.base_url:
        phase1.init_api_client(
            base_url=config.api.base_url,
            token=config.api.token or "",
            timeout=config.api.timeout,
            api_path_prefix="/portal/ai-gateway/devspace/rpc/v3/work-item",
        )

    task_ids = []
    if args.excel:
        df = pd.read_excel(args.excel)
        task_ids = df.iloc[:, 0].astype(str).tolist()
    else:
        task_ids = [t.strip() for t in args.task_ids.split(",")]

    await phase1.run(task_ids, use_llm=args.use_llm)


if __name__ == "__main__":
    asyncio.run(main())
