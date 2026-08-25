"""反馈数据模型"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class FeedbackType(str, Enum):
    LABEL_CORRECTION = "label_correction"  # 标签纠正
    ROOT_CAUSE_CORRECTION = "root_cause_correction"  # 根因纠正
    FALSE_POSITIVE = "false_positive"  # 误报
    FALSE_NEGATIVE = "false_negative"  # 漏报
    GENERAL = "general"  # 一般反馈


class FeedbackRating(int, Enum):
    VERY_POOR = 1
    POOR = 2
    FAIR = 3
    GOOD = 4
    EXCELLENT = 5


class Feedback(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    feedback_type: FeedbackType
    original_result: dict[str, Any]  # 原始分析结果
    corrected_result: dict[str, Any] | None = None  # 纠正后的结果
    rating: FeedbackRating
    comment: str | None = None
    created_by: str
    created_at: datetime = Field(default_factory=datetime.now)
    reviewed: bool = False
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None


# API 请求/响应模型
class FeedbackCreate(BaseModel):
    task_id: str
    feedback_type: FeedbackType
    original_result: dict[str, Any]
    corrected_result: dict[str, Any] | None = None
    rating: FeedbackRating
    comment: str | None = None
    created_by: str


class FeedbackReview(BaseModel):
    reviewed_by: str


class FeedbackResponse(Feedback):
    model_config = {"from_attributes": True}


class FeedbackListResponse(BaseModel):
    total: int
    items: list[FeedbackResponse]
    offset: int
    limit: int


class FeedbackStatsResponse(BaseModel):
    total_feedback: int
    by_type: dict[str, int]
    by_rating: dict[int, int]
    reviewed_count: int
    correction_ratio: float
    positive_ratio: float
