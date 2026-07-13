"""聚类模块数据模型

注意：ClusterInfo 和 ClusterResult 已迁移到 src/core/models.py
本模块保持向后兼容性，直接导入核心模型
"""

from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from src.core.models import ClusterInfo, ClusterResult


class DimensionReductionResult(BaseModel):
    """降维结果模型"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    embeddings_2d: np.ndarray = Field(..., description="2D降维结果")
    embeddings_3d: np.ndarray | None = Field(default=None, description="3D降维结果")
    n_components: int = Field(default=2, description="降维维度")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")
