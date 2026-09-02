"""V4 核心数据模型 — 供所有 V4 模块共享使用。

命名空间独立于 src/api/models.py（V1）。
V4 CodeChange 是 commit 级别（含 diff），与 V1 文件级 CodeChange 不同。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


class TaskStatus(str, Enum):
    """任务状态枚举"""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TaskPriority(str, Enum):
    """任务优先级枚举"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskData(BaseModel):
    """任务数据模型"""

    task_id: int = Field(..., description="任务ID")
    title: str = Field(..., description="任务标题")
    description: str = Field(default="", description="任务描述")
    status: TaskStatus = Field(..., description="任务状态")
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM, description="任务优先级")
    create_time: datetime = Field(..., description="创建时间")
    resolve_time: datetime | None = Field(default=None, description="解决时间")
    assignee: str = Field(default="", description="经办人")
    reporter: str = Field(default="", description="报告人")
    project_name: str = Field(default="", description="项目名称")
    module_name: str = Field(default="", description="模块名称")

    @field_validator("task_id")
    @classmethod
    def validate_task_id(cls, v: int, _info: ValidationInfo) -> int:
        """验证任务ID必须是正整数"""
        if v <= 0:
            raise ValueError(f"task_id 必须是正整数，实际值: {v}")
        return v

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str, _info: ValidationInfo) -> str:
        """验证标题不能为空"""
        if not v or v.strip() == "":
            raise ValueError("任务标题不能为空")
        return v.strip()

    @field_validator("resolve_time")
    @classmethod
    def validate_resolve_time(cls, v: datetime | None, info: ValidationInfo) -> datetime | None:
        """验证解决时间不能早于创建时间"""
        if v is not None and info.data.get("create_time") and v < info.data["create_time"]:
            raise ValueError("解决时间不能早于创建时间")
        return v


class AnalysisResult(BaseModel):
    """分析结果模型"""

    task_id: int = Field(..., description="任务ID")
    analysis_time: datetime = Field(default_factory=datetime.now, description="分析时间")
    is_complete: bool = Field(default=False, description="分析是否完成")
    violation_count: int = Field(default=0, ge=0, description="违规数量")
    root_cause_count: int = Field(default=0, ge=0, description="根因数量")
    cluster_id: int = Field(default=-1, description="聚类ID（-1表示噪声点）")
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度分数")

    @field_validator("task_id")
    @classmethod
    def validate_task_id(cls, v: int, _info: ValidationInfo) -> int:
        """验证任务ID必须是正整数"""
        if v <= 0:
            raise ValueError(f"task_id 必须是正整数，实际值: {v}")
        return v


class ClusterInfo(BaseModel):
    """聚类信息模型"""

    cluster_id: int = Field(..., description="聚类ID")
    size: int = Field(default=0, description="聚类大小")
    centroid: list[float] | None = Field(default=None, description="聚类中心")
    member_indices: list[int] = Field(default_factory=list, description="成员索引")
    label: str = Field(default="", description="聚类标签")
    keywords: list[str] = Field(default_factory=list, description="关键词")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")

    @field_validator("cluster_id")
    @classmethod
    def validate_cluster_id(cls, v: int, _info: ValidationInfo) -> int:
        """验证聚类ID必须是非负整数"""
        if v < 0:
            raise ValueError(f"cluster_id 必须是非负整数，实际值: {v}")
        return v

    @field_validator("size")
    @classmethod
    def validate_size(cls, v: int, _info: ValidationInfo) -> int:
        """验证聚类大小必须是非负整数"""
        if v < 0:
            raise ValueError(f"聚类大小必须是非负整数，实际值: {v}")
        return v


class EmbeddingData(BaseModel):
    """嵌入数据模型"""

    task_id: int = Field(..., description="任务ID")
    embedding: list[float] = Field(..., description="嵌入向量")
    text: str = Field(default="", description="用于向量化的文本")
    model: str = Field(default="", description="使用的模型")
    media_type: str = Field(default="text", description="媒体类型：text / image / mixed")
    metadata: dict[str, Any] = Field(default_factory=dict, description="额外元数据")

    @field_validator("task_id")
    @classmethod
    def validate_task_id(cls, v: int, _info: ValidationInfo) -> int:
        """验证任务ID必须是正整数"""
        if v <= 0:
            raise ValueError(f"task_id 必须是正整数，实际值: {v}")
        return v

    @field_validator("embedding")
    @classmethod
    def validate_embedding(cls, v: list[float], _info: ValidationInfo) -> list[float]:
        """验证嵌入向量不能为空"""
        if not v:
            raise ValueError("嵌入向量不能为空")
        return v

    @field_validator("media_type")
    @classmethod
    def validate_media_type(cls, v: str, _info: ValidationInfo) -> str:
        """验证媒体类型"""
        valid_types = ["text", "image", "mixed"]
        if v not in valid_types:
            raise ValueError(f"媒体类型必须是 {valid_types} 中的一种，实际值: {v}")
        return v


