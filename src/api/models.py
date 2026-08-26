from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CodeChange(BaseModel):
    """文件级代码变更详情"""

    file_path: str = Field(..., description="文件路径")
    old_content: str = Field(default="", description="旧内容")
    new_content: str = Field(default="", description="新内容")
    change_type: str = Field(default="modify", description="变更类型: add/modify/delete")
    head_commit_id: str = Field(default="", description="修改前的CommitId")
    latest_commit_id: str = Field(default="", description="修改后的CommitId")


class CommitInfo(BaseModel):
    commit_id: str = Field(..., description="提交ID")
    message: str = Field(..., description="提交信息")
    author: str = Field(default="", description="作者")
    time: datetime = Field(..., description="提交时间")
    changes: list[str] = Field(default_factory=list, description="变更文件列表")
    diff: str = Field(default="", description="代码diff内容")
    branch: str = Field(default="", description="分支名")
    repository: str = Field(default="", description="仓库名")
    repo_url: str = Field(default="", description="仓库地址")
    base_branch: str = Field(default="", description="来源分支名")
    head_commit_id: str = Field(default="", description="特性分支初始CommitId")
    code_changes: list[CodeChange] = Field(default_factory=list, description="文件级代码变更详情")


class CodeReview(BaseModel):
    reviewer: str = Field(default="", description="评审人")
    time: datetime = Field(..., description="评审时间")
    comments: list[str] = Field(default_factory=list, description="评审意见")
    approved: bool = Field(default=False, description="是否通过")


class DevelopmentInfo(BaseModel):
    commits: list[CommitInfo] = Field(default_factory=list, description="代码提交列表")
    code_changes: list[CodeChange] = Field(default_factory=list, description="代码变更列表")
    code_reviews: list[CodeReview] = Field(default_factory=list, description="代码评审列表")


class TimelineEvent(BaseModel):
    time: datetime = Field(..., description="事件时间")
    action: str = Field(..., description="动作")
    actor: str = Field(default="", description="执行人")
    details: str = Field(default="", description="详情")


class ProductionInfo(BaseModel):
    incident_time: datetime = Field(..., description="故障发生时间")
    symptoms: str = Field(default="", description="故障现象")
    logs: list[str] = Field(default_factory=list, description="日志")
    stack_traces: list[str] = Field(default_factory=list, description="堆栈信息")
    resolution: str = Field(default="", description="解决方案")
    timeline: list[TimelineEvent] = Field(default_factory=list, description="处理时间线")


class RequirementInfo(BaseModel):
    requirement_id: str = Field(default="", description="需求ID")
    description: str = Field(default="", description="需求描述")
    review_records: list[str] = Field(default_factory=list, description="评审记录")
    documents: list[str] = Field(default_factory=list, description="相关文档")


class DesignInfo(BaseModel):
    design_document: str = Field(default="", description="设计文档")
    review_records: list[str] = Field(default_factory=list, description="评审记录")
    technical_solution: str = Field(default="", description="技术方案")


class TestingInfo(BaseModel):
    __test__ = False  # avoid pytest collecting this as a test class

    test_cases: list[str] = Field(default_factory=list, description="测试用例")
    test_results: list[str] = Field(default_factory=list, description="测试结果")
    defects: list[str] = Field(default_factory=list, description="缺陷记录")


class TaskInfo(BaseModel):
    task_id: int = Field(..., description="任务ID")
    title: str = Field(..., description="任务标题")
    description: str = Field(default="", description="任务描述")
    status: str = Field(default="", description="状态")
    priority: str = Field(default="medium", description="优先级")
    create_time: datetime = Field(..., description="创建时间")
    resolve_time: datetime | None = Field(default=None, description="解决时间")
    is_commit_code: str = Field(default="N", description="是否有代码变更: Y/N")

    requirement: RequirementInfo | None = Field(default=None, description="需求信息")
    design: DesignInfo | None = Field(default=None, description="设计信息")
    development: DevelopmentInfo | None = Field(default=None, description="开发信息")
    testing: TestingInfo | None = Field(default=None, description="测试信息")
    production: ProductionInfo | None = Field(default=None, description="生产信息")
    fault_analysis: dict[str, Any] | None = Field(
        default=None, description="故障复盘结论（研发/测试/管理环节分析）"
    )


class FetchResult(BaseModel):
    success: bool = Field(..., description="是否成功")
    task_id: int = Field(..., description="任务ID")
    task: TaskInfo | None = Field(default=None, description="任务信息")
    error: str = Field(default="", description="错误信息")
    cached: bool = Field(default=False, description="是否来自缓存")
