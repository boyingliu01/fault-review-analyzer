"""健康检查路由"""

from fastapi import APIRouter

from src.api.server_models import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check() -> HealthResponse:
    """
    健康检查接口

    返回服务状态信息，用于监控和负载均衡。

    Returns:
        HealthResponse: 健康检查响应
    """
    return HealthResponse(
        status="healthy",
    )
