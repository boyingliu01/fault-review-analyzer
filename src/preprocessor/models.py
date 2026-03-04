from typing import Any

from pydantic import BaseModel, Field


class TextSegment(BaseModel):
    task_id: int = Field(..., description="任务ID")
    type: str = Field(..., description="文本类型")
    content: str = Field(..., description="文本内容")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")


class ProcessedTask(BaseModel):
    task_id: int = Field(..., description="任务ID")
    segments: list[TextSegment] = Field(default_factory=list, description="文本片段列表")
    combined_text: str = Field(default="", description="合并文本")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")

    def get_segments_by_type(self, segment_type: str) -> list[TextSegment]:
        return [s for s in self.segments if s.type == segment_type]


class PreprocessResult(BaseModel):
    tasks: list[ProcessedTask] = Field(default_factory=list)
    total_count: int = Field(default=0)
    success_count: int = Field(default=0)
    error_count: int = Field(default=0)
    errors: list[dict[str, Any]] = Field(default_factory=list)
