"""微调触发器"""

from typing import Any

from loguru import logger

from src.feedback.manager import FeedbackManager


class RetrainingTrigger:
    """重训练触发器 - 当反馈积累到一定阈值时触发模型微调"""

    def __init__(
        self,
        feedback_manager: FeedbackManager,
        min_feedback_count: int = 100,  # 最小反馈数
        min_positive_ratio: float = 0.7,  # 最小好评率
        max_correction_ratio: float = 0.3,  # 最大纠错率（超过则触发重训练）
    ):
        self.feedback_manager = feedback_manager
        self.min_feedback_count = min_feedback_count
        self.min_positive_ratio = min_positive_ratio
        self.max_correction_ratio = max_correction_ratio

    def should_trigger_retraining(self) -> tuple[bool, dict[str, Any]]:
        """检查是否应该触发重训练

        Returns:
            (should_trigger, reason_info)
        """
        stats = self.feedback_manager.get_statistics()

        # 检查反馈数量
        total_feedback = stats.get("total_feedback", 0)
        if total_feedback < self.min_feedback_count:
            return False, {
                "reason": "insufficient_feedback",
                "current": total_feedback,
                "required": self.min_feedback_count,
            }

        # 检查纠错率
        correction_ratio = stats.get("correction_ratio", 0)
        if correction_ratio > self.max_correction_ratio:
            return True, {
                "reason": "high_correction_rate",
                "current_ratio": correction_ratio,
                "threshold": self.max_correction_ratio,
            }

        # 检查好评率
        positive_ratio = stats.get("positive_ratio", 0)
        if positive_ratio < self.min_positive_ratio:
            return True, {
                "reason": "low_positive_rating",
                "current_ratio": positive_ratio,
                "threshold": self.min_positive_ratio,
            }

        return False, {"reason": "all_metrics_healthy"}

    def get_retraining_recommendations(self) -> list[dict[str, Any]]:
        """获取重训练建议

        分析反馈数据，识别需要改进的模型方面
        """
        recommendations = []

        # 分析反馈类型分布
        by_type = self.feedback_manager.get_statistics().get("by_type", {})

        # 如果标签纠正较多，建议改进标签生成模型
        if by_type.get("label_correction", 0) > 10:
            recommendations.append(
                {
                    "priority": "high",
                    "area": "label_generation",
                    "suggestion": "标签生成模型需要改进",
                    "evidence": f"收到 {by_type['label_correction']} 个标签纠正反馈",
                }
            )

        # 如果根因纠正较多，建议改进根因分析模型
        if by_type.get("root_cause_correction", 0) > 10:
            recommendations.append(
                {
                    "priority": "high",
                    "area": "root_cause_analysis",
                    "suggestion": "根因分析模型需要改进",
                    "evidence": f"收到 {by_type['root_cause_correction']} 个根因纠正反馈",
                }
            )

        # 如果误报/漏报较多，建议改进聚类模型
        if by_type.get("false_positive", 0) + by_type.get("false_negative", 0) > 15:
            recommendations.append(
                {
                    "priority": "medium",
                    "area": "clustering_model",
                    "suggestion": "聚类模型需要改进以减少误报和漏报",
                    "evidence": f"收到 {by_type.get('false_positive', 0)} 个误报和 {by_type.get('false_negative', 0)} 个漏报反馈",
                }
            )

        return recommendations

    def trigger_retraining_pipeline(self) -> dict[str, Any]:
        """触发重训练流程

        当满足触发条件时，执行重训练流程
        """
        should_trigger, info = self.should_trigger_retraining()

        if not should_trigger:
            logger.debug("Retraining not triggered - all metrics healthy")
            return {"triggered": False, "reason": info}

        logger.info("Triggering retraining pipeline based on feedback metrics")

        # 获取重训练建议
        recommendations = self.get_retraining_recommendations()

        # 准备训练数据
        feedback_list = self.feedback_manager.list_feedback(reviewed=None, limit=10000)

        training_data = []
        for feedback in feedback_list:
            training_data.append(
                {
                    "task_id": feedback.task_id,
                    "original_result": feedback.original_result,
                    "corrected_result": feedback.corrected_result,
                    "feedback_type": feedback.feedback_type,
                    "rating": feedback.rating,
                }
            )

        # 返回触发结果
        return {
            "triggered": True,
            "reason": info,
            "recommendations": recommendations,
            "training_data_stats": {
                "total_samples": len(training_data),
                "by_type": self.feedback_manager.get_statistics().get("by_type", {}),
            },
            "next_steps": [
                "1. 导出训练数据到训练管道",
                "2. 启动模型微调任务",
                "3. 评估新模型性能",
                "4. 部署新模型到生产环境",
            ],
        }
