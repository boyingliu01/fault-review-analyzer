from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field


class ClusterInfo(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    cluster_id: int = Field(..., description="聚类ID")
    member_indices: list[int] = Field(default_factory=list, description="成员索引")
    size: int = Field(default=0, description="聚类大小")
    centroid: list[float] | None = Field(default=None, description="聚类中心")
    label: str = Field(default="", description="聚类标签")
    keywords: list[str] = Field(default_factory=list, description="关键词")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")


class ClusterResult(BaseModel):
    labels: list[int] = Field(default_factory=list, description="聚类标签")
    n_clusters: int = Field(default=0, description="聚类数量")
    n_noise: int = Field(default=0, description="噪声点数量")
    clusters: list[ClusterInfo] = Field(default_factory=list, description="聚类信息")
    probabilities: list[float] | None = Field(default=None, description="聚类概率")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")

    def get_cluster(self, cluster_id: int) -> ClusterInfo | None:
        for cluster in self.clusters:
            if cluster.cluster_id == cluster_id:
                return cluster
        return None

    def get_noise_indices(self) -> list[int]:
        return [i for i, label in enumerate(self.labels) if label == -1]


class DimensionReductionResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    embeddings_2d: np.ndarray = Field(..., description="2D降维结果")
    embeddings_3d: np.ndarray | None = Field(default=None, description="3D降维结果")
    n_components: int = Field(default=2, description="降维维度")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")