class LabelInfo(BaseModel):
    """标签信息模型"""

    label_id: str = Field(..., description="标签ID")
    name: str = Field(..., description="标签名称")
    category: str = Field(default="", description="标签类别")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度")
    description: str = Field(default="", description="标签描述")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")

    @field_validator("label_id")
    @classmethod
    def validate_label_id(cls, v: str, _info: ValidationInfo) -> str:
        """验证标签ID不能为空"""
        if not v or v.strip() == "":
            raise ValueError("标签ID不能为空")
        return v.strip()

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str, _info: ValidationInfo) -> str:
        """验证标签名称不能为空"""
        if not v or v.strip() == "":
            raise ValueError("标签名称不能为空")
        return v.strip()


class RootCauseInfo(BaseModel):
    """根因信息模型"""

    root_cause_id: str = Field(..., description="根因ID")
    description: str = Field(..., description="根因描述")
    category: str = Field(default="", description="根因类别")
    evidence: list[str] = Field(default_factory=list, description="证据列表")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度")
    improvement_measures: list[str] = Field(default_factory=list, description="改进措施")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")

    @field_validator("root_cause_id")
    @classmethod
    def validate_root_cause_id(cls, v: str, _info: ValidationInfo) -> str:
        """验证根因ID不能为空"""
        if not v or v.strip() == "":
            raise ValueError("根因ID不能为空")
        return v.strip()

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str, _info: ValidationInfo) -> str:
        """验证根因描述不能为空"""
        if not v or v.strip() == "":
            raise ValueError("根因描述不能为空")
        return v.strip()


class ClusterResult(BaseModel):
    """聚类结果模型"""

    labels: list[int] = Field(default_factory=list, description="聚类标签")
    n_clusters: int = Field(default=0, description="聚类数量")
    n_noise: int = Field(default=0, description="噪声点数量")
    clusters: list[ClusterInfo] = Field(default_factory=list, description="聚类信息")
    probabilities: list[float] | None = Field(default=None, description="聚类概率")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")

    def get_cluster(self, cluster_id: int) -> ClusterInfo | None:
        """获取指定ID的聚类信息"""
        for cluster in self.clusters:
            if cluster.cluster_id == cluster_id:
                return cluster
        return None

    def get_noise_indices(self) -> list[int]:
        """获取噪声点索引列表"""
        return [i for i, label in enumerate(self.labels) if label == -1]


