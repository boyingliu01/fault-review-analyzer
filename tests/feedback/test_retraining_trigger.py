"""重训练触发器测试"""

import os
import tempfile
from pathlib import Path

import pytest

from src.feedback.manager import FeedbackManager
from src.feedback.models import Feedback, FeedbackRating, FeedbackType
from src.feedback.trigger import RetrainingTrigger


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


class TestRetrainingTrigger:
    """重训练触发器测试"""

    def test_init(self, feedback_manager):
        """测试初始化"""
        trigger = RetrainingTrigger(feedback_manager)
        assert isinstance(trigger, RetrainingTrigger)
        assert trigger.feedback_manager == feedback_manager
        assert trigger.min_feedback_count == 100
        assert trigger.min_positive_ratio == 0.7
        assert trigger.max_correction_ratio == 0.3

    def test_should_trigger_insufficient_feedback(self, feedback_manager):
        """测试反馈数量不足时不触发"""
        trigger = RetrainingTrigger(feedback_manager, min_feedback_count=10)
        should_trigger, info = trigger.should_trigger_retraining()

        assert should_trigger is False
        assert info["reason"] == "insufficient_feedback"
        assert info["current"] == 0
        assert info["required"] == 10

    def test_should_trigger_high_correction_rate(self, feedback_manager):
        """测试纠错率过高触发重训练"""
        # 添加大量纠错反馈
        for i in range(20):
            feedback_manager.add_feedback(
                Feedback(
                    task_id=f"task-{i}",
                    feedback_type=FeedbackType.LABEL_CORRECTION
                    if i % 2 == 0
                    else FeedbackType.ROOT_CAUSE_CORRECTION,
                    original_result={"data": f"test-{i}"},
                    corrected_result={"data": f"fixed-{i}"},
                    rating=FeedbackRating.POOR,
                    created_by=f"user-{i}",
                )
            )

        # 配置阈值
        trigger = RetrainingTrigger(
            feedback_manager,
            min_feedback_count=10,
            max_correction_ratio=0.6,  # 60% 纠错率阈值
        )

        should_trigger, info = trigger.should_trigger_retraining()

        assert should_trigger is True
        assert info["reason"] == "high_correction_rate"
        assert info["current_ratio"] > 0.6
        assert info["threshold"] == 0.6

    def test_should_trigger_low_positive_ratio(self, feedback_manager):
        """测试好评率过低触发重训练"""
        # 添加大量差评反馈
        for i in range(15):
            feedback_manager.add_feedback(
                Feedback(
                    task_id=f"task-{i}",
                    feedback_type=FeedbackType.GENERAL,
                    original_result={"data": f"test-{i}"},
                    rating=FeedbackRating.POOR if i % 2 == 0 else FeedbackRating.VERY_POOR,
                    created_by=f"user-{i}",
                )
            )

        # 配置阈值
        trigger = RetrainingTrigger(
            feedback_manager,
            min_feedback_count=10,
            min_positive_ratio=0.4,  # 40% 好评率阈值
        )

        should_trigger, info = trigger.should_trigger_retraining()

        assert should_trigger is True
        assert info["reason"] == "low_positive_rating"
        assert info["current_ratio"] < 0.4
        assert info["threshold"] == 0.4

    def test_should_trigger_all_conditions_met(self, feedback_manager):
        """测试满足所有条件时不触发"""
        # 添加大量正面反馈，且纠错反馈比例低
        for i in range(20):
            feedback_type = (
                FeedbackType.GENERAL
                if i % 2 == 0
                else FeedbackType.FALSE_POSITIVE
                if i % 5 != 0
                else FeedbackType.LABEL_CORRECTION
            )
            feedback_manager.add_feedback(
                Feedback(
                    task_id=f"task-{i}",
                    feedback_type=feedback_type,
                    original_result={"data": f"test-{i}"},
                    rating=FeedbackRating.GOOD if i % 2 == 0 else FeedbackRating.EXCELLENT,
                    created_by=f"user-{i}",
                )
            )

        trigger = RetrainingTrigger(
            feedback_manager,
            min_feedback_count=15,
            min_positive_ratio=0.7,
            max_correction_ratio=0.3,
        )

        should_trigger, info = trigger.should_trigger_retraining()

        assert should_trigger is False
        assert info["reason"] == "all_metrics_healthy"

    def test_get_retraining_recommendations(self, feedback_manager):
        """测试获取重训练建议"""
        # 添加标签纠正和根因纠正反馈
        for i in range(30):
            feedback_manager.add_feedback(
                Feedback(
                    task_id=f"task-{i}",
                    feedback_type=FeedbackType.LABEL_CORRECTION
                    if i < 15
                    else FeedbackType.ROOT_CAUSE_CORRECTION,
                    original_result={"data": f"test-{i}"},
                    corrected_result={"data": f"fixed-{i}"},
                    rating=FeedbackRating.POOR,
                    created_by=f"user-{i}",
                )
            )

        trigger = RetrainingTrigger(feedback_manager, min_feedback_count=10)

        recommendations = trigger.get_retraining_recommendations()
        assert len(recommendations) >= 2

        # 检查是否有标签生成和根因分析的建议
        label_recommendations = [r for r in recommendations if r["area"] == "label_generation"]
        assert len(label_recommendations) > 0
        assert label_recommendations[0]["priority"] == "high"

        root_cause_recommendations = [
            r for r in recommendations if r["area"] == "root_cause_analysis"
        ]
        assert len(root_cause_recommendations) > 0
        assert root_cause_recommendations[0]["priority"] == "high"

    def test_trigger_retraining_pipeline_not_triggered(self, feedback_manager):
        """测试不触发重训练流程"""
        trigger = RetrainingTrigger(feedback_manager, min_feedback_count=10, min_positive_ratio=0.7)

        result = trigger.trigger_retraining_pipeline()
        assert result["triggered"] is False
        assert result["reason"]["reason"] == "insufficient_feedback"

    def test_trigger_retraining_pipeline_triggered(self, feedback_manager):
        """测试触发重训练流程"""
        for i in range(15):
            feedback_manager.add_feedback(
                Feedback(
                    task_id=f"task-{i}",
                    feedback_type=FeedbackType.LABEL_CORRECTION,
                    original_result={"data": f"test-{i}"},
                    corrected_result={"data": f"fixed-{i}"},
                    rating=FeedbackRating.POOR,
                    created_by=f"user-{i}",
                )
            )

        trigger = RetrainingTrigger(
            feedback_manager, min_feedback_count=10, max_correction_ratio=0.5
        )

        result = trigger.trigger_retraining_pipeline()
        assert result["triggered"] is True
        assert "recommendations" in result
        assert "training_data_stats" in result
        assert "next_steps" in result

        assert result["training_data_stats"]["total_samples"] == 15
        assert "by_type" in result["training_data_stats"]
        assert result["training_data_stats"]["by_type"]["label_correction"] == 15
