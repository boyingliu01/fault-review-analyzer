"""反馈管理器测试"""

import os
import tempfile
from pathlib import Path

import pytest

from src.feedback.manager import FeedbackManager
from src.feedback.models import Feedback, FeedbackRating, FeedbackType


@pytest.fixture
def temp_db_path():
    """创建临时数据库文件"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    # Windows 上的文件锁定问题，尝试多次删除
    import time

    for _ in range(3):
        try:
            if Path(path).exists():
                Path(path).unlink()
            break
        except OSError:
            time.sleep(0.1)


@pytest.fixture
def feedback_manager(temp_db_path):
    """创建反馈管理器实例"""
    return FeedbackManager(db_path=temp_db_path)


@pytest.fixture
def sample_feedback():
    """创建示例反馈数据"""
    return Feedback(
        task_id="task-123",
        feedback_type=FeedbackType.LABEL_CORRECTION,
        original_result={"label": "Original Label", "confidence": 0.8},
        corrected_result={"label": "Corrected Label", "confidence": 0.9},
        rating=FeedbackRating.GOOD,
        comment="标签需要修正",
        created_by="test-user",
    )


class TestFeedbackManager:
    """反馈管理器测试"""

    def test_add_feedback(self, feedback_manager, sample_feedback):
        """测试添加反馈"""
        feedback_id = feedback_manager.add_feedback(sample_feedback)
        assert feedback_id is not None
        assert feedback_id == sample_feedback.id

    def test_get_feedback(self, feedback_manager, sample_feedback):
        """测试获取反馈"""
        feedback_id = feedback_manager.add_feedback(sample_feedback)
        retrieved = feedback_manager.get_feedback(feedback_id)

        assert retrieved is not None
        assert retrieved.id == feedback_id
        assert retrieved.task_id == sample_feedback.task_id
        assert retrieved.feedback_type == sample_feedback.feedback_type
        assert retrieved.rating == sample_feedback.rating
        assert retrieved.created_by == sample_feedback.created_by

    def test_get_nonexistent_feedback(self, feedback_manager):
        """测试获取不存在的反馈"""
        retrieved = feedback_manager.get_feedback("nonexistent-id")
        assert retrieved is None

    def test_get_feedback_by_task(self, feedback_manager):
        """测试按任务获取反馈"""
        # 添加多个不同任务的反馈
        feedback1 = Feedback(
            task_id="task-123",
            feedback_type=FeedbackType.GENERAL,
            original_result={"data": "test1"},
            rating=FeedbackRating.GOOD,
            created_by="user1",
        )
        feedback2 = Feedback(
            task_id="task-123",
            feedback_type=FeedbackType.LABEL_CORRECTION,
            original_result={"data": "test2"},
            rating=FeedbackRating.EXCELLENT,
            created_by="user2",
        )
        feedback3 = Feedback(
            task_id="task-456",
            feedback_type=FeedbackType.GENERAL,
            original_result={"data": "test3"},
            rating=FeedbackRating.FAIR,
            created_by="user3",
        )

        feedback_manager.add_feedback(feedback1)
        feedback_manager.add_feedback(feedback2)
        feedback_manager.add_feedback(feedback3)

        # 获取任务 task-123 的反馈
        task_feedbacks = feedback_manager.get_feedback_by_task("task-123")
        assert len(task_feedbacks) == 2

        # 获取任务 task-456 的反馈
        task_feedbacks_456 = feedback_manager.get_feedback_by_task("task-456")
        assert len(task_feedbacks_456) == 1
        assert task_feedbacks_456[0].id == feedback3.id

    def test_list_feedback_by_type(self, feedback_manager):
        """测试按类型筛选反馈"""
        feedback1 = Feedback(
            task_id="task-1",
            feedback_type=FeedbackType.LABEL_CORRECTION,
            original_result={"data": "test1"},
            rating=FeedbackRating.GOOD,
            created_by="user1",
        )
        feedback2 = Feedback(
            task_id="task-2",
            feedback_type=FeedbackType.ROOT_CAUSE_CORRECTION,
            original_result={"data": "test2"},
            rating=FeedbackRating.GOOD,
            created_by="user2",
        )

        feedback_manager.add_feedback(feedback1)
        feedback_manager.add_feedback(feedback2)

        # 按类型筛选
        label_feedbacks = feedback_manager.list_feedback(
            feedback_type=FeedbackType.LABEL_CORRECTION
        )
        assert len(label_feedbacks) == 1
        assert label_feedbacks[0].id == feedback1.id

    def test_list_feedback_by_rating(self, feedback_manager):
        """测试按评分筛选反馈"""
        feedback1 = Feedback(
            task_id="task-1",
            feedback_type=FeedbackType.GENERAL,
            original_result={"data": "test1"},
            rating=FeedbackRating.EXCELLENT,
            created_by="user1",
        )
        feedback2 = Feedback(
            task_id="task-2",
            feedback_type=FeedbackType.GENERAL,
            original_result={"data": "test2"},
            rating=FeedbackRating.POOR,
            created_by="user2",
        )

        feedback_manager.add_feedback(feedback1)
        feedback_manager.add_feedback(feedback2)

        # 按评分筛选
        excellent_feedbacks = feedback_manager.list_feedback(rating=FeedbackRating.EXCELLENT)
        assert len(excellent_feedbacks) == 1
        assert excellent_feedbacks[0].id == feedback1.id

    def test_review_feedback(self, feedback_manager, sample_feedback):
        """测试审核反馈"""
        feedback_id = feedback_manager.add_feedback(sample_feedback)

        # 初始未审核
        feedback = feedback_manager.get_feedback(feedback_id)
        assert feedback.reviewed is False
        assert feedback.reviewed_by is None
        assert feedback.reviewed_at is None

        # 执行审核
        success = feedback_manager.review_feedback(feedback_id, "reviewer-user")
        assert success is True

        # 验证审核结果
        reviewed = feedback_manager.get_feedback(feedback_id)
        assert reviewed.reviewed is True
        assert reviewed.reviewed_by == "reviewer-user"
        assert reviewed.reviewed_at is not None

    def test_get_statistics(self, feedback_manager):
        """测试获取统计数据"""
        # 添加多个反馈
        feedbacks = [
            Feedback(
                task_id=f"task-{i}",
                feedback_type=ft,
                original_result={"data": f"test-{i}"},
                rating=r,
                created_by=f"user-{i}",
            )
            for i, (ft, r) in enumerate(
                [
                    (FeedbackType.LABEL_CORRECTION, FeedbackRating.GOOD),
                    (FeedbackType.ROOT_CAUSE_CORRECTION, FeedbackRating.EXCELLENT),
                    (FeedbackType.FALSE_POSITIVE, FeedbackRating.FAIR),
                    (FeedbackType.GENERAL, FeedbackRating.POOR),
                    (FeedbackType.LABEL_CORRECTION, FeedbackRating.EXCELLENT),
                ]
            )
        ]

        for fb in feedbacks:
            feedback_manager.add_feedback(fb)

        # 审核其中两个
        feedback_manager.review_feedback(feedbacks[0].id, "reviewer")
        feedback_manager.review_feedback(feedbacks[1].id, "reviewer")

        # 获取统计
        stats = feedback_manager.get_statistics()

        assert stats["total_feedback"] == 5
        assert stats["by_type"]["label_correction"] == 2
        assert stats["by_type"]["root_cause_correction"] == 1
        assert stats["by_rating"][5] == 2  # EXCELLENT
        assert stats["by_rating"][4] == 1  # GOOD
        assert stats["reviewed_count"] == 2
        assert stats["correction_ratio"] == 3 / 5  # 3个纠错类型
        assert stats["positive_ratio"] == 3 / 5  # 3个4分及以上
