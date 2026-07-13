"""核心数据模型测试"""

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from src.core.models import (
    AnalysisResult,
    ClusterInfo,
    EmbeddingData,
    LabelInfo,
    RootCauseInfo,
    TaskData,
    TaskPriority,
    TaskStatus,
)


class TestTaskData:
    """TaskData 模型测试"""

    def test_valid_task_data(self):
        """测试有效的任务数据"""
        create_time = datetime.now()
        task_data = TaskData(
            task_id=12345,
            title="测试任务",
            description="这是一个测试任务",
            status=TaskStatus.OPEN,
            priority=TaskPriority.HIGH,
            create_time=create_time,
        )
        assert task_data.task_id == 12345
        assert task_data.title == "测试任务"
        assert task_data.status == TaskStatus.OPEN

    def test_task_id_must_be_positive(self):
        """测试 task_id 必须是正整数"""
        with pytest.raises(ValidationError, match="task_id 必须是正整数"):
            TaskData(
                task_id=0,
                title="测试任务",
                status=TaskStatus.OPEN,
                priority=TaskPriority.MEDIUM,
                create_time=datetime.now(),
            )
        with pytest.raises(ValidationError, match="task_id 必须是正整数"):
            TaskData(
                task_id=-1,
                title="测试任务",
                status=TaskStatus.OPEN,
                priority=TaskPriority.MEDIUM,
                create_time=datetime.now(),
            )

    def test_title_cannot_be_empty(self):
        """测试标题不能为空"""
        with pytest.raises(ValidationError, match="任务标题不能为空"):
            TaskData(
                task_id=12345,
                title="",
                status=TaskStatus.OPEN,
                priority=TaskPriority.MEDIUM,
                create_time=datetime.now(),
            )
        with pytest.raises(ValidationError, match="任务标题不能为空"):
            TaskData(
                task_id=12345,
                title="   ",
                status=TaskStatus.OPEN,
                priority=TaskPriority.MEDIUM,
                create_time=datetime.now(),
            )

    def test_resolve_time_cannot_be_earlier_than_create_time(self):
        """测试解决时间不能早于创建时间"""
        create_time = datetime.now()
        resolve_time = create_time - timedelta(hours=1)
        with pytest.raises(ValidationError, match="解决时间不能早于创建时间"):
            TaskData(
                task_id=12345,
                title="测试任务",
                status=TaskStatus.RESOLVED,
                priority=TaskPriority.MEDIUM,
                create_time=create_time,
                resolve_time=resolve_time,
            )
        # 正常情况
        resolve_time = create_time + timedelta(hours=1)
        task_data = TaskData(
            task_id=12345,
            title="测试任务",
            status=TaskStatus.RESOLVED,
            priority=TaskPriority.MEDIUM,
            create_time=create_time,
            resolve_time=resolve_time,
        )
        assert task_data.resolve_time == resolve_time

    def test_title_is_stripped(self):
        """测试标题会被自动去空格"""
        task_data = TaskData(
            task_id=12345,
            title="  测试任务  ",
            status=TaskStatus.OPEN,
            priority=TaskPriority.MEDIUM,
            create_time=datetime.now(),
        )
        assert task_data.title == "测试任务"


class TestAnalysisResult:
    """AnalysisResult 模型测试"""

    def test_valid_analysis_result(self):
        """测试有效的分析结果"""
        analysis_result = AnalysisResult(
            task_id=12345,
            is_complete=True,
            violation_count=2,
            root_cause_count=1,
            cluster_id=3,
            confidence_score=0.85,
        )
        assert analysis_result.task_id == 12345
        assert analysis_result.is_complete is True
        assert analysis_result.confidence_score == 0.85

    def test_task_id_must_be_positive(self):
        """测试 task_id 必须是正整数"""
        with pytest.raises(ValidationError, match="task_id 必须是正整数"):
            AnalysisResult(task_id=0)

    def test_confidence_score_bounds(self):
        """测试置信度分数在 0-1 之间"""
        with pytest.raises(ValidationError):
            AnalysisResult(task_id=12345, confidence_score=-0.1)
        with pytest.raises(ValidationError):
            AnalysisResult(task_id=12345, confidence_score=1.1)
        # 边界值测试
        result1 = AnalysisResult(task_id=12345, confidence_score=0.0)
        result2 = AnalysisResult(task_id=12345, confidence_score=1.0)
        assert result1.confidence_score == 0.0
        assert result2.confidence_score == 1.0


class TestClusterInfo:
    """ClusterInfo 模型测试"""

    def test_valid_cluster_info(self):
        """测试有效的聚类信息"""
        cluster_info = ClusterInfo(
            cluster_id=0,
            size=10,
            centroid=[0.5, 0.5, 0.5],
            member_indices=[1, 2, 3, 4, 5],
            label="测试聚类",
            keywords=["测试", "聚类"],
        )
        assert cluster_info.cluster_id == 0
        assert cluster_info.size == 10
        assert cluster_info.label == "测试聚类"

    def test_cluster_id_must_be_non_negative(self):
        """测试 cluster_id 必须是非负整数"""
        with pytest.raises(ValidationError, match="cluster_id 必须是非负整数"):
            ClusterInfo(cluster_id=-1)

    def test_size_must_be_non_negative(self):
        """测试 size 必须是非负整数"""
        with pytest.raises(ValidationError) as exc_info:
            ClusterInfo(cluster_id=0, size=-1)
        assert "必须是非负整数" in str(exc_info.value)


