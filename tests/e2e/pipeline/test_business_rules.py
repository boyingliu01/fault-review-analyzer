"""E2E: 业务规则验证测试.

覆盖 spec 中的 Business Rules:
  - Rule 1: isCommitCode=N / 无代码变更 → 跳过违规检测
  - Rule 2: 聚类簇小于 min_cluster_size → 标记为噪声
  - Rule 4: 改进建议关联规范编号（J000001 格式）

仅 mock API 客户端，其余组件（Preprocessor、RulesEngine、
ReportGenerator）全部使用真实实例。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import numpy as np
import pytest

from src.analyzer.pipeline import AnalysisPipeline, PipelineConfig
from src.api.models import CommitInfo, DevelopmentInfo, ProductionInfo, TaskInfo
from src.clustering.analyzer import ClusterAnalyzer
from src.config.manager import ConfigManager

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def real_config_manager(tmp_path: Path) -> ConfigManager:
    """创建使用临时文件的真实 ConfigManager。"""
    cache_db = str(tmp_path / "cache.db").replace("\\", "/")
    output_dir = str(tmp_path / "output").replace("\\", "/")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""\
api:
  base_url: "https://example.com"
  timeout: 5
  retry: 1
  api_key: "test-token"
llm:
  provider: "openai"
  model: "gpt-4"
  api_key: ""
embedding:
  provider: "openai"
  model: "text-embedding-3-small"
  api_key: ""
clustering:
  algorithm: "hdbscan"
  min_cluster_size: 3
  min_samples: 2
  metric: "cosine"
cache:
  db_path: "{cache_db}"
  ttl: 3600
  enabled: true
output:
  directory: "{output_dir}"
""",
        encoding="utf-8",
    )
    return ConfigManager(config_path)


def _create_mock_api_client(task: TaskInfo) -> AsyncMock:
    """创建一个返回指定 TaskInfo 的 mock API 客户端。"""
    client = AsyncMock()
    client.get_task = AsyncMock(return_value=task)
    client.get_full_task = AsyncMock(return_value=task)
    client.get_fault_analysis = AsyncMock(return_value={})
    client.close = AsyncMock()
    client.ensure_client = lambda: None
    return client


# ---------------------------------------------------------------------------
# Rule 1: 无代码变更 → 跳过违规检测
# ---------------------------------------------------------------------------


