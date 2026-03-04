from typing import Any

import numpy as np
from pydantic import BaseModel, Field


class EmbeddingResult(BaseModel):
    task_id: int = Field(..., description="任务ID")
    embedding: list[float] = Field(..., description="嵌入向量")
    model: str = Field(..., description="使用的模型")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")

    def to_numpy(self) -> np.ndarray:
        return np.array(self.embedding)


class BatchEmbeddingResult(BaseModel):
    results: list[EmbeddingResult] = Field(default_factory=list)
    total_count: int = Field(default=0)
    success_count: int = Field(default=0)
    error_count: int = Field(default=0)
    model: str = Field(default="", description="使用的模型")
