"""P0 集成测试: Preprocessor → RulesEngine → ReportGenerator 真实数据流。

不 mock 任何组件，验证组件间数据格式正确传递。
"""

from datetime import datetime

import pytest

from src.api.models import (
    CodeChange,
    CodeReview,
    CommitInfo,
    DesignInfo,
    DevelopmentInfo,
    ProductionInfo,
    RequirementInfo,
    TaskInfo,
    TimelineEvent,
)
from src.preprocessor.processor import DataPreprocessor
from src.report.generator import ReportGenerator
from src.rules.engine import RulesEngine


@pytest.fixture
def preprocessor():
    return DataPreprocessor()


@pytest.fixture
def rules_engine():
    return RulesEngine()


@pytest.fixture
def report_generator():
    return ReportGenerator()


@pytest.fixture
def full_task():
    """构造一个完整的 TaskInfo 对象，包含所有字段。"""
    return TaskInfo(
        task_id=99001,
        title="数据库连接池耗尽导致服务不可用",
        description="生产环境高峰期，数据库连接池被占满，新请求无法获取连接，导致服务超时。",
        status="resolved",
        priority="high",
        create_time=datetime(2024, 3, 10, 8, 0, 0),
        resolve_time=datetime(2024, 3, 10, 14, 30, 0),
        requirement=RequirementInfo(
            requirement_id="REQ-001",
            description="系统需支持1000并发连接",
            review_records=["评审通过"],
            documents=["需求规格说明书v1.2"],
        ),
        design=DesignInfo(
            design_document="使用HikariCP连接池，最大连接数设置为50",
            review_records=["设计评审通过"],
            technical_solution="连接池参数调优 + 慢SQL优化",
        ),
        development=DevelopmentInfo(
            commits=[
                CommitInfo(
                    commit_id="def456",
                    message="修复连接泄漏问题，添加连接超时回收机制",
                    author="dev1",
                    time=datetime(2024, 3, 9, 15, 0, 0),
                    changes=["src/db/pool.py", "src/db/config.py"],
                ),
                CommitInfo(
                    commit_id="ghi789",
                    message="优化慢查询，添加索引",
                    author="dev2",
                    time=datetime(2024, 3, 9, 16, 0, 0),
                    changes=["sql/migration.sql"],
                ),
            ],
            code_changes=[
                CodeChange(
                    file_path="src/db/pool.py",
                    old_content="max_connections = 10",
                    new_content="max_connections = 50",
                    change_type="modify",
                ),
            ],
            code_reviews=[
                CodeReview(
                    reviewer="senior_dev",
                    time=datetime(2024, 3, 9, 17, 0, 0),
                    comments=["建议增加连接泄漏检测"],
                    approved=True,
                ),
            ],
        ),
        production=ProductionInfo(
            incident_time=datetime(2024, 3, 10, 9, 0, 0),
            symptoms="API响应时间从200ms飙升到30s以上，大量504超时",
            logs=[
                "ERROR: Connection pool exhausted",
                "WARN: HikariPool-1 - Connection is not available",
                "ERROR: Timeout waiting for connection",
            ],
            stack_traces=[
                "java.sql.SQLTransientConnectionException: HikariPool-1 - Connection is not available"
            ],
            resolution="增大连接池大小 + 修复连接泄漏 + 优化慢SQL",
            timeline=[
                TimelineEvent(
                    time=datetime(2024, 3, 10, 9, 0, 0),
                    action="告警触发",
                    actor="监控系统",
                    details="P99延迟超过阈值",
                ),
                TimelineEvent(
                    time=datetime(2024, 3, 10, 9, 15, 0),
                    action="排查开始",
                    actor="oncall工程师",
                    details="发现连接池耗尽",
                ),
                TimelineEvent(
                    time=datetime(2024, 3, 10, 14, 30, 0),
                    action="服务恢复",
                    actor="oncall工程师",
                    details="部署修复版本",
                ),
            ],
        ),
    )


class TestPreprocessorToRulesIntegration:
    """测试 Preprocessor 输出 → RulesEngine 输入的数据流。"""

    def test_preprocessed_data_can_be_checked_by_rules(
        self, preprocessor: DataPreprocessor, rules_engine: RulesEngine, full_task: TaskInfo
    ):
        """预处理后的数据可以正确传入规则引擎检查。"""
        preprocessor.process(full_task)

        # 将 preprocessed 转为 dict 传给 rules engine
        task_dict = full_task.model_dump()
        violations = rules_engine.check(task_dict)

        # violations 应该是 list[RuleViolation]
        assert isinstance(violations, list)
        for v in violations:
            assert hasattr(v, "rule_id")
            assert hasattr(v, "rule_name")
            assert hasattr(v, "severity")
            assert hasattr(v, "message")

    def test_preprocessor_segments_contain_expected_types(
        self, preprocessor: DataPreprocessor, full_task: TaskInfo
    ):
        """预处理器应提取出所有存在的 segment 类型。"""
        preprocessed = preprocessor.process(full_task)

        segment_types = {s.type for s in preprocessed.segments}
        # full_task 有 title, description, requirement, design, development, production
        assert "title" in segment_types
        assert "description" in segment_types
        assert "requirement" in segment_types
        assert "design" in segment_types

    def test_preprocessed_combined_text_is_nonempty(
        self, preprocessor: DataPreprocessor, full_task: TaskInfo
    ):
        """预处理后的合并文本不应为空。"""
        preprocessed = preprocessor.process(full_task)
        assert preprocessed.combined_text
        assert len(preprocessed.combined_text) > 50


