from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger

from src.analysis.code_change_analyzer import CodeChangeAnalyzer
from src.analysis.improvement_recommender import ImprovementRecommender
from src.analysis.root_cause import ExistingFaultAnalysis, FaultAnalysisInput
from src.analysis.root_cause import RootCauseAnalyzer as DeepRootCauseAnalyzer
from src.analysis.standards_matcher import StandardsMatcher
from src.analysis.violation_detector import ViolationDetector
from src.analyzer.image_evidence import ImageEvidenceExtractor
from src.analyzer.labeling import LabelGenerator
from src.analyzer.llm_provider import create_llm_provider
from src.analyzer.reasoning import RootCauseAnalyzer
from src.api.client import APIClient
from src.api.models import TaskInfo
from src.cache.manager import CacheManager
from src.clustering.analyzer import ClusterAnalyzer
from src.config.manager import ConfigManager
from src.embedding.generator import EmbeddingGenerator
from src.knowledge.manager import StandardsManager
from src.preprocessor.models import ProcessedTask, TextSegment
from src.preprocessor.processor import DataPreprocessor
from src.report.generator import ReportFormat, ReportGenerator
from src.rules.engine import RulesEngine


class _LLMClientAdapter:
    """Adapter that converts generate(system, user) to generate(prompt)."""

    def __init__(self, provider: Any) -> None:
        self._provider = provider

    async def generate(self, prompt: str) -> str:
        """Generate using the provider with combined system and user prompt."""
        return str(
            await self._provider.generate(system="You are a helpful assistant.", user=prompt)
        )


