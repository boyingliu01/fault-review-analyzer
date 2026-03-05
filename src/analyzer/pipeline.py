from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from src.analyzer.labeling import LabelGenerator
from src.analyzer.llm_provider import create_llm_provider
from src.analyzer.reasoning import RootCauseAnalyzer
from src.api.client import APIClient
from src.api.models import TaskInfo
from src.cache.manager import CacheManager
from src.clustering.analyzer import ClusterAnalyzer
from src.config.manager import ConfigManager
from src.embedding.generator import EmbeddingGenerator
from src.preprocessor.models import ProcessedTask
from src.preprocessor.processor import DataPreprocessor
from src.report.generator import ReportGenerator
from src.rules.engine import RulesEngine


@dataclass
class PipelineConfig:
    """Configuration for analysis pipeline."""

    use_cache: bool = True
    use_llm: bool = False
    generate_labels: bool = True
    analyze_root_cause: bool = True
    check_rules: bool = True
    generate_report: bool = True
    output_path: Path = field(default_factory=lambda: Path("./output"))


@dataclass
class PipelineResult:
    """Result of running the analysis pipeline."""

    task_id: int
    task_data: dict[str, Any] | None = None
    preprocessed: dict[str, Any] | None = None
    embedding: list[float] | None = None
    labels: list[dict] | None = None
    root_causes: list[dict] | None = None
    violations: list[dict] | None = None
    cluster_id: int | None = None
    report: str = ""
    error: str = ""


