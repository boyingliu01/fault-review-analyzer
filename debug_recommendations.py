"""调试建议生成问题"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.feedback.models import Feedback, FeedbackType, FeedbackRating
from src.feedback.manager import FeedbackManager
from src.feedback.trigger import RetrainingTrigger


# 调试方法
def debug_recommendations():
    print("Debugging recommendation generation...")

    # 创建临时数据库
    import tempfile
    import os
    fd, temp_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        manager = FeedbackManager(db_path=temp_path)

        # 添加大量标签纠正反馈
        for i in range(15):
            fb = Feedback(
                task_id=f"task-{i}",
                feedback_type=FeedbackType.LABEL_CORRECTION,
                original_result={"data": f"test-{i}"},
                rating=FeedbackRating.POOR,
                created_by=f"user-{i}"
            )
            manager.add_feedback(fb)

        # 打印统计信息
        print("\n=== Statistics ===")
        stats = manager.get_statistics()
        print(f"Total feedback: {stats['total_feedback']}")
        print(f"By type: {stats['by_type']}")
        print(f"By rating: {stats['by_rating']}")

        # 创建触发器
        trigger = RetrainingTrigger(
            manager,
            min_feedback_count=50,
            min_positive_ratio=0.6,
            max_correction_ratio=0.5
        )

        # 获取建议
        recommendations = trigger.get_retraining_recommendations()
        print(f"\nRecommendations returned: {len(recommendations)}")
        for rec in recommendations:
            print(f"  - {rec['area']}: {rec['suggestion']} ({rec['priority']})")

        manager.close()
    finally:
        # 清理
        import time
        time.sleep(0.2)
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except:
            pass


if __name__ == "__main__":
    debug_recommendations()
