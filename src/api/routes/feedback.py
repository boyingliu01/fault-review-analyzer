"""反馈 API 路由"""

import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any

from loguru import logger

# 确保能找到 src 模块
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from fastapi import APIRouter, Depends, HTTPException, Query

    from src.feedback.manager import FeedbackManager, FeedbackRating, FeedbackType
    from src.feedback.models import (
        Feedback,
        FeedbackCreate,
        FeedbackListResponse,
        FeedbackResponse,
        FeedbackReview,
        FeedbackStatsResponse,
        RecurrencePatternListResponse,
    )
    from src.feedback.recurrence_detector import RecurrenceDetector
except Exception as e:
    logger.error(f"Failed to import modules: {e}")
    raise

router = APIRouter(prefix="/feedback", tags=["feedback"])


def get_feedback_manager() -> Generator[FeedbackManager, None, None]:
    """依赖注入 - 获取反馈管理器实例"""
    manager = FeedbackManager()
    try:
        yield manager
    finally:
        manager.close()


@router.post("", response_model=FeedbackResponse)
async def create_feedback(
    feedback: FeedbackCreate, manager: FeedbackManager = Depends(get_feedback_manager)
) -> Any:
    """创建反馈"""
    try:
        # 创建完整的 Feedback 对象
        full_feedback = Feedback(
            task_id=feedback.task_id,
            feedback_type=feedback.feedback_type,
            original_result=feedback.original_result,
            corrected_result=feedback.corrected_result,
            rating=feedback.rating,
            comment=feedback.comment,
            created_by=feedback.created_by,
        )

        feedback_id = manager.add_feedback(full_feedback)
        created = manager.get_feedback(feedback_id)

        if not created:
            raise HTTPException(status_code=500, detail="Failed to create feedback")

        return created
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating feedback: exception_type={type(e).__name__}")
        raise HTTPException(status_code=500, detail="An internal error occurred") from e


@router.get("/{feedback_id}", response_model=FeedbackResponse)
async def get_feedback(
    feedback_id: str, manager: FeedbackManager = Depends(get_feedback_manager)
) -> Any:
    """获取反馈详情"""
    feedback = manager.get_feedback(feedback_id)
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return feedback


@router.get("/task/{task_id}", response_model=list[FeedbackResponse])
async def get_task_feedback(
    task_id: str, manager: FeedbackManager = Depends(get_feedback_manager)
) -> Any:
    """获取任务的反馈列表"""
    return manager.get_feedback_by_task(task_id)


@router.get("", response_model=FeedbackListResponse)
async def list_feedback(
    feedback_type: FeedbackType | None = Query(None),
    rating: int | None = Query(None, ge=1, le=5),
    reviewed: bool | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    manager: FeedbackManager = Depends(get_feedback_manager),
) -> Any:
    """列出反馈"""
    rating_enum = FeedbackRating(rating) if rating else None

    items = manager.list_feedback(
        feedback_type=feedback_type,
        rating=rating_enum,
        reviewed=reviewed,
        limit=limit,
        offset=offset,
    )

    # 获取总数（简化版，实际项目中应该单独查询）
    all_items = manager.list_feedback(
        feedback_type=feedback_type, rating=rating_enum, reviewed=reviewed, limit=1000000
    )

    return FeedbackListResponse(
        total=len(all_items),
        items=[FeedbackResponse.model_validate(item) for item in items],
        offset=offset,
        limit=limit,
    )


@router.post("/{feedback_id}/review", response_model=FeedbackResponse)
async def review_feedback(
    feedback_id: str,
    review: FeedbackReview,
    manager: FeedbackManager = Depends(get_feedback_manager),
) -> Any:
    """审核反馈"""
    success = manager.review_feedback(feedback_id, review.reviewed_by)
    if not success:
        raise HTTPException(status_code=404, detail="Feedback not found")

    updated = manager.get_feedback(feedback_id)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to retrieve updated feedback")

    return updated


@router.get("/stats/summary", response_model=FeedbackStatsResponse)
async def get_feedback_statistics(manager: FeedbackManager = Depends(get_feedback_manager)) -> Any:
    """获取反馈统计"""
    stats = manager.get_statistics()
    return FeedbackStatsResponse(
        total_feedback=stats.get("total_feedback", 0),
        by_type=stats.get("by_type", {}),
        by_rating=stats.get("by_rating", {}),
        reviewed_count=stats.get("reviewed_count", 0),
        correction_ratio=stats.get("correction_ratio", 0.0),
        positive_ratio=stats.get("positive_ratio", 0.0),
    )


@router.get("/recurrences", response_model=RecurrencePatternListResponse)
async def get_recurrences(
    similarity_threshold: float = Query(0.7, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=500),
    manager: FeedbackManager = Depends(get_feedback_manager),
) -> Any:
    """获取复发模式

    从已有反馈数据中检测重复出现的故障模式。

    Args:
        similarity_threshold: 相似度阈值（0~1）
        limit: 返回的最大模式数
        manager: 反馈管理器

    Returns:
        RecurrencePatternListResponse: 复发模式列表
    """
    try:
        feedback_list = manager.list_feedback(reviewed=None, limit=10000)

        # 从反馈中提取故障特征用于复发检测
        tasks = []
        task_ids = []
        for fb in feedback_list:
            original = fb.original_result or {}
            tasks.append(
                {
                    "task_id": fb.task_id,
                    "title": original.get("title", ""),
                    "description": original.get("description", ""),
                    "problem_category": original.get("problem_category", ""),
                    "severity": original.get("severity", "medium"),
                    "create_time": fb.created_at,
                }
            )
            task_ids.append(fb.task_id)

        detector = RecurrenceDetector(similarity_threshold=similarity_threshold)
        patterns = detector.detect(tasks, task_ids=task_ids)

        return RecurrencePatternListResponse(
            total=len(patterns),
            items=patterns[:limit],
            offset=0,
            limit=limit,
        )

    except Exception as e:
        logger.error(f"Error detecting recurrences: exception_type={type(e).__name__}")
        raise HTTPException(status_code=500, detail="An internal error occurred") from e