@dataclass
class PipelineConfig:
    """Configuration for analysis pipeline."""

    use_cache: bool = True
    use_llm: bool = False
    generate_labels: bool = True
    analyze_root_cause: bool = True
    analyze_root_cause_deep: bool = False  # Enhanced 5-layer root cause analysis
    check_rules: bool = True
    match_standards: bool = True  # 故障结论与研发规范语义匹配
    generate_report: bool = True
    report_format: ReportFormat = ReportFormat.MARKDOWN
    output_path: Path = field(default_factory=lambda: Path("./output"))
    max_concurrency: int = 10

    def __post_init__(self) -> None:
        if self.max_concurrency < 1:
            raise ValueError("max_concurrency must be positive")


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
    standard_matches: list[dict] | None = None  # 规范匹配结果（violated/related）
    improvements: list[dict] | None = None  # 改进建议与行动项
    cluster_id: int | None = None
    report: str = ""
    error: str = ""
    processing_time: float = 0.0  # 处理耗时（秒，不含 LLM 调用延迟）


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
        self._llm_providers: list[Any] = []
        self._cluster_analyzer: ClusterAnalyzer | None = None
        self._preprocessor = DataPreprocessor()
        self._image_evidence_extractor = ImageEvidenceExtractor()
        self._label_generator: LabelGenerator | None = None
        self._root_cause_analyzer: RootCauseAnalyzer | None = None
        self._deep_root_cause_analyzer: DeepRootCauseAnalyzer | None = None
        self._rules_engine = RulesEngine()
        self._code_change_analyzer: CodeChangeAnalyzer | None = None
        self._violation_detector: ViolationDetector | None = None
        self._standards_matcher: StandardsMatcher | None = None
        self._report_generator: ReportGenerator | None = None
        self._improvement_recommender: ImprovementRecommender | None = None

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
        """Close all owned resources."""
        api_client, self._api_client = self._api_client, None
        embedding_generator, self._embedding_generator = self._embedding_generator, None
        llm_providers, self._llm_providers = self._llm_providers, []
        cache_manager, self._cache_manager = self._cache_manager, None
        first_error: BaseException | None = None

        if api_client is not None:
            try:
                await api_client.close()
            except BaseException as error:
                first_error = error
        if embedding_generator is not None:
            try:
                await embedding_generator.close()
            except BaseException as error:
                if first_error is None:
                    first_error = error
        for provider in llm_providers:
            try:
                await provider.close()
            except BaseException as error:
                if first_error is None:
                    first_error = error
        if cache_manager is not None:
            try:
                cache_manager.close()
            except BaseException as error:
                if first_error is None:
                    first_error = error

        if first_error is not None:
            raise first_error

    def _create_llm_provider(self, config: Any) -> Any:
        """Create and track an LLM provider owned by this pipeline."""
        provider = create_llm_provider(config)
        if provider is not None:
            self._llm_providers.append(provider)
        return provider

    async def run_single(self, task_id: int) -> PipelineResult:
        """Run analysis pipeline for a single task.

        记录处理耗时（不含 LLM 调用延迟），满足非功能需求
        "单个故障单处理时间 < 30 秒"的可度量性要求。
        """
        import time

        result = PipelineResult(task_id=task_id)
        start_time = time.perf_counter()

        try:
            task_data = await self._fetch_task_data(task_id)
            if not task_data:
                result.error = f"Task {task_id} not found"
                return result

            preprocessed = await self._prepare_task_data(task_data, result)

            # 代码变更分析（新增）
            await self._analyze_code_changes(task_data, result)

            await self._analyze_with_llm(task_data, preprocessed, result)
            await self._match_standards(task_data, result)
            self._generate_improvements(result)
            self._check_and_generate_report(task_data, preprocessed, result)

        except Exception as error:
            logger.bind(
                task_id=task_id,
                exception_type=type(error).__name__,
            ).error("Analysis pipeline failed")
            result.error = "Analysis failed due to an internal error"

        finally:
            result.processing_time = time.perf_counter() - start_time

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
        # 图片证据增强：若有占位符图片，下载 + 视觉读图，追加为 image_evidence segment
        await self._enrich_with_image_evidence(task_data, preprocessed)
        result.preprocessed = {
            "task_id": preprocessed.task_id,
            "combined_text": preprocessed.combined_text,
            "segments": [
                {"type": s.type, "content": s.content, "metadata": s.metadata}
                for s in preprocessed.segments
            ],
        }
        return preprocessed

    async def _enrich_with_image_evidence(
        self, task_data: TaskInfo, preprocessed: ProcessedTask
    ) -> None:
        """下载并读取故障单中的占位符图片，把图片证据追加为 segment。

        图片证据使 LLM 能基于完整信息（描述 + 截图内容）做根因分析，
        避免因读不到图片而得出"信息不足/无法定位"的结论。

        无占位符图片或提取失败时静默跳过，不影响主分析流程。
        """
        try:
            evidence = await self._image_evidence_extractor.get_image_evidence(
                task_data.model_dump()
            )
            if not evidence:
                return
            preprocessed.segments.append(
                TextSegment(
                    task_id=preprocessed.task_id,
                    type="image_evidence",
                    content=evidence,
                    metadata={"source": "cos_images"},
                )
            )
            # 同步更新合并文本（供规范匹配等下游使用）
            preprocessed.combined_text = (
                f"{preprocessed.combined_text}\n\n[图片证据]\n{evidence}"
            )
            logger.info(
                "urId={} 已注入图片证据（{} 字符）",
                task_data.task_id,
                len(evidence),
            )
        except Exception as e:
            logger.warning(
                "urId={} 图片证据提取失败，降级为无图片证据: {}",
                task_data.task_id,
                str(e)[:100],
            )

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

    async def _analyze_code_changes(self, task_data: TaskInfo, result: PipelineResult) -> None:
        """分析代码变更（diff分析、模式检测、规范检查、LLM语义分析）。

        业务规则 1：只有标记为有代码变更（is_commit_code=Y）或存在 commits 的
        故障单才进行违规检测。is_commit_code 字段未填充时（默认 'N'），
        降级为检查 development.commits 是否存在，保证向后兼容。
        """
        has_commits = False
        if task_data.development is not None:
            has_commits = bool(task_data.development.commits)
        has_code_changes = task_data.is_commit_code == "Y" or has_commits
        if not has_code_changes:
            return

        development = task_data.development
        if development is None:
            return

        # 构建commit字典列表供CodeChangeAnalyzer使用
        commits_data = []
        all_diff_content = ""
        for commit in development.commits:
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
            if commit.diff:
                all_diff_content += commit.diff + "\n"

        # 使用CodeChangeAnalyzer进行diff分析和模式检测
        analyzer = self._get_code_change_analyzer()
        analysis_result = analyzer.analyze_code_changes(commits_data)

        # 生成分析文本（不含LLM，后面单独处理LLM）
        analysis_text = analyzer.generate_analysis_text(commits_data)

        # 异步LLM代码分析（解决同步方法中无法await的问题）
        llm_analysis = ""
        if self._pipeline_config.use_llm and all_diff_content:
            llm_analysis = await self._llm_analyze_code_diff(commits_data)
            if llm_analysis:
                analysis_text = f"{analysis_text}; LLM分析: {llm_analysis}"

        result.code_change_analysis = {
            "summary": analysis_result["summary"],
            "diff_stats": analysis_result["diff_stats"],
            "detected_patterns": analysis_result["detected_patterns"],
            "analysis_text": analysis_text,
            "llm_analysis": llm_analysis,
        }

        # 使用ViolationDetector进行Java规范违规检测
        if all_diff_content:
            violation_violations = self._detect_violations(all_diff_content, task_data)
            if violation_violations:
                # 合并到result.violations
                existing = result.violations or []
                result.violations = existing + violation_violations

    def _check_and_generate_report(
        self, task_data: TaskInfo, _preprocessed: Any, result: PipelineResult
    ) -> None:
        """Check rules and generate report if configured."""
        if self._pipeline_config.check_rules:
            rule_violations = self._check_rules(task_data.model_dump())
            result.violations = rule_violations + (result.violations or [])

        if self._pipeline_config.generate_report:
            result.report = self._generate_report(
                task_data.model_dump(mode="json"),
                result.preprocessed or {},
                result.labels,
                result.root_causes,
                violations=result.violations,
                code_change_analysis=result.code_change_analysis,
                standard_matches=result.standard_matches,
            )

    async def _match_standards(self, task_data: TaskInfo, result: PipelineResult) -> None:
        """将故障分析结论与研发规范库做语义匹配（embedding召回+LLM精排）。

        查询文本由分析结论构成：故障标题 + 标签 + 根因 + 代码变更分析，
        确保匹配由"结论"驱动而非仅由原始故障描述驱动。
        """
        if not self._pipeline_config.match_standards:
            return

        query_text = self._build_standards_query(task_data, result)
        if not query_text:
            return

        matcher = self._get_standards_matcher()
        match_result = await matcher.match(query_text)

        if match_result.matches:
            result.standard_matches = [m.to_dict() for m in match_result.matches]
            violated = [m.rule_id for m in match_result.violated]
            if violated:
                logger.info(f"规范匹配命中违规条款: {violated}")

    def _build_standards_query(self, task_data: TaskInfo, result: PipelineResult) -> str:
        """构造规范匹配查询文本（分析结论驱动）。"""
        parts: list[str] = [task_data.title or ""]

        for label in result.labels or []:
            parts.append(f"{label.get('name', '')} {label.get('description', '')}")

        for rc in result.root_causes or []:
            parts.append(f"{rc.get('cause_type', '')} {rc.get('description', '')}")

        if result.code_change_analysis:
            analysis_text = result.code_change_analysis.get("analysis_text", "")
            if analysis_text:
                parts.append(analysis_text[:1000])

        # 结论不足时补充故障描述，保证召回效果
        if sum(len(p) for p in parts) < 100 and task_data.description:
            parts.append(task_data.description[:1000])

        return "\n".join(p for p in parts if p).strip()

    def _generate_improvements(self, result: PipelineResult) -> None:
        """基于根因和违规项生成改进建议与行动项（GAP G4）。

        将高频根因映射到可落地的改进措施，作为流水线输出（PipelineResult.improvements）。
        """
        if result.improvements is not None:
            return

        # 收集根因文本
        root_causes: list[str] = []
        for rc in result.root_causes or []:
            cause = rc.get("cause_type") or rc.get("description")
            if cause:
                root_causes.append(str(cause))

        if not root_causes:
            result.improvements = []
            return

        # 收集违规根因（带 rule_id 的违规项）
        violation_causes: list[str] = []
        rule_ids_by_cause: dict[str, list[str]] = {}
        for v in result.violations or []:
            name = v.get("rule_name") or v.get("rule_id")
            if name:
                name_str = str(name)
                violation_causes.append(name_str)
                rule_id = v.get("rule_id")
                if rule_id:
                    rule_ids_by_cause.setdefault(name_str, []).append(str(rule_id))

        recommender = self._get_improvement_recommender()
        measures = recommender.recommend_measures(
            root_causes=root_causes,
            violation_causes=violation_causes or None,
            top_n=5,
            rule_ids_by_cause=rule_ids_by_cause or None,
        )

        result.improvements = [
            {
                "root_cause": m.root_cause,
                "measure": m.measure,
                "acceptance_criteria": m.acceptance_criteria,
                "expected_impact": m.expected_impact,
                "priority": m.priority,
                "category": m.category,
                "rule_ids": m.rule_ids,
            }
            for m in measures
        ]

    def _get_improvement_recommender(self) -> ImprovementRecommender:
        """Get or create ImprovementRecommender."""
        if self._improvement_recommender is None:
            self._improvement_recommender = ImprovementRecommender()
        return self._improvement_recommender

    def _get_standards_matcher(self) -> StandardsMatcher:
        """Get or create StandardsMatcher（复用embedding与LLM配置）。"""
        if self._standards_matcher is None:
            standards_manager = StandardsManager()

            embedding_generator = None
            llm_provider = None

            emb_config = self._config.get_config().embedding
            if emb_config.api_key:
                embedding_generator = self._get_embedding_generator()

            if self._pipeline_config.use_llm:
                llm_config = self._config.get_config().llm
                if llm_config.api_key:
                    llm_provider = self._create_llm_provider(llm_config)

            self._standards_matcher = StandardsMatcher(
                standards_manager=standards_manager,
                embedding_generator=embedding_generator,
                llm_provider=llm_provider,
            )
        return self._standards_matcher

    async def run_batch(
        self,
        task_ids: list[int],
    ) -> list[PipelineResult]:
        """Run analysis pipeline for multiple tasks concurrently."""
        import asyncio

        semaphore = asyncio.Semaphore(self._pipeline_config.max_concurrency)

        async def run_with_limit(task_id: int) -> PipelineResult:
            async with semaphore:
                return await self.run_single(task_id)

        results = await asyncio.gather(
            *[run_with_limit(task_id) for task_id in task_ids],
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

        semaphore = asyncio.Semaphore(self._pipeline_config.max_concurrency)

        async def fetch_with_limit(task_id: int) -> TaskInfo | None:
            async with semaphore:
                return await self._fetch_task(task_id)

        fetch_tasks = [fetch_with_limit(task_id) for task_id in task_ids]
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
                    commits_data.append(
                        {
                            "commit_id": commit.commit_id,
                            "author": commit.author,
                            "message": commit.message,
                            "diff": commit.diff,
                            "files_changed": commit.changes,
                            "branch": commit.branch,
                            "repository": commit.repository,
                            "timestamp": commit.time.isoformat() if commit.time else "",
                        }
                    )

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

        # G2: 为每个非噪声簇生成语义标签（需 LLM；无 LLM 时跳过）
        cluster_labels: dict[int, str] = {}
        if self._pipeline_config.use_llm and self._pipeline_config.generate_labels:
            cluster_labels = await self._generate_cluster_labels(
                tasks_data, processed_tasks, labels_list
            )

        # G18: 识别噪声点（cluster_id=-1），供独立下游分析
        noise_tasks = [
            {
                "task_id": tasks_data[i].task_id,
                "title": processed_tasks[i].metadata.get("title", "")
                if i < len(processed_tasks)
                else tasks_data[i].title or "",
                "reason": "噪声点：不归属于任何聚类簇，建议单独进行根因分析",
            }
            for i, label in enumerate(labels_list)
            if label == -1 and i < len(tasks_data)
        ]

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
            "noise_tasks": noise_tasks,
            "cluster_labels": cluster_labels,
            "total_requested": len(task_ids),
            "total_found": len(tasks_data),
            "clustering_mode": "code_change_enhanced" if has_code_data else "text_only",
        }

    async def _generate_cluster_labels(
        self,
        tasks_data: list[TaskInfo],
        processed_tasks: list[Any],
        labels_list: list[int],
    ) -> dict[int, str]:
        """为每个非噪声聚类簇生成语义标签（GAP G2）。

        复用 LabelGenerator.generate_for_cluster；无 LLM provider 时返回空字典。

        Returns:
            dict[cluster_id, cluster_label]
        """
        if self._label_generator is None:
            llm_config = self._config.get_config().llm
            provider = self._create_llm_provider(llm_config) if llm_config.api_key else None
            self._label_generator = LabelGenerator(llm_provider=provider)

        if not self._label_generator.is_available:
            return {}

        # 按簇分组任务
        cluster_members: dict[int, list[dict[str, Any]]] = {}
        for i, label in enumerate(labels_list):
            if label == -1:
                continue  # 噪声点不生成簇标签
            if i >= len(tasks_data):
                continue
            title = (
                processed_tasks[i].metadata.get("title", "")
                if i < len(processed_tasks)
                else tasks_data[i].title or ""
            )
            cluster_members.setdefault(int(label), []).append(
                {
                    "cluster_id": int(label),
                    "title": title,
                    "description": tasks_data[i].description or "",
                }
            )

        cluster_labels: dict[int, str] = {}
        for cluster_id, members in cluster_members.items():
            try:
                result = await self._label_generator.generate_for_cluster(members)
                if result.summary:
                    cluster_labels[cluster_id] = result.summary
                elif result.labels:
                    cluster_labels[cluster_id] = result.labels[0].name
            except Exception as e:
                logger.warning(f"簇 {cluster_id} 标签生成失败: {e}")

        return cluster_labels

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
        """Fetch task from API or cache.

        使用 get_full_task 以同时获取代码变更（development）和生产信息（production）。
        """
        import asyncio

        if self._pipeline_config.use_cache:
            cache = self._get_cache_manager()
            cached = await asyncio.to_thread(cache.load_task, task_id)
            if cached:
                return TaskInfo(**cached)

        api = self._get_api_client()
        task = await api.get_full_task(task_id)

        if self._pipeline_config.use_cache:
            cache = self._get_cache_manager()
            await asyncio.to_thread(cache.save_task, task_id, task.model_dump(mode="json"))

        return task

    def _get_code_change_analyzer(self) -> CodeChangeAnalyzer:
        """Get or create code change analyzer."""
        if self._code_change_analyzer is None:
            llm_provider = None
            if self._pipeline_config.use_llm:
                llm_config = self._config.get_config().llm
                if llm_config.api_key:
                    llm_provider = self._create_llm_provider(llm_config)
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
                rate_limit_qps=getattr(api_config, "rate_limit_qps", 0.0),
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
            provider = self._create_llm_provider(llm_config) if llm_config.api_key else None
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
            provider = self._create_llm_provider(llm_config) if llm_config.api_key else None
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
            provider = self._create_llm_provider(llm_config) if llm_config.api_key else None
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

    def _get_violation_detector(self) -> ViolationDetector:
        """Get or create ViolationDetector with real standards."""
        if self._violation_detector is None:
            standards_manager = StandardsManager()
            self._violation_detector = ViolationDetector(standards_manager)
        return self._violation_detector

    def _detect_violations(self, diff_content: str, task_data: TaskInfo) -> list[dict]:
        """使用ViolationDetector检测Java代码规范违规。

        Args:
            diff_content: 所有commit的diff内容合并
            task_data: 任务信息

        Returns:
            违规列表，每项包含rule_id/rule_name/severity/message/evidence
        """
        detector = self._get_violation_detector()
        fault_info = {
            "task_id": task_data.task_id if hasattr(task_data, "task_id") else 0,
            "title": task_data.title if hasattr(task_data, "title") else "",
            "description": task_data.description if hasattr(task_data, "description") else "",
            "code_snippet": diff_content,
        }

        detection = detector.detect(fault_info)
        if not detection.is_violation:
            return []

        # 将ViolationDetection转换为统一的violation字典格式
        violations = []
        for rule_label in detection.violated_rules:
            # rule_label 格式: "J000066:empty_catch" 或 "empty_catch"
            parts = rule_label.split(":", 1) if ":" in rule_label else ["", rule_label]
            rule_id = parts[0] if len(parts) > 1 else ""
            rule_name = parts[1] if len(parts) > 1 else parts[0]

            violations.append(
                {
                    "rule_id": rule_id,
                    "rule_name": rule_name,
                    "severity": "warning",
                    "message": detection.violation_type or "",
                    "evidence": [detection.evidence] if detection.evidence else [],
                }
            )

        return violations

    async def _llm_analyze_code_diff(self, commits: list[dict[str, Any]]) -> str:
        """异步调用LLM分析代码变更diff。

        解决了CodeChangeAnalyzer._llm_analyze_changes()在同步方法中
        无法await异步LLM调用的问题。

        Args:
            commits: commit信息列表（含diff）

        Returns:
            LLM分析结果摘要（最多500字符）
        """
        llm_config = self._config.get_config().llm
        if not llm_config.api_key:
            return ""

        provider = self._create_llm_provider(llm_config)
        if provider is None:
            return ""

        # 构建diff内容
        diffs_summary = []
        for c in commits:
            diff = c.get("diff", "")
            if diff:
                diff_preview = diff[:3000]
                diffs_summary.append(
                    f"Commit: {c.get('message', '')}\n"
                    f"Files: {', '.join(c.get('files_changed', []))}\n"
                    f"Diff preview:\n{diff_preview}"
                )

        if not diffs_summary:
            return ""

        combined = "\n---\n".join(diffs_summary[:5])

        system_prompt = (
            "你是一个资深代码审查专家。请**仅基于代码变更（diff）本身**进行分析。\n"
            "重要原则：\n"
            "- 代码变更是唯一可信的证据，不要根据故障描述做推测\n"
            "- 区分'删除代码'和'将代码移入条件分支'是完全不同的操作\n"
            "- 如果diff中删除的行和新增的行内容相似，通常是代码移动/重组，而非删除\n"
            "- 只描述代码实际做了什么，不要臆测业务背景\n"
            "请用简短的中文回答。"
        )
        user_prompt = (
            "请分析以下代码变更，仅基于diff内容：\n"
            "1. 代码实际做了什么改动（区分新增/删除/移动）\n"
            "2. 修改前后的行为差异\n"
            "3. 这个改动的核心目的\n"
            "4. 潜在风险（包括可能的副作用）\n\n"
            f"代码变更：\n{combined}\n\n"
            "请用3-5句话总结。"
        )

        try:
            result = await provider.generate(system=system_prompt, user=user_prompt)
            return str(result)[:500]
        except Exception as e:
            from loguru import logger

            logger.warning(f"LLM代码分析失败: {e}")
            return ""

    def _generate_report(
        self,
        task_data: dict[str, Any],
        preprocessed: dict[str, Any],
        labels: list[dict] | None,
        root_causes: list[dict] | None,
        violations: list[dict] | None = None,
        code_change_analysis: dict[str, Any] | None = None,
        standard_matches: list[dict] | None = None,
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
            format=self._pipeline_config.report_format,
            violations=violations,
            code_change_analysis=code_change_analysis,
            standard_matches=standard_matches,
        )