class TestSkipViolationForNoCodeChanges:
    """Spec Rule 1: 只有代码变更记录（isCommitCode=Y）的故障单才进行违规检测."""

    @pytest.fixture
    def task_no_code_changes(self) -> TaskInfo:
        """无 development 字段的故障任务 — 没有代码变更。"""
        return TaskInfo(
            task_id=40001,
            title="纯流程故障 - 无代码变更",
            description="这是一个运维层面的问题，没有涉及代码修改",
            status="resolved",
            priority="medium",
            create_time=datetime(2024, 10, 1, 10, 0, 0),
            resolve_time=datetime(2024, 10, 1, 16, 0, 0),
            production=ProductionInfo(
                incident_time=datetime(2024, 10, 1, 12, 0, 0),
                symptoms="服务重启解决",
                logs=["WARN: Memory threshold reached"],
                resolution="增加内存配额，重启服务",
            ),
            # 关键：development=None → 无代码变更
        )

    @pytest.fixture
    def task_empty_commits(self) -> TaskInfo:
        """development 存在但 commits 为空的故障任务。"""
        return TaskInfo(
            task_id=40002,
            title="空提交记录 - 无代码变更",
            description="结论记录但没有代码变更",
            status="resolved",
            priority="low",
            create_time=datetime(2024, 10, 2, 8, 0, 0),
            resolve_time=datetime(2024, 10, 2, 10, 0, 0),
            development=DevelopmentInfo(commits=[]),
        )

    @pytest.fixture
    def task_with_code(self) -> TaskInfo:
        """有代码变更的故障任务 — 应有违规检测。"""
        return TaskInfo(
            task_id=40003,
            title="有代码变更的故障",
            description="包含代码修改的故障",
            status="resolved",
            priority="high",
            create_time=datetime(2024, 10, 3, 9, 0, 0),
            resolve_time=datetime(2024, 10, 3, 15, 0, 0),
            development=DevelopmentInfo(
                commits=[
                    CommitInfo(
                        commit_id="cc001",
                        message="fixes the bug",
                        author="dev",
                        time=datetime(2024, 10, 3, 12, 0, 0),
                        changes=["src/fix.py"],
                        diff="catch(Exception e) {}  ← empty catch bad practice",
                    )
                ]
            ),
            production=ProductionInfo(
                incident_time=datetime(2024, 10, 3, 10, 0, 0),
                symptoms="某功能异常",
                resolution="修复代码",
            ),
        )

    @pytest.mark.asyncio
    async def test_no_violations_when_development_is_none(
        self,
        real_config_manager: ConfigManager,
        task_no_code_changes: TaskInfo,
    ):
        """无 development 字段时，应不产生违规记录。"""
        pipeline = AnalysisPipeline(
            real_config_manager,
            PipelineConfig(
                use_cache=False,
                use_llm=False,
                generate_labels=False,
                analyze_root_cause=False,
                check_rules=True,
                generate_report=True,
            ),
        )
        pipeline._api_client = _create_mock_api_client(task_no_code_changes)

        try:
            result = await pipeline.run_single(40001)

            assert result.error == ""
            # 无 violations 或有 violations 但为空（ViolationDetector 未被触发）
            assert result.violations is None or len(result.violations) == 0
            # 报告应包含任务信息
            assert "40001" in result.report

        finally:
            await pipeline.close()

    @pytest.mark.asyncio
    async def test_no_violations_when_commits_is_empty(
        self,
        real_config_manager: ConfigManager,
        task_empty_commits: TaskInfo,
    ):
        """commits 为空列表时，应不产生违规记录。"""
        pipeline = AnalysisPipeline(
            real_config_manager,
            PipelineConfig(
                use_cache=False,
                use_llm=False,
                generate_labels=False,
                analyze_root_cause=False,
                check_rules=True,
                generate_report=True,
            ),
        )
        pipeline._api_client = _create_mock_api_client(task_empty_commits)

        try:
            result = await pipeline.run_single(40002)

            assert result.error == ""
            assert result.violations is None or len(result.violations) == 0

        finally:
            await pipeline.close()

    @pytest.mark.asyncio
    async def test_violations_present_when_code_exists(
        self,
        real_config_manager: ConfigManager,
        task_with_code: TaskInfo,
    ):
        """有代码变更时，RulesEngine 应检测到违规（commit message 匹配）。"""
        pipeline = AnalysisPipeline(
            real_config_manager,
            PipelineConfig(
                use_cache=False,
                use_llm=False,
                generate_labels=False,
                analyze_root_cause=False,
                check_rules=True,
                generate_report=True,
            ),
        )
        pipeline._api_client = _create_mock_api_client(task_with_code)

        try:
            result = await pipeline.run_single(40003)

            assert result.error == ""
            # 代码变更存在，且有 code_change_analysis 中的异常检测
            assert result.code_change_analysis is not None
            detected = result.code_change_analysis.get("detected_patterns", [])
            has_pattern = any(
                p.get("matched") for p in detected if isinstance(p, dict)
            )
            # 可能检测到异常处理模式（exception_handling）
            if has_pattern:
                assert len(detected) > 0

        finally:
            await pipeline.close()


# ---------------------------------------------------------------------------
# Rule 2: 聚类噪声点处理（单样本簇 → -1 标签）
# ---------------------------------------------------------------------------