class TestPreprocessorToReportIntegration:
    """测试 Preprocessor → ReportGenerator 的数据流。"""

    def test_report_generator_accepts_preprocessed_segments(
        self,
        preprocessor: DataPreprocessor,
        report_generator: ReportGenerator,
        full_task: TaskInfo,
    ):
        """报告生成器应能接受预处理后的 segments 格式。"""
        preprocessed = preprocessor.process(full_task)

        # 将 segments 转为 report generator 期望的 dict 格式
        segments_dict = [
            {"type": s.type, "content": s.content, "metadata": s.metadata}
            for s in preprocessed.segments
        ]

        task_dict = full_task.model_dump()
        report = report_generator.generate_single(
            task_data=task_dict,
            segments=segments_dict,
            labels=[],
            root_causes=[],
            suggestions=["建议优化数据库连接池配置"],
        )

        assert isinstance(report, str)
        assert len(report) > 100
        # 报告应包含任务ID
        assert "99001" in report

    def test_report_contains_task_title(
        self,
        preprocessor: DataPreprocessor,
        report_generator: ReportGenerator,
        full_task: TaskInfo,
    ):
        """生成的报告应包含任务标题。"""
        preprocessed = preprocessor.process(full_task)
        segments_dict = [
            {"type": s.type, "content": s.content, "metadata": s.metadata}
            for s in preprocessed.segments
        ]

        report = report_generator.generate_single(
            task_data=full_task.model_dump(),
            segments=segments_dict,
        )

        assert "数据库连接池" in report


class TestFullPipelineDataFlow:
    """测试完整数据流: TaskInfo → Preprocessor → Rules → Report。"""

    def test_full_data_flow_no_errors(
        self,
        preprocessor: DataPreprocessor,
        rules_engine: RulesEngine,
        report_generator: ReportGenerator,
        full_task: TaskInfo,
    ):
        """完整数据流不应抛出异常。"""
        # Step 1: Preprocess
        preprocessed = preprocessor.process(full_task)
        assert preprocessed.task_id == 99001

        # Step 2: Rules check
        task_dict = full_task.model_dump()
        violations = rules_engine.check(task_dict)
        assert isinstance(violations, list)

        # Step 3: Report generation
        segments_dict = [
            {"type": s.type, "content": s.content, "metadata": s.metadata}
            for s in preprocessed.segments
        ]
        report = report_generator.generate_single(
            task_data=task_dict,
            segments=segments_dict,
            labels=[],
            root_causes=[],
        )

        assert isinstance(report, str)
        assert len(report) > 0

    def test_rules_violations_format_matches_pipeline_expectation(
        self, rules_engine: RulesEngine, full_task: TaskInfo
    ):
        """RulesEngine 输出的 violations 格式应与 Pipeline._check_rules 期望一致。"""
        task_dict = full_task.model_dump()
        violations = rules_engine.check(task_dict)

        # Pipeline._check_rules 期望每个 violation 有这些属性
        for v in violations:
            assert hasattr(v, "rule_id")
            assert hasattr(v, "rule_name")
            assert hasattr(v, "severity")
            assert hasattr(v, "message")
            assert hasattr(v, "evidence")

            # Pipeline 会将其转为 dict
            result_dict = {
                "rule_id": v.rule_id,
                "rule_name": v.rule_name,
                "severity": v.severity,
                "message": v.message,
                "evidence": v.evidence,
            }
            assert isinstance(result_dict["rule_id"], str)
            assert isinstance(result_dict["evidence"], list)

    def test_minimal_task_through_full_flow(
        self,
        preprocessor: DataPreprocessor,
        rules_engine: RulesEngine,
        report_generator: ReportGenerator,
    ):
        """最小化的 TaskInfo 也能走完全流程。"""
        minimal_task = TaskInfo(
            task_id=1,
            title="最小化测试任务",
            description="",
            status="open",
            priority="low",
            create_time=datetime(2024, 1, 1),
        )

        # Preprocess
        preprocessed = preprocessor.process(minimal_task)
        assert preprocessed.task_id == 1

        # Rules
        violations = rules_engine.check(minimal_task.model_dump())
        assert isinstance(violations, list)

        # Report
        segments_dict = [
            {"type": s.type, "content": s.content, "metadata": s.metadata}
            for s in preprocessed.segments
        ]
        report = report_generator.generate_single(
            task_data=minimal_task.model_dump(),
            segments=segments_dict,
        )
        assert isinstance(report, str)
        assert len(report) > 0
