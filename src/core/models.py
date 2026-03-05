"""V4 核心数据模型 — 供所有 V4 模块共享使用。

命名空间独立于 src/api/models.py（V1）。
V4 CodeChange 是 commit 级别（含 diff），与 V1 文件级 CodeChange 不同。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


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
# 向量化结果
# ---------------------------------------------------------------------------

class EmbeddingResult(BaseModel):
    """向量化结果（多模态增强版，统一 2048 维）"""

    task_id: str = Field(..., description="故障单ID")
    embedding: list[float] = Field(..., description="2048维向量")
    text: str = Field(default="", description="用于向量化的文本")
    media_type: str = Field(default="text", description="媒体类型：text / image / mixed")
    metadata: dict[str, Any] = Field(default_factory=dict, description="额外元数据")


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
# 聚类结果
# ---------------------------------------------------------------------------

class ClusteringResult(BaseModel):
    """聚类分析结果"""

    labels: list[int] = Field(..., description="每个样本的聚类标签，-1 表示噪声")
    n_clusters: int = Field(default=0, ge=0, description="有效聚类数量")
    n_noise: int = Field(default=0, ge=0, description="噪声点数量")
    silhouette_score: float = Field(default=0.0, description="轮廓系数（-1~1）")
    algorithm: str = Field(default="hdbscan", description="使用的聚类算法")
    parameters: dict[str, Any] = Field(default_factory=dict, description="算法参数")