class DimensionReductionResult(BaseModel):
    """降维结果模型"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    embeddings_2d: Any = Field(..., description="2D降维结果")
    embeddings_3d: Any | None = Field(default=None, description="3D降维结果")
    n_components: int = Field(default=2, description="降维维度")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")


# ---------------------------------------------------------------------------
# 规范知识库相关
# ---------------------------------------------------------------------------


class StandardRule(BaseModel):
    """规范规则条目"""

    id: str = Field(..., description="规则ID，如 JAVA-001")
    category: str = Field(..., description="规范类别，如 java_coding")
    subcategory: str = Field(default="", description="子类别，如 异常处理")
    title: str = Field(..., description="规则标题")
    content: str = Field(..., description="规则内容")
    level: str = Field(..., description="强制 / 推荐")
    code: str = Field(default="", description="规则编号，如 J000001")
    examples: list[str] = Field(default_factory=list, description="示例列表")

    @field_validator("examples", mode="before")
    @classmethod
    def coerce_examples(cls, v: Any) -> list[str]:
        """JSON 里 examples 可能是 dict，统一转为 list[str]"""
        if isinstance(v, dict):
            return [f"{k}: {val}" for k, val in v.items()]
        if v is None:
            return []
        # v 已经是 list 类型，直接返回
        return list(v) if isinstance(v, list) else [str(v)]


class StandardCategory(BaseModel):
    """规范类别"""

    id: str = Field(..., description="类别ID")
    name: str = Field(..., description="类别名称")
    description: str = Field(default="", description="类别描述")
    rules: list[StandardRule] = Field(default_factory=list, description="规则列表")


# 违规类型常量映射
VIOLATION_CATEGORIES: dict[str, str] = {
    "java_coding": "违反Java编码规范",
    "javascript_coding": "违反JavaScript编码规范",
    "cpp_coding": "违反C/C++编码规范",
    "python_coding": "违反Python编码规范",
    "golang_coding": "违反Golang编码规范",
    "database_design": "违反数据库设计规范",
    "sql_development": "违反SQL开发规范",
    "database_ops": "违反数据库运维规范",
    "security": "违反安全规范",
    "config_management": "违反配置管理规范",
    "delivery_process": "违反交付流程规范",
}


# ---------------------------------------------------------------------------
# 故障单 & 代码变更
# ---------------------------------------------------------------------------


class CodeChange(BaseModel):
    """代码变更（commit 级别）— V4 新增，区别于 V1 的文件级 CodeChange"""

    commit_id: str = Field(..., description="提交ID")
    author: str = Field(default="", description="作者")
    timestamp: datetime = Field(..., description="提交时间")
    message: str = Field(default="", description="提交信息")
    diff: str = Field(default="", description="代码diff内容")
    files_changed: list[str] = Field(default_factory=list, description="变更文件列表")
    branch: str = Field(default="", description="分支名")
    repository: str = Field(default="", description="仓库名")


class MediaContent(BaseModel):
    """多模态内容"""

    type: str = Field(..., description="内容类型：text / image")
    content: str = Field(..., description="文本内容或图片URL/base64")
    filename: str | None = Field(default=None, description="文件名")
    content_type: str | None = Field(default=None, description="MIME类型")


# ---------------------------------------------------------------------------
# 违规检测 & 根因验证
# ---------------------------------------------------------------------------


class ImprovementMeasure(BaseModel):
    """改进措施"""

    id: str = Field(..., description="措施ID")
    description: str = Field(..., description="改进措施描述")
    acceptance_criteria: str = Field(default="", description="验收标准")
    expected_impact: str = Field(default="", description="预期影响")
    priority: str = Field(default="medium", description="优先级：high / medium / low")


class ViolationDetection(BaseModel):
    """违规检测结果"""

    is_violation: bool = Field(..., description="是否违规")
    violation_type: str | None = Field(default=None, description="违规类型")
    violation_category: str | None = Field(default=None, description="违规类别")
    violated_rules: list[str] = Field(default_factory=list, description="违反的规则ID列表")
    evidence: str = Field(default="", description="违规证据")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度 0~1")
    relevant_standards: list[str] = Field(default_factory=list, description="相关规范引用")
    # 各命中规则的对齐详情（rule_label/description/evidence 等），用于
    # pipeline 生成逐规则对应的 violation 记录，避免 message 错位
    rule_details: list[dict[str, Any]] = Field(default_factory=list, description="命中规则对齐详情")


class RootCauseValidation(BaseModel):
    """根因可落地性验证结果"""

    root_cause: str = Field(..., description="根因描述")
    is_actionable: bool = Field(..., description="是否可落地")
    actionability_score: float = Field(default=0.0, ge=0.0, le=1.0, description="可落地性评分")
    improvement_measures: list[ImprovementMeasure] = Field(
        default_factory=list, description="改进措施列表"
    )
    validation_reason: str = Field(default="", description="验证理由")
    needs_reanalysis: bool = Field(default=False, description="是否需要重新分析")
    reanalysis_feedback: str = Field(default="", description="重新分析的反馈建议")


# ---------------------------------------------------------------------------
# LLM 分析结果
# ---------------------------------------------------------------------------


class LLMAnalysisResult(BaseModel):
    """LLM 深度分析结果（含违规检测 + 代码变更 + 根因验证）"""

    task_id: str = Field(..., description="故障单ID")
    violation_detection: ViolationDetection = Field(..., description="违规检测结果")
    root_cause: str = Field(default="", description="根因分析文本")
    root_cause_validation: RootCauseValidation = Field(..., description="根因验证结果")
    code_changes: list[CodeChange] = Field(default_factory=list, description="关联的代码变更")
    analysis_text: str = Field(default="", description="完整分析文本")
    timestamp: datetime = Field(default_factory=datetime.now, description="分析时间")


# ---------------------------------------------------------------------------
# 统计 & 推荐
# ---------------------------------------------------------------------------


class RootCauseStat(BaseModel):
    """根因统计"""

    root_cause: str = Field(..., description="根因描述")
    count: int = Field(default=0, ge=0, description="出现次数")
    percentage: float = Field(default=0.0, ge=0.0, le=100.0, description="占比百分比")
    related_tasks: list[str] = Field(default_factory=list, description="相关故障单ID")
    trend: str = Field(default="", description="趋势描述")


class ImprovementRecommendation(BaseModel):
    """改进推荐（针对高频根因）"""

    root_cause: str = Field(..., description="根因描述")
    frequency: int = Field(default=0, ge=0, description="出现频次")
    measures: list[ImprovementMeasure] = Field(default_factory=list, description="改进措施")
    priority: str = Field(default="medium", description="优先级")
    expected_impact: str = Field(default="", description="预期整体影响")


# ---------------------------------------------------------------------------
# 聚类结果 - 已迁移到 src/clustering/models.py
# 使用 ClusterResult 和 ClusterInfo 代替
# ---------------------------------------------------------------------------