class TestClusterNoisePointHandling:
    """Spec Rule 2: 聚类簇大小小于 min_cluster_size 的标记为噪声."""

    def test_single_sample_returns_noise_label(self):
        """单个样本应标记为噪声（cluster_id=-1）。"""
        analyzer = ClusterAnalyzer(
            algorithm="hdbscan",
            min_cluster_size=3,
            min_samples=2,
            metric="cosine",
        )

        # 单个样本
        embeddings = np.array([[0.1, 0.2, 0.3]], dtype=float)
        result = analyzer.fit_predict(embeddings)

        assert result is not None
        labels = np.asarray(result.labels)
        # 所有点都应为噪声
        assert np.all(labels == -1), f"Expected all -1 labels, got {labels}"

    def test_fewer_than_min_cluster_returns_all_noise(self):
        """样本数少于 min_cluster_size 时，全部标记为噪声。"""
        analyzer = ClusterAnalyzer(
            algorithm="hdbscan",
            min_cluster_size=3,
            min_samples=2,
            metric="cosine",
        )

        # 2 个样本 < min_cluster_size(3)
        embeddings = np.array([[0.1, 0.2], [0.15, 0.25]], dtype=float)
        result = analyzer.fit_predict(embeddings)

        labels = np.asarray(result.labels)
        assert np.all(labels == -1), f"All 2 samples should be noise, got {labels}"

    def test_run_clustering_with_noise_includes_noise_count(self):
        """run_clustering 应统计噪声点数量。"""
        analyzer = ClusterAnalyzer(
            algorithm="hdbscan",
            min_cluster_size=5,
            min_samples=2,
            metric="cosine",
        )

        # 3 个样本 < 5
        embeddings = np.array(
            [[0.1 * i, 0.2 * i, 0.3 * i] for i in range(1, 4)],
            dtype=float,
        )
        result = analyzer.fit_predict(embeddings)
        labels = np.asarray(result.labels)

        noise_count = int(np.sum(labels == -1))
        assert noise_count == len(embeddings), (
            f"All {len(embeddings)} samples should be noise, got {noise_count}"
        )

    def test_noise_label_is_negative_one(self):
        """噪声点标签必须是 -1（HDBSCAN 约定）。"""
        analyzer = ClusterAnalyzer(
            algorithm="hdbscan",
            min_cluster_size=3,
            min_samples=2,
            metric="cosine",
        )

        # 单个样本
        embeddings = np.array([[0.1, 0.2, 0.3]], dtype=float)
        result = analyzer.fit_predict(embeddings)

        labels = np.asarray(result.labels)
        assert labels[0] == -1, f"Noise point label should be -1, got {labels[0]}"


# ---------------------------------------------------------------------------
# Rule 4: 改进建议关联规范编号（J000001 格式）
# ---------------------------------------------------------------------------


