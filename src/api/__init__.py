"""API模块 - 包含客户端和服务器"""

from src.api.client import APIClient
from src.api.exceptions import (
    APIConnectionError,
    APIError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ServerError,
)
from src.api.models import (
    CodeChange,
    CodeReview,
    CommitInfo,
    DesignInfo,
    DevelopmentInfo,
    FetchResult,
    ProductionInfo,
    RequirementInfo,
    TaskInfo,
    TestingInfo,
    TimelineEvent,
)

# API 服务器相关
try:
    from src.api.server import create_app
    from src.api.server_models import (
        AnalyzeOptions,
        BatchAnalyzeRequest,
        BatchAnalyzeResponse,
        ClusterDetailResponse,
        ClusterInfo,
        ClusterListResponse,
        ErrorResponse,
        HealthResponse,
        LabelInfo,
        ReportResponse,
        RootCauseInfo,
        SingleAnalyzeRequest,
        SingleAnalyzeResponse,
        ViolationInfo,
    )

    __api_server_all__ = [
        "create_app",
        "HealthResponse",
        "SingleAnalyzeRequest",
        "SingleAnalyzeResponse",
        "BatchAnalyzeRequest",
        "BatchAnalyzeResponse",
        "AnalyzeOptions",
        "LabelInfo",
        "RootCauseInfo",
        "ViolationInfo",
        "ClusterInfo",
        "ClusterListResponse",
        "ClusterDetailResponse",
        "ReportResponse",
        "ErrorResponse",
    ]
except ImportError:
    # FastAPI 相关依赖可能未安装
    __api_server_all__ = []

__all__ = [
    "APIClient",
    "APIError",
    "AuthenticationError",
    "APIConnectionError",
    "NotFoundError",
    "RateLimitError",
    "ServerError",
    "TaskInfo",
    "CommitInfo",
    "CodeChange",
    "CodeReview",
    "DevelopmentInfo",
    "ProductionInfo",
    "RequirementInfo",
    "DesignInfo",
    "TestingInfo",
    "TimelineEvent",
    "FetchResult",
] + __api_server_all__
