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


class RecurrencePattern(BaseModel):
    """复发模式 - 检测到的重复故障模式"""

    pattern_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str  # 模式名称
    description: str = ""  # 模式描述
    keywords: list[str] = Field(default_factory=list)  # 模式关键词
    task_ids: list[str] = Field(default_factory=list)  # 关联的故障单ID
    occurrence_count: int = Field(default=0, ge=0)  # 出现次数
    first_seen: datetime = Field(default_factory=datetime.now)  # 首次发现
    last_seen: datetime = Field(default_factory=datetime.now)  # 最近发现
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)  # 相似度阈值
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)  # 置信度
    severity: str = Field(default="medium")  # 严重程度: high/medium/low
    metadata: dict[str, Any] = Field(default_factory=dict)  # 额外元数据


class RecurrencePatternListResponse(BaseModel):
    total: int
    items: list[RecurrencePattern]
    offset: int
    limit: int