class AnalysisPipeline:
    """Orchestrates the complete fault analysis pipeline."""

    def __init__(
        self,
        config: ConfigManager,
        pipeline_config: PipelineConfig | None = None,
    ):
        self._config = config
        self._pipeline_config = pipeline_config or PipelineConfig()

        self._api_client: APIClient | None = None
        self._cache_manager: CacheManager | None = None
        self._embedding_generator: EmbeddingGenerator | None = None
        self._cluster_analyzer: ClusterAnalyzer | None = None
        self._preprocessor = DataPreprocessor()
        self._label_generator: LabelGenerator | None = None
        self._root_cause_analyzer: RootCauseAnalyzer | None = None
        self._rules_engine = RulesEngine()
        self._report_generator: ReportGenerator | None = None

    async def __aenter__(self) -> "AnalysisPipeline":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        """Close all async resources."""
        if self._api_client:
            await self._api_client.close()
            self._api_client = None

    async def run_single(self, task_id: int) -> PipelineResult:
        """Run analysis pipeline for a single task."""
        result = PipelineResult(task_id=task_id)

        try:
            task_data = await self._fetch_task(task_id)
            if not task_data:
                result.error = f"Task {task_id} not found"
                return result

            result.task_data = task_data.model_dump()
            task_dict = result.task_data
            preprocessed = self._preprocessor.process(task_data)
            result.preprocessed = {
                "task_id": preprocessed.task_id,
                "combined_text": preprocessed.combined_text,
                "segments": [
                    {"type": s.type, "content": s.content, "metadata": s.metadata}
                    for s in preprocessed.segments
                ],
            }

            if self._pipeline_config.use_llm:
                if self._pipeline_config.generate_labels:
                    result.labels = await self._generate_labels(task_dict, preprocessed)

                if self._pipeline_config.analyze_root_cause:
                    result.root_causes = await self._analyze_root_cause(
                        task_dict, preprocessed
                    )

            if self._pipeline_config.check_rules:
                result.violations = self._check_rules(task_dict)

            if self._pipeline_config.generate_report:
                result.report = self._generate_report(
                    task_dict, result.preprocessed, result.labels, result.root_causes
                )

        except Exception as e:
            result.error = str(e)

        return result

    async def run_batch(
        self,
        task_ids: list[int],
    ) -> list[PipelineResult]:
        """Run analysis pipeline for multiple tasks concurrently."""
        import asyncio
        results = await asyncio.gather(
            *[self.run_single(task_id) for task_id in task_ids],
            return_exceptions=False,
        )
        return list(results)

    async def run_clustering(
        self,
        task_ids: list[int],
    ) -> dict[str, Any]:
        """Run clustering analysis on tasks."""
        import asyncio

        fetch_tasks = [self._fetch_task(task_id) for task_id in task_ids]
        fetched = await asyncio.gather(*fetch_tasks)
        tasks_data: list[TaskInfo] = [t for t in fetched if t is not None]

        if not tasks_data:
            return {"error": "No tasks to cluster", "missing_tasks": task_ids}

        processed_tasks = self._preprocessor.process_batch(tasks_data)

        texts = [t.combined_text for t in processed_tasks]

        embedding_gen = self._get_embedding_generator()
        embeddings = await embedding_gen.embed_batch(texts)

        cluster_analyzer = self._get_cluster_analyzer()
        embeddings_array = np.array(embeddings)
        cluster_result = cluster_analyzer.fit_predict(embeddings_array)
        labels_list = cluster_result.labels

        return {
            "tasks": [
                {
                    "task_id": t.task_id,
                    "cluster_id": int(labels_list[i]),
                    "title": processed_tasks[i].metadata.get("title", "") if i < len(processed_tasks) else "",
                    "text": t.combined_text[:200],
                }
                for i, t in enumerate(processed_tasks)
            ],
            "cluster_count": len(set(labels_list)) - (1 if -1 in labels_list else 0),
            "noise_count": sum(1 for label in labels_list if label == -1),
            "total_requested": len(task_ids),
            "total_found": len(tasks_data),
        }

    async def _fetch_task(self, task_id: int) -> TaskInfo | None:
        """Fetch task from API or cache."""
        if self._pipeline_config.use_cache:
            cache = self._get_cache_manager()
            cached = cache.load_task(task_id)
            if cached:
                return TaskInfo(**cached)

        api = self._get_api_client()
        task = await api.get_task(task_id)

        if self._pipeline_config.use_cache:
            cache = self._get_cache_manager()
            cache.save_task(task_id, task.model_dump(mode="json"))

        return task

    def _get_api_client(self) -> APIClient:
        """Get or create API client."""
        if self._api_client is None:
            api_config = self._config.get_config().api
            self._api_client = APIClient(
                base_url=api_config.base_url,
                api_key=api_config.api_key,
                timeout=api_config.timeout,
                retry=api_config.retry,
            )
            self._api_client.ensure_client()
        return self._api_client

    def _get_cache_manager(self) -> CacheManager:
        """Get or create cache manager."""
        if self._cache_manager is None:
            cache_config = self._config.get_config().cache
            self._cache_manager = CacheManager(
                db_path=cache_config.db_path,
                ttl=cache_config.ttl,
            )
        return self._cache_manager

    def _get_embedding_generator(self) -> EmbeddingGenerator:
        """Get or create embedding generator."""
        if self._embedding_generator is None:
            emb_config = self._config.get_config().embedding
            self._embedding_generator = EmbeddingGenerator(
                provider=emb_config.provider,
                model=emb_config.model,
                api_key=emb_config.api_key,
                base_url=emb_config.base_url,
                batch_size=emb_config.batch_size,
            )
        return self._embedding_generator

    def _get_cluster_analyzer(self) -> ClusterAnalyzer:
        """Get or create cluster analyzer."""
        if self._cluster_analyzer is None:
            cluster_config = self._config.get_config().clustering
            self._cluster_analyzer = ClusterAnalyzer(
                algorithm=cluster_config.algorithm,
                min_cluster_size=cluster_config.min_cluster_size,
                min_samples=cluster_config.min_samples,
                metric=cluster_config.metric,
            )
        return self._cluster_analyzer

    async def _generate_labels(
        self,
        task_data: dict[str, Any],
        preprocessed: ProcessedTask,
    ) -> list[dict]:
        """Generate labels for task."""
        if self._label_generator is None:
            llm_config = self._config.get_config().llm
            provider = create_llm_provider(llm_config) if llm_config.api_key else None
            self._label_generator = LabelGenerator(llm_provider=provider)

        if not self._label_generator.is_available:
            return []

        result = await self._label_generator.generate(
            task_data,
            [{"type": s.type, "content": s.content} for s in preprocessed.segments],
        )

        return [
            {
                "name": label.name,
                "confidence": label.confidence,
                "category": label.category,
                "description": label.description,
            }
            for label in result.labels
        ]

    async def _analyze_root_cause(
        self,
        task_data: dict[str, Any],
        preprocessed: ProcessedTask,
    ) -> list[dict]:
        """Analyze root cause for task."""
        if self._root_cause_analyzer is None:
            llm_config = self._config.get_config().llm
            provider = create_llm_provider(llm_config) if llm_config.api_key else None
            self._root_cause_analyzer = RootCauseAnalyzer(llm_provider=provider)

        if not self._root_cause_analyzer.is_available:
            return []

        result = await self._root_cause_analyzer.analyze(
            task_data,
            [{"type": s.type, "content": s.content} for s in preprocessed.segments],
        )

        return [
            {
                "cause_type": rc.cause_type,
                "description": rc.description,
                "evidence": rc.evidence,
                "confidence": rc.confidence,
            }
            for rc in result.root_causes
        ]

    def _check_rules(self, task_data: dict[str, Any]) -> list[dict]:
        """Check rules for task."""
        violations = self._rules_engine.check(task_data)

        return [
            {
                "rule_id": v.rule_id,
                "rule_name": v.rule_name,
                "severity": v.severity,
                "message": v.message,
                "evidence": v.evidence,
            }
            for v in violations
        ]

    def _generate_report(
        self,
        task_data: dict[str, Any],
        preprocessed: dict[str, Any],
        labels: list[dict] | None,
        root_causes: list[dict] | None,
    ) -> str:
        """Generate report for task."""
        if self._report_generator is None:
            self._report_generator = ReportGenerator()

        suggestions = []
        if root_causes:
            suggestions = [
                f"针对{rc.get('cause_type', '未知')}类型问题，建议加强相关环节的质量把控"
                for rc in root_causes[:3]
            ]

        return self._report_generator.generate_single(
            task_data=task_data,
            segments=preprocessed.get("segments", []),
            labels=labels or [],
            root_causes=root_causes or [],
            suggestions=suggestions,
        )