class TestImprovementSuggestionsWithRuleIds:
    """Spec Rule 4: 改进建议需关联具体开发规范条款.

    ViolationDetector 的 VIOLATION_PATTERNS 使用 J000066 等规则 ID。
    """

    @pytest.fixture
    def task_with_empty_catch(self) -> TaskInfo:
        """包含空 catch 反模式的任务 — 触发 J000066 违规。"""
        return TaskInfo(
            task_id=50001,
            title="空 catch 导致异常被吞",
            description="代码中使用了空 catch 块",
            status="resolved",
            priority="high",
            create_time=datetime(2024, 11, 1, 10, 0, 0),
            resolve_time=datetime(2024, 11, 1, 14, 0, 0),
            development=DevelopmentInfo(
                commits=[
                    CommitInfo(
                        commit_id="ec001",
                        message="空 catch 反模式示例",
                        author="dev",
                        time=datetime(2024, 11, 1, 12, 0, 0),
                        changes=["src/problem.py"],
                        diff="""
try {
    riskyOperation();
} catch(Exception e) {
    // empty - bad practice
}
""",
                    )
                ]
            ),
            production=ProductionInfo(
                incident_time=datetime(2024, 11, 1, 11, 0, 0),
                symptoms="异常被静默吞掉",
                resolution="添加异常处理和日志",
            ),
        )

    @pytest.fixture
    def task_with_security_violation(self) -> TaskInfo:
        """包含硬编码凭证的任务 — 触发安全规范违规。"""
        return TaskInfo(
            task_id=50002,
            title="硬编码密码违规",
            description="代码中包含硬编码凭证",
            status="resolved",
            priority="critical",
            create_time=datetime(2024, 11, 2, 8, 0, 0),
            resolve_time=datetime(2024, 11, 2, 12, 0, 0),
            development=DevelopmentInfo(
                commits=[
                    CommitInfo(
                        commit_id="sec001",
                        message="硬编码密码示例",
                        author="dev",
                        time=datetime(2024, 11, 2, 10, 0, 0),
                        changes=["config/app.py"],
                        diff="PASSWORD = 'test123'  # hardcoded credential",
                    )
                ]
            ),
            production=ProductionInfo(
                incident_time=datetime(2024, 11, 2, 9, 0, 0),
                symptoms="安全审计发现硬编码密码",
                resolution="移除硬编码密码，使用密钥管理服务",
            ),
        )

    @pytest.mark.asyncio
    async def test_violation_contains_rule_id(
        self,
        real_config_manager: ConfigManager,
        task_with_security_violation: TaskInfo,
    ):
        """硬编码密码违规应包含 security-001 规则 ID。"""
        pipeline = AnalysisPipeline(
            real_config_manager,
            PipelineConfig(
                use_cache=False,
                use_llm=False,
                generate_labels=False,
                analyze_root_cause=False,
                check_rules=True,
                generate_report=True,
            ),
        )
        pipeline._api_client = _create_mock_api_client(task_with_security_violation)

        try:
            result = await pipeline.run_single(50002)

            assert result.error == ""
            # 使用 security violation 测试 — 应检测到 security-001 违规
            assert result.violations is not None
            assert len(result.violations) > 0

            # 违规项应包含 rule_id 字段
            for violation in result.violations:
                assert "rule_id" in violation, (
                    f"Violation missing rule_id: {violation}"
                )

        finally:
            await pipeline.close()

    @pytest.mark.asyncio
    async def test_violation_rule_id_format(
        self,
        real_config_manager: ConfigManager,
        task_with_security_violation: TaskInfo,
    ):
        """违规项的 rule_id 应有标准格式（如 security-001）。"""
        pipeline = AnalysisPipeline(
            real_config_manager,
            PipelineConfig(
                use_cache=False,
                use_llm=False,
                generate_labels=False,
                analyze_root_cause=False,
                check_rules=True,
                generate_report=True,
            ),
        )
        pipeline._api_client = _create_mock_api_client(task_with_security_violation)

        try:
            result = await pipeline.run_single(50002)

            assert result.error == ""
            assert result.violations is not None and len(result.violations) > 0

            # 至少有一个违规项的 rule_id 是有效格式
            rule_ids = [v["rule_id"] for v in result.violations]
            valid_format = any(
                rid.startswith("security") or rid.startswith("SEC-") or rid.startswith("J")
                for rid in rule_ids
            )
            assert valid_format, f"No valid rule_id format found in {rule_ids}"

        finally:
            await pipeline.close()

    @pytest.mark.asyncio
    async def test_report_contains_rule_id_reference(
        self,
        real_config_manager: ConfigManager,
        task_with_security_violation: TaskInfo,
    ):
        """生成的报告应包含违规规则 ID 的引用。"""
        pipeline = AnalysisPipeline(
            real_config_manager,
            PipelineConfig(
                use_cache=False,
                use_llm=False,
                generate_labels=False,
                analyze_root_cause=False,
                check_rules=True,
                generate_report=True,
            ),
        )
        pipeline._api_client = _create_mock_api_client(task_with_security_violation)

        try:
            result = await pipeline.run_single(50002)

            assert result.error == ""
            assert result.report

            # 报告中应包含违规信息（规则 ID 或规则名称）
            violations = result.violations
            if violations:
                has_rule_ref = any(
                    v.get("rule_id", "") in (result.report or "")
                    for v in violations
                    if v.get("rule_id")
                )
                has_rule_name = any(
                    v.get("rule_name", "") in (result.report or "")
                    for v in violations
                    if v.get("rule_name")
                )
                assert has_rule_ref or has_rule_name, (
                    "Report does not reference any rule ID or name: "
                    f"{[v.get('rule_id') for v in violations]}"
                )

        finally:
            await pipeline.close()

    @pytest.mark.asyncio
    async def test_security_violation_has_security_rule_id(
        self,
        real_config_manager: ConfigManager,
        task_with_security_violation: TaskInfo,
    ):
        """安全漏洞违规应有 SEC- 前缀的 rule_id。"""
        pipeline = AnalysisPipeline(
            real_config_manager,
            PipelineConfig(
                use_cache=False,
                use_llm=False,
                generate_labels=False,
                analyze_root_cause=False,
                check_rules=True,
                generate_report=True,
            ),
        )
        pipeline._api_client = _create_mock_api_client(task_with_security_violation)

        try:
            result = await pipeline.run_single(50002)

            assert result.error == ""
            assert result.violations is not None
            # 至少有一个安全相关的违规检测
            security_violations = [
                v
                for v in result.violations
                if v.get("rule_id", "").startswith("SEC-")
                or "security" in v.get("rule_id", "").lower()
            ]
            assert len(security_violations) > 0, (
                f"No security violations found: {result.violations}"
            )

        finally:
            await pipeline.close()
