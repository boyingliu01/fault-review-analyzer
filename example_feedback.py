"""反馈循环系统使用示例"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from src.feedback import (
    Feedback, FeedbackType, FeedbackRating,
    FeedbackManager, RetrainingTrigger
)


def example_basic_usage():
    """基本使用示例"""
    print("=" * 60)
    print("Example 1: 基本反馈管理")
    print("=" * 60)

    # 创建反馈管理器
    manager = FeedbackManager(db_path="data/example_feedback.db")

    # 1. 添加反馈
    print("\n1. 添加反馈...")
    feedback = Feedback(
        task_id="task-11745664",  # 一个实际的故障单号
        feedback_type=FeedbackType.LABEL_CORRECTION,
        original_result={
            "cluster_id": 5,
            "label": "数据库连接问题",
            "confidence": 0.75
        },
        corrected_result={
            "cluster_id": 8,
            "label": "网络超时问题",
            "confidence": 0.90
        },
        rating=FeedbackRating.GOOD,
        comment="原始分类不准确，应该归类为网络问题",
        created_by="analyst-zhang"
    )

    feedback_id = manager.add_feedback(feedback)
    print(f"   ✓ 反馈已添加，ID: {feedback_id}")

    # 2. 获取反馈
    print("\n2. 获取反馈...")
    retrieved = manager.get_feedback(feedback_id)
    print(f"   ✓ 任务ID: {retrieved.task_id}")
    print(f"   ✓ 反馈类型: {retrieved.feedback_type}")
    print(f"   ✓ 评分: {retrieved.rating}")

    # 3. 审核反馈
    print("\n3. 审核反馈...")
    success = manager.review_feedback(feedback_id, "admin-li")
    print(f"   ✓ 审核成功: {success}")

    # 4. 添加更多反馈
    print("\n4. 添加更多示例反馈...")
    feedbacks = [
        Feedback(
            task_id=f"task-{i}",
            feedback_type=FeedbackType.LABEL_CORRECTION if i % 2 == 0
            else FeedbackType.ROOT_CAUSE_CORRECTION,
            original_result={"data": f"test-{i}"},
            rating=FeedbackRating.POOR if i % 3 == 0
            else FeedbackRating.GOOD,
            created_by=f"user-{i}"
        )
        for i in range(10)
    ]
    for fb in feedbacks:
        manager.add_feedback(fb)
    print(f"   ✓ 已添加 {len(feedbacks)} 个反馈")

    # 5. 获取统计
    print("\n5. 获取反馈统计...")
    stats = manager.get_statistics()
    print(f"   ✓ 总反馈数: {stats['total_feedback']}")
    print(f"   ✓ 已审核: {stats['reviewed_count']}")
    print(f"   ✓ 纠错率: {stats['correction_ratio']:.2%}")
    print(f"   ✓ 好评率: {stats['positive_ratio']:.2%}")

    manager.close()
    print("\n✅ 示例 1 完成\n")


def example_trigger():
    """重训练触发器示例"""
    print("=" * 60)
    print("Example 2: 重训练触发器")
    print("=" * 60)

    manager = FeedbackManager(db_path="data/example_trigger.db")

    # 添加大量纠错反馈，模拟需要重训练的场景
    print("\n1. 添加模拟反馈数据...")
    for i in range(80):
        fb = Feedback(
            task_id=f"task-{1000+i}",
            feedback_type=FeedbackType.LABEL_CORRECTION if i % 2 == 0
            else FeedbackType.ROOT_CAUSE_CORRECTION,
            original_result={"label": "wrong-label"},
            corrected_result={"label": "correct-label"},
            rating=FeedbackRating.POOR if i % 4 == 0 else FeedbackRating.FAIR,
            created_by="tester"
        )
        manager.add_feedback(fb)

    # 添加一些正常反馈
    for i in range(20):
        fb = Feedback(
            task_id=f"task-{2000+i}",
            feedback_type=FeedbackType.GENERAL,
            original_result={"data": "good"},
            rating=FeedbackRating.GOOD if i % 2 == 0 else FeedbackRating.EXCELLENT,
            created_by="user"
        )
        manager.add_feedback(fb)
    print("   ✓ 已添加 100 个反馈")

    # 创建触发器
    print("\n2. 检查重训练触发条件...")
    trigger = RetrainingTrigger(
        manager,
        min_feedback_count=50,
        min_positive_ratio=0.6,
        max_correction_ratio=0.5
    )

    # 检查是否应该触发重训练
    should_trigger, info = trigger.should_trigger_retraining()
    print(f"   ✓ 是否触发重训练: {should_trigger}")
    print(f"   ✓ 原因: {info}")

    # 获取重训练建议
    print("\n3. 获取重训练建议...")
    recommendations = trigger.get_retraining_recommendations()
    print(f"   ✓ 发现 {len(recommendations)} 个改进建议:")
    for rec in recommendations:
        print(f"     - [{rec['priority']}] {rec['area']}: {rec['suggestion']}")
        print(f"       依据: {rec['evidence']}")

    # 触发重训练流程
    print("\n4. 触发重训练流程...")
    result = trigger.trigger_retraining_pipeline()
    if result["triggered"]:
        print("   ✓ 重训练流程已触发!")
        print(f"   ✓ 推荐改进: {len(result['recommendations'])} 项")
        print(f"   ✓ 训练样本: {result['training_data_stats']['total_samples']} 个")
        print("   ✓ 下一步:")
        for step in result["next_steps"]:
            print(f"     {step}")

    manager.close()
    print("\n✅ 示例 2 完成\n")


if __name__ == "__main__":
    try:
        # 创建数据目录
        Path("data").mkdir(exist_ok=True)

        # 运行示例
        example_basic_usage()
        example_trigger()

        print("=" * 60)
        print("🎉 所有示例运行完成!")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ 示例运行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
