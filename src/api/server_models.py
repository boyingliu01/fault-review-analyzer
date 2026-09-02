"""API 服务数据模型"""

from datetime import datetime
from typing import Any, Final

from pydantic import BaseModel, Field, field_validator

# 批量分析单次请求上限（G15: 从 50 提升到 1000，满足"支持 1000+ 故障单批量分析"）。
# 实际并发由 pipeline 的 max_concurrency（默认 10）约束，避免压垮下游 API。
MAX_BATCH_TASK_IDS: Final = 1000


class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str = Field(..., description="服务状态")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    version: str = Field(default="0.1.0", description="服务版本")


class AnalyzeOptions(BaseModel):
    """分析选项"""

    include_code: bool = Field(default=True, description="是否包含代码变更")
    include_analysis: bool = Field(default=True, description="是否包含 LLM 分析")
    use_cache: bool = Field(default=True, description="是否使用缓存")
    use_llm: bool = Field(default=False, description="是否使用 LLM 分析")
    generate_labels: bool = Field(default=True, description="是否生成标签")
    analyze_root_cause: bool = Field(default=True, description="是否分析根因")
    analyze_root_cause_deep: bool = Field(default=False, description="是否进行深度根因分析")
    check_rules: bool = Field(default=True, description="是否检查规则")
    generate_report: bool = Field(default=True, description="是否生成报告")


class SingleAnalyzeRequest(BaseModel):
    """单个任务分析请求"""

    task_id: str | int = Field(..., description="任务ID")
    options: AnalyzeOptions = Field(default_factory=AnalyzeOptions, description="分析选项")


class BatchAnalyzeRequest(BaseModel):
    """批量分析请求"""

    task_ids: list[int] = Field(..., description="任务ID列表", min_length=1)
    options: AnalyzeOptions = Field(default_factory=AnalyzeOptions, description="分析选项")

    @field_validator("task_ids")
    @classmethod
    def deduplicate_task_ids(cls, task_ids: list[int]) -> list[int]:
        """Preserve the first occurrence of at most 50 unique task IDs."""
        unique_task_ids = list(dict.fromkeys(task_ids))
        if len(unique_task_ids) > MAX_BATCH_TASK_IDS:
            message = f"batch requests support at most {MAX_BATCH_TASK_IDS} unique task IDs"
            raise ValueError(message)
        return unique_task_ids


class LabelInfo(BaseModel):
    """标签信息"""

    name: str = Field(..., description="标签名称")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度")
    category: str = Field(default="", description="标签类别")
    description: str = Field(default="", description="标签描述")


class RootCauseInfo(BaseModel):
    """根因信息（不含置信度：LLM 自评未校准，已按用户决策移除）"""

    cause_type: str = Field(..., description="根因类型")
    description: str = Field(..., description="根因描述")
    evidence: list[str] = Field(default_factory=list, description="证据列表")


class ViolationInfo(BaseModel):
    """违规信息"""

    rule_id: str = Field(..., description="规则ID")
    rule_name: str = Field(..., description="规则名称")
    severity: str = Field(..., description="严重程度")
    message: str = Field(..., description="违规消息")
    evidence: str = Field(default="", description="违规证据")


class SingleAnalyzeResponse(BaseModel):
    """单个任务分析响应"""

    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="分析状态: pending/completed/failed")
    error: str = Field(default="", description="错误信息")

    # 分析结果
    labels: list[dict[str, Any]] = Field(default_factory=list, description="标签列表")
    root_causes: list[dict[str, Any]] = Field(default_factory=list, description="根因列表")
    deep_root_causes: dict[str, Any] = Field(default_factory=dict, description="深度根因分析结果")
    violations: list[dict[str, Any]] = Field(default_factory=list, description="违规列表")
    suggestions: list[str] = Field(default_factory=list, description="改进建议")
    report: str = Field(default="", description="分析报告")

    # 元数据
    analysis_time: float = Field(default=0.0, description="分析耗时(秒)")
    cached: bool = Field(default=False, description="是否来自缓存")


class BatchAnalyzeResponse(BaseModel):
    """批量分析响应"""

    total_requested: int = Field(..., description="请求的任务总数")
    total_completed: int = Field(..., description="完成的任务数")
    total_failed: int = Field(..., description="失败的任务数")
    results: list[SingleAnalyzeResponse] = Field(..., description="分析结果列表")
    analysis_time: float = Field(default=0.0, description="总分析耗时(秒)")


class ClusterInfo(BaseModel):
    """聚类信息"""

    cluster_id: int = Field(..., description="聚类ID")
    size: int = Field(default=0, description="聚类大小")
    label: str = Field(default="", description="聚类标签")
    keywords: list[str] = Field(default_factory=list, description="关键词列表")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")


class ClusterListResponse(BaseModel):
    """聚类列表响应"""

    total_clusters: int = Field(..., description="聚类总数")
    total_tasks: int = Field(..., description="任务总数")
    noise_count: int = Field(default=0, description="噪声点数量")
    clusters: list[ClusterInfo] = Field(default_factory=list, description="聚类列表")


class ClusterTaskInfo(BaseModel):
    """聚类中的任务信息"""

    task_id: str = Field(..., description="任务ID")
    title: str = Field(default="", description="任务标题")
    description: str = Field(default="", description="任务描述")
    similarity_score: float = Field(default=0.0, ge=0.0, le=1.0, description="相似度分数")


class ClusterDetailResponse(BaseModel):
    """聚类详情响应"""

    cluster_id: int = Field(..., description="聚类ID")
    size: int = Field(default=0, description="聚类大小")
    label: str = Field(default="", description="聚类标签")
    description: str = Field(default="", description="聚类描述")
    keywords: list[str] = Field(default_factory=list, description="关键词列表")
    tasks: list[ClusterTaskInfo] = Field(default_factory=list, description="任务列表")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")


class ReportResponse(BaseModel):
    """报告响应"""

    task_id: str = Field(..., description="任务ID")
    report_format: str = Field(default="html", description="报告格式: html/markdown/json")
    content: str = Field(..., description="报告内容")
    generated_at: datetime = Field(default_factory=datetime.now, description="生成时间")


class ErrorResponse(BaseModel):
    """错误响应"""

    error: str = Field(..., description="错误类型")
    message: str = Field(..., description="错误消息")
    detail: dict[str, Any] = Field(default_factory=dict, description="详细信息")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
