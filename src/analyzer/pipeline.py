from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from src.analysis.code_change_analyzer import CodeChangeAnalyzer
from src.analysis.root_cause import ExistingFaultAnalysis, FaultAnalysisInput
from src.analysis.root_cause import RootCauseAnalyzer as DeepRootCauseAnalyzer
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


class _LLMClientAdapter:
    """Adapter that converts generate(system, user) to generate(prompt)."""

    def __init__(self, provider: Any) -> None:
        self._provider = provider

    async def generate(self, prompt: str) -> str:
        """Generate using the provider with combined system and user prompt."""
        return str(await self._provider.generate(system="You are a helpful assistant.", user=prompt))


@dataclass
class PipelineConfig:
    """Configuration for analysis pipeline."""

    use_cache: bool = True
    use_llm: bool = False
    generate_labels: bool = True
    analyze_root_cause: bool = True
    analyze_root_cause_deep: bool = False  # Enhanced 5-layer root cause analysis
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
    deep_root_causes: dict[str, Any] | None = None  # Enhanced root cause analysis result
    violations: list[dict] | None = None
    code_change_analysis: dict[str, Any] | None = None  # 代码变更分析结果
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
        self._deep_root_cause_analyzer: DeepRootCauseAnalyzer | None = None
        self._rules_engine = RulesEngine()
        self._code_change_analyzer: CodeChangeAnalyzer | None = None
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
            task_data = await self._fetch_task_data(task_id)
            if not task_data:
                result.error = f"Task {task_id} not found"
                return result

            preprocessed = await self._prepare_task_data(task_data, result)

            # 代码变更分析（新增）
            await self._analyze_code_changes(task_data, result)

            await self._analyze_with_llm(task_data, preprocessed, result)
            self._check_and_generate_report(task_data, preprocessed, result)

        except Exception as e:
            result.error = str(e)

        return result

    async def _fetch_task_data(self, task_id: int) -> TaskInfo | None:
        """Fetch task data from API or cache."""
        return await self._fetch_task(task_id)

    async def _prepare_task_data(
        self, task_data: TaskInfo, result: PipelineResult
    ) -> ProcessedTask:
        """Prepare task data by converting to dict and preprocessing."""
        result.task_data = task_data.model_dump()
        preprocessed = self._preprocessor.process(task_data)
        result.preprocessed = {
            "task_id": preprocessed.task_id,
            "combined_text": preprocessed.combined_text,
            "segments": [
                {"type": s.type, "content": s.content, "metadata": s.metadata}
                for s in preprocessed.segments
            ],
        }
        return preprocessed

    async def _analyze_with_llm(
        self, task_data: TaskInfo, preprocessed: ProcessedTask, result: PipelineResult
    ) -> None:
        """Perform LLM-based analysis if configured."""
        if self._pipeline_config.use_llm:
            task_dict = task_data.model_dump()
            if self._pipeline_config.generate_labels:
                result.labels = await self._generate_labels(task_dict, preprocessed)

            if self._pipeline_config.analyze_root_cause:
                result.root_causes = await self._analyze_root_cause(task_dict, preprocessed)

            if self._pipeline_config.analyze_root_cause_deep:
                result.deep_root_causes = await self._analyze_root_cause_deep(task_dict)

    async def _analyze_code_changes(
        self, task_data: TaskInfo, result: PipelineResult
    ) -> None:
        """分析代码变更（diff分析、模式检测、规范检查）"""
        if not task_data.development or not task_data.development.commits:
            return

        # 构建commit字典列表供CodeChangeAnalyzer使用
        commits_data = []
        for commit in task_data.development.commits:
            commit_dict = {
                "commit_id": commit.commit_id,
                "author": commit.author,
                "message": commit.message,
                "diff": commit.diff,
                "files_changed": commit.changes,
                "branch": commit.branch,
                "repository": commit.repository,
                "timestamp": commit.time.isoformat() if commit.time else "",
            }
            commits_data.append(commit_dict)

        # 使用CodeChangeAnalyzer进行分析
        analyzer = self._get_code_change_analyzer()
        analysis_result = analyzer.analyze_code_changes(commits_data)

        result.code_change_analysis = {
            "summary": analysis_result["summary"],
            "diff_stats": analysis_result["diff_stats"],
            "detected_patterns": analysis_result["detected_patterns"],
            "analysis_text": analyzer.generate_analysis_text(commits_data),
        }

    def _check_and_generate_report(
        self, task_data: TaskInfo, _preprocessed: Any, result: PipelineResult
    ) -> None:
        """Check rules and generate report if configured."""
        if self._pipeline_config.check_rules:
            result.violations = self._check_rules(task_data.model_dump())

        if self._pipeline_config.generate_report:
            result.report = self._generate_report(
                task_data.model_dump(),
                result.preprocessed or {},
                result.labels,
                result.root_causes,
                violations=result.violations,
                code_change_analysis=result.code_change_analysis,
            )

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
        """Run clustering analysis on tasks.

        当有代码变更数据时，将代码变更分析结果与故障文本结合进行聚类。
        否则降级到纯文本聚类。
        """
        import asyncio

        fetch_tasks = [self._fetch_task(task_id) for task_id in task_ids]
        fetched = await asyncio.gather(*fetch_tasks)
        tasks_data: list[TaskInfo] = [t for t in fetched if t is not None]

        if not tasks_data:
            return {"error": "No tasks to cluster", "missing_tasks": task_ids}

        processed_tasks = self._preprocessor.process_batch(tasks_data)

        # 生成聚类文本：结合故障描述和代码变更分析
        code_analyzer = self._get_code_change_analyzer()
        texts = []
        has_code_data = False

        for i, task in enumerate(tasks_data):
            base_text = processed_tasks[i].combined_text if i < len(processed_tasks) else ""

            # 如果有代码变更数据，生成代码变更分析文本并合并
            code_analysis_text = ""
            if task.development and task.development.commits:
                commits_data = []
                for commit in task.development.commits:
                    commits_data.append({
                        "commit_id": commit.commit_id,
                        "author": commit.author,
                        "message": commit.message,
                        "diff": commit.diff,
                        "files_changed": commit.changes,
                        "branch": commit.branch,
                        "repository": commit.repository,
                        "timestamp": commit.time.isoformat() if commit.time else "",
                    })

                # 只有当有diff数据时才生成代码分析文本
                if any(c.get("diff", "") for c in commits_data):
                    code_analysis_text = code_analyzer.generate_analysis_text(commits_data)
                    has_code_data = True

            if code_analysis_text:
                # 代码变更分析权重更高，放在前面
                combined = f"[代码变更分析] {code_analysis_text} [故障描述] {base_text}"
            else:
                combined = base_text

            texts.append(combined)

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
                    "title": processed_tasks[i].metadata.get("title", "")
                    if i < len(processed_tasks)
                    else "",
                    "text": texts[i][:200],
                    "has_code_analysis": self._has_code_analysis(tasks_data, i),
                }
                for i, t in enumerate(processed_tasks)
            ],
            "cluster_count": len(set(labels_list)) - (1 if -1 in labels_list else 0),
            "noise_count": sum(1 for label in labels_list if label == -1),
            "total_requested": len(task_ids),
            "total_found": len(tasks_data),
            "clustering_mode": "code_change_enhanced" if has_code_data else "text_only",
        }

    @staticmethod
    def _has_code_analysis(tasks_data: list[TaskInfo], index: int) -> bool:
        """Check if a task has code analysis data."""
        if index >= len(tasks_data):
            return False
        dev = tasks_data[index].development
        if dev is None or not dev.commits:
            return False
        return any(c.diff for c in dev.commits)

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

    def _get_code_change_analyzer(self) -> CodeChangeAnalyzer:
        """Get or create code change analyzer."""
        if self._code_change_analyzer is None:
            llm_provider = None
            if self._pipeline_config.use_llm:
                llm_config = self._config.get_config().llm
                if llm_config.api_key:
                    llm_provider = create_llm_provider(llm_config)
            self._code_change_analyzer = CodeChangeAnalyzer(llm_provider=llm_provider)
        return self._code_change_analyzer

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

    def _convert_api_to_existing_analysis(self, api_data: dict[str, Any]) -> ExistingFaultAnalysis:
        """Convert API response to ExistingFaultAnalysis model."""
        dev_data = api_data.get("apiDevTaskAnalysis", {})
        test_data = api_data.get("apiTestTaskAnalysis", {})

        return ExistingFaultAnalysis(
            dev_catalog=dev_data.get("catalog", ""),
            dev_catalog_detail=dev_data.get("catalogDetail", ""),
            dev_reason=dev_data.get("reason", ""),
            dev_conclusion=dev_data.get("conclusion", ""),
            dev_improve_stage=dev_data.get("improveStage", ""),
            test_catalog=test_data.get("catalog", ""),
            test_catalog_detail=test_data.get("catalogDetail", ""),
            test_reason=test_data.get("reason", ""),
            test_conclusion=test_data.get("conclusion", ""),
            test_improve_stage=test_data.get("improveStage", ""),
        )

    async def _analyze_root_cause_deep(
        self,
        task_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Perform enhanced 5-layer root cause analysis.

        Uses the new root cause analysis module with fault analysis input
        and existing analysis from the API.
        """
        if self._deep_root_cause_analyzer is None:
            llm_config = self._config.get_config().llm
            provider = create_llm_provider(llm_config) if llm_config.api_key else None
            if provider is not None:
                adapter = _LLMClientAdapter(provider)
                self._deep_root_cause_analyzer = DeepRootCauseAnalyzer(adapter)
            else:
                return {}

        if (
            self._deep_root_cause_analyzer is None
            or self._deep_root_cause_analyzer.llm_client is None
        ):
            return {}

        task_no = str(task_data.get("task_no", task_data.get("taskId", "")))
        if not task_no:
            return {}

        # Get existing fault analysis from API
        api = self._get_api_client()
        try:
            existing_api_data = await api.get_fault_analysis(task_no)
        except Exception:
            existing_api_data = {}

        existing_analysis = self._convert_api_to_existing_analysis(existing_api_data)

        # Build fault analysis input
        fault_input = FaultAnalysisInput(
            task_no=task_no,
            title=task_data.get("title", ""),
            description=task_data.get("description", ""),
            task_src=task_data.get("task_src", ""),
            created_date=task_data.get("created_date", task_data.get("createdDate", "")),
            finish_date=task_data.get("finish_date", task_data.get("finishDate", "")),
            product_module_id=task_data.get("product_module_id")
            or task_data.get("productModuleId"),
            product_version_id=task_data.get("product_version_id")
            or task_data.get("productVersionId"),
        )

        # Perform deep root cause analysis
        result = await self._deep_root_cause_analyzer.analyze(fault_input, existing_analysis)

        from dataclasses import asdict

        return asdict(result)

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
        violations: list[dict] | None = None,
        code_change_analysis: dict[str, Any] | None = None,
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

        # 如果有代码变更违规，添加针对性建议
        if violations:
            for v in violations[:3]:
                suggestions.append(
                    f"代码规范违规 [{v.get('rule_name', '')}]: {v.get('message', '')}"
                )

        return self._report_generator.generate_single(
            task_data=task_data,
            segments=preprocessed.get("segments", []),
            labels=labels or [],
            root_causes=root_causes or [],
            suggestions=suggestions,
            violations=violations,
            code_change_analysis=code_change_analysis,
        )