class TestEmbeddingData:
    """EmbeddingData 模型测试"""

    def test_valid_embedding_data(self):
        """测试有效的嵌入数据"""
        embedding_data = EmbeddingData(
            task_id=12345,
            embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
            text="测试文本",
            model="test-model",
            media_type="text",
        )
        assert embedding_data.task_id == 12345
        assert len(embedding_data.embedding) == 5
        assert embedding_data.media_type == "text"

    def test_task_id_must_be_positive(self):
        """测试 task_id 必须是正整数"""
        with pytest.raises(ValidationError, match="task_id 必须是正整数"):
            EmbeddingData(task_id=0, embedding=[0.1, 0.2])

    def test_embedding_cannot_be_empty(self):
        """测试嵌入向量不能为空"""
        with pytest.raises(ValidationError, match="嵌入向量不能为空"):
            EmbeddingData(task_id=12345, embedding=[])

    def test_media_type_validation(self):
        """测试媒体类型验证"""
        with pytest.raises(ValidationError, match="媒体类型必须是"):
            EmbeddingData(task_id=12345, embedding=[0.1, 0.2], media_type="invalid")
        # 验证有效值
        for media_type in ["text", "image", "mixed"]:
            embedding_data = EmbeddingData(
                task_id=12345, embedding=[0.1, 0.2], media_type=media_type
            )
            assert embedding_data.media_type == media_type


class TestLabelInfo:
    """LabelInfo 模型测试"""

    def test_valid_label_info(self):
        """测试有效的标签信息"""
        label_info = LabelInfo(
            label_id="label-001",
            name="测试标签",
            category="测试类别",
            confidence=0.9,
            description="这是一个测试标签",
        )
        assert label_info.label_id == "label-001"
        assert label_info.name == "测试标签"
        assert label_info.confidence == 0.9

    def test_label_id_cannot_be_empty(self):
        """测试标签ID不能为空"""
        with pytest.raises(ValidationError, match="标签ID不能为空"):
            LabelInfo(label_id="", name="测试标签")
        with pytest.raises(ValidationError, match="标签ID不能为空"):
            LabelInfo(label_id="   ", name="测试标签")

    def test_name_cannot_be_empty(self):
        """测试标签名称不能为空"""
        with pytest.raises(ValidationError, match="标签名称不能为空"):
            LabelInfo(label_id="label-001", name="")

    def test_label_id_is_stripped(self):
        """测试标签ID会被自动去空格"""
        label_info = LabelInfo(label_id="  label-001  ", name="测试标签")
        assert label_info.label_id == "label-001"

    def test_confidence_bounds(self):
        """测试置信度在 0-1 之间"""
        with pytest.raises(ValidationError):
            LabelInfo(label_id="label-001", name="测试标签", confidence=-0.1)
        with pytest.raises(ValidationError):
            LabelInfo(label_id="label-001", name="测试标签", confidence=1.1)


class TestRootCauseInfo:
    """RootCauseInfo 模型测试"""

    def test_valid_root_cause_info(self):
        """测试有效的根因信息"""
        root_cause_info = RootCauseInfo(
            root_cause_id="rc-001",
            description="这是根因描述",
            category="技术问题",
            evidence=["证据1", "证据2"],
            confidence=0.85,
            improvement_measures=["措施1", "措施2"],
        )
        assert root_cause_info.root_cause_id == "rc-001"
        assert root_cause_info.description == "这是根因描述"
        assert len(root_cause_info.evidence) == 2

    def test_root_cause_id_cannot_be_empty(self):
        """测试根因ID不能为空"""
        with pytest.raises(ValidationError, match="根因ID不能为空"):
            RootCauseInfo(root_cause_id="", description="根因描述")
        with pytest.raises(ValidationError, match="根因ID不能为空"):
            RootCauseInfo(root_cause_id="   ", description="根因描述")

    def test_description_cannot_be_empty(self):
        """测试根因描述不能为空"""
        with pytest.raises(ValidationError, match="根因描述不能为空"):
            RootCauseInfo(root_cause_id="rc-001", description="")

    def test_root_cause_id_is_stripped(self):
        """测试根因ID会被自动去空格"""
        root_cause_info = RootCauseInfo(root_cause_id="  rc-001  ", description="根因描述")
        assert root_cause_info.root_cause_id == "rc-001"

    def test_confidence_bounds(self):
        """测试置信度在 0-1 之间"""
        with pytest.raises(ValidationError):
            RootCauseInfo(
                root_cause_id="rc-001", description="根因描述", confidence=-0.1
            )
        with pytest.raises(ValidationError):
            RootCauseInfo(
                root_cause_id="rc-001", description="根因描述", confidence=1.1
            )


class TestEnums:
    """枚举测试"""

    def test_task_status_enum_values(self):
        """测试任务状态枚举值"""
        assert TaskStatus.OPEN == "open"
        assert TaskStatus.IN_PROGRESS == "in_progress"
        assert TaskStatus.RESOLVED == "resolved"
        assert TaskStatus.CLOSED == "closed"

    def test_task_priority_enum_values(self):
        """测试任务优先级枚举值"""
        assert TaskPriority.LOW == "low"
        assert TaskPriority.MEDIUM == "medium"
        assert TaskPriority.HIGH == "high"
        assert TaskPriority.CRITICAL == "critical"
