"""P0 集成测试: Preprocessor 输出 → RulesEngine 输入的协议兼容性。

验证边界数据（空描述、超长文本、特殊字符）在组件间传递的正确性。
"""

from datetime import datetime

import pytest

from src.api.models import (
    CodeChange,
    CommitInfo,
    DesignInfo,
    DevelopmentInfo,
    ProductionInfo,
    RequirementInfo,
    TaskInfo,
)
from src.preprocessor.processor import DataPreprocessor
from src.rules.engine import RulesEngine


@pytest.fixture
def preprocessor():
    return DataPreprocessor()


@pytest.fixture
def rules_engine():
    return RulesEngine()


def _make_task(**overrides) -> TaskInfo:
    """快速构造 TaskInfo，支持覆盖任意字段。"""
    defaults = {
        "task_id": 20001,
        "title": "默认测试任务",
        "description": "默认描述",
        "status": "resolved",
        "priority": "medium",
        "create_time": datetime(2024, 6, 1, 10, 0, 0),
    }
    defaults.update(overrides)
    return TaskInfo(**defaults)


class TestPreprocessorToRulesProtocol:
    """测试 Preprocessor 输出与 RulesEngine 输入的协议兼容性。"""

    def test_empty_description_passes_through(
        self, preprocessor: DataPreprocessor, rules_engine: RulesEngine
    ):
        """空描述的任务应能正常走完全流程。"""
        task = _make_task(task_id=20001, title="空描述任务", description="")

        preprocessed = preprocessor.process(task)
        assert preprocessed.combined_text  # 至少有标题

        violations = rules_engine.check(task.model_dump())
        assert isinstance(violations, list)

    def test_empty_title_and_description(
        self, preprocessor: DataPreprocessor, rules_engine: RulesEngine
    ):
        """标题和描述都为空时不应崩溃。"""
        task = _make_task(task_id=20002, title="无标题无描述", description="")

        preprocessor.process(task)
        # 标题不为空（有 "无标题无描述"），但 description 为空
        violations = rules_engine.check(task.model_dump())
        assert isinstance(violations, list)

    def test_very_long_text(self, preprocessor: DataPreprocessor, rules_engine: RulesEngine):
        """超长文本应被预处理器截断，规则引擎也能正常处理。"""
        long_text = "A" * 50000
        task = _make_task(task_id=20003, title="超长文本测试", description=long_text)

        preprocessed = preprocessor.process(task)
        # 预处理器应截断（max_text_length=8000，加上段标题前缀可能略超）
        assert len(preprocessed.combined_text) <= 8100

        violations = rules_engine.check(task.model_dump())
        assert isinstance(violations, list)

    def test_special_characters_in_text(
        self, preprocessor: DataPreprocessor, rules_engine: RulesEngine
    ):
        """包含特殊字符的文本应能正常处理。"""
        special_text = "测试 <script>alert('xss')</script> & \"quotes\" 'single' \n\t换行"
        task = _make_task(task_id=20004, title="特殊字符<>&\"'", description=special_text)

        preprocessed = preprocessor.process(task)
        assert preprocessed.task_id == 20004

        violations = rules_engine.check(task.model_dump())
        assert isinstance(violations, list)

    def test_unicode_and_emoji(self, preprocessor: DataPreprocessor, rules_engine: RulesEngine):
        """Unicode 和 emoji 字符应能正常处理。"""
        unicode_text = "日本語テスト 한국어 中文 🚀🔥💥 error occurred"
        task = _make_task(task_id=20005, title="Unicode🌍", description=unicode_text)

        preprocessor.process(task)
        violations = rules_engine.check(task.model_dump())
        assert isinstance(violations, list)

    def test_security_pattern_detected_in_commit_message(self, rules_engine: RulesEngine):
        """规则引擎应能从 commit message 中检测到敏感信息模式。"""
        task = _make_task(
            task_id=20006,
            title="含敏感信息的提交",
            development=DevelopmentInfo(
                commits=[
                    CommitInfo(
                        commit_id="sec001",
                        message="password = 'secret123'  # 临时硬编码",
                        author="dev",
                        time=datetime(2024, 6, 1, 9, 0, 0),
                        changes=["config.py"],
                    )
                ]
            ),
        )

        violations = rules_engine.check(task.model_dump())
        # 应检测到 security-001 规则违规
        rule_ids = [v.rule_id for v in violations]
        assert "security-001" in rule_ids

    def test_no_development_data_no_crash(
        self, preprocessor: DataPreprocessor, rules_engine: RulesEngine
    ):
        """没有 development 数据的任务不应导致规则引擎崩溃。"""
        task = _make_task(
            task_id=20007,
            title="无开发信息",
            development=DevelopmentInfo(),  # 空的
        )

        preprocessor.process(task)
        violations = rules_engine.check(task.model_dump())
        assert isinstance(violations, list)
        assert len(violations) == 0  # 没有代码可检查

    def test_multiple_commits_all_checked(self, rules_engine: RulesEngine):
        """多个 commit 的 message 都应被规则引擎检查。"""
        task = _make_task(
            task_id=20008,
            title="多提交测试",
            development=DevelopmentInfo(
                commits=[
                    CommitInfo(
                        commit_id="c1",
                        message="正常提交",
                        author="dev",
                        time=datetime(2024, 6, 1, 9, 0, 0),
                        changes=["a.py"],
                    ),
                    CommitInfo(
                        commit_id="c2",
                        message="api_key = 'sk-12345' 临时调试",
                        author="dev",
                        time=datetime(2024, 6, 1, 10, 0, 0),
                        changes=["b.py"],
                    ),
                ]
            ),
        )

        violations = rules_engine.check(task.model_dump())
        rule_ids = [v.rule_id for v in violations]
        # 第二个 commit 包含 api_key 模式
        assert "security-001" in rule_ids

    def test_preprocessed_segments_metadata_preserved(self, preprocessor: DataPreprocessor):
        """预处理后的 segments 应保留正确的 metadata。"""
        task = _make_task(
            task_id=20009,
            title="元数据测试",
            requirement=RequirementInfo(
                requirement_id="REQ-100",
                description="需求描述内容",
            ),
        )

        preprocessed = preprocessor.process(task)
        req_segments = [s for s in preprocessed.segments if s.type == "requirement"]
        assert len(req_segments) == 1
        assert req_segments[0].metadata.get("source") == "requirement"

    def test_rules_engine_builtin_rules_loaded(self, rules_engine: RulesEngine):
        """RulesEngine 应自动加载内置规则。"""
        rules = rules_engine.get_all_rules()
        assert len(rules) > 0
        rule_ids = {r.id for r in rules}
        assert "security-001" in rule_ids
        assert "security-002" in rule_ids

    def test_full_task_with_all_sections(
        self, preprocessor: DataPreprocessor, rules_engine: RulesEngine
    ):
        """包含所有 section 的完整任务应能走完全流程。"""
        task = TaskInfo(
            task_id=20010,
            title="完整任务测试",
            description="完整描述",
            status="resolved",
            priority="high",
            create_time=datetime(2024, 6, 1, 10, 0, 0),
            resolve_time=datetime(2024, 6, 1, 14, 0, 0),
            requirement=RequirementInfo(
                requirement_id="REQ-200",
                description="需求内容",
            ),
            design=DesignInfo(
                design_document="设计文档内容",
                technical_solution="技术方案",
            ),
            development=DevelopmentInfo(
                commits=[
                    CommitInfo(
                        commit_id="full001",
                        message="正常提交信息",
                        author="dev",
                        time=datetime(2024, 6, 1, 9, 0, 0),
                        changes=["src/main.py"],
                    )
                ],
                code_changes=[
                    CodeChange(
                        file_path="src/main.py",
                        old_content="old",
                        new_content="new",
                        change_type="modify",
                    )
                ],
            ),
            production=ProductionInfo(
                incident_time=datetime(2024, 6, 1, 11, 0, 0),
                symptoms="服务异常",
                logs=["ERROR: something failed"],
                stack_traces=["Traceback..."],
                resolution="修复问题",
            ),
        )

        preprocessed = preprocessor.process(task)
        segment_types = {s.type for s in preprocessed.segments}
        assert "title" in segment_types
        assert "description" in segment_types
        assert "requirement" in segment_types
        assert "design" in segment_types

        violations = rules_engine.check(task.model_dump())
        assert isinstance(violations, list)
