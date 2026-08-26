"""聚类路由"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from src.analyzer.pipeline import AnalysisPipeline, PipelineConfig
from src.api.dependencies import get_config_manager
from src.api.server_models import (
    ClusterDetailResponse,
    ClusterInfo,
    ClusterListResponse,
    ClusterTaskInfo,
    ErrorResponse,
)
from src.config.manager import ConfigManager

router = APIRouter()

# 内存存储 - 实际应用中应使用数据库
_cluster_cache: dict[int, dict[str, Any]] = {}


@router.post(
    "/clusters/analyze",
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    tags=["Clusters"],
)
async def analyze_clusters(
    task_ids: list[int],
    config_manager: ConfigManager = Depends(get_config_manager),
) -> Any:
    """
    执行聚类分析并更新聚类缓存

    运行 HDBSCAN 聚类，并将结果写入内存缓存供 /clusters 查询。

    Args:
        task_ids: 待聚类的任务ID列表
        config_manager: 配置管理器

    Returns:
        dict: 聚类结果摘要
    """
    if not task_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "EmptyTaskIds",
                "message": "task_ids must not be empty",
                "detail": {},
            },
        )

    try:
        logger.info(f"Running clustering analysis for {len(task_ids)} tasks")

        pipeline_config = PipelineConfig(
            use_cache=True,
            use_llm=False,
            generate_labels=False,
            analyze_root_cause=False,
            check_rules=False,
            generate_report=False,
        )

        async with AnalysisPipeline(config_manager, pipeline_config) as pipeline:
            cluster_result = await pipeline.run_clustering(task_ids)

        if "error" in cluster_result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "ClusteringFailed",
                    "message": cluster_result["error"],
                    "detail": {},
                },
            )

        update_cluster_cache(cluster_result)

        return {
            "cluster_count": cluster_result.get("cluster_count", 0),
            "noise_count": cluster_result.get("noise_count", 0),
            "total_tasks": cluster_result.get("total_found", 0),
            "clustering_mode": cluster_result.get("clustering_mode", "text_only"),
        }

    except HTTPException:
        raise
    except Exception as error:
        logger.bind(exception_type=type(error).__name__).error("Clustering analysis failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ClusteringFailed",
                "message": "Clustering failed due to an internal error",
                "detail": {},
            },
        ) from error


@router.get(
    "/clusters",
    response_model=ClusterListResponse,
    responses={
        500: {"model": ErrorResponse},
    },
    tags=["Clusters"],
)
async def get_clusters(
    config_manager: ConfigManager = Depends(get_config_manager),
) -> Any:
    """
    获取聚类列表

    Returns:
        ClusterListResponse: 聚类列表
    """
    try:
        logger.info("Fetching clusters")

        # 检查缓存
        if _cluster_cache:
            clusters = []
            total_tasks = 0
            noise_count = 0

            for cluster_id, data in _cluster_cache.items():
                if cluster_id == -1:
                    noise_count = data.get("size", 0)
                else:
                    clusters.append(
                        ClusterInfo(
                            cluster_id=cluster_id,
                            size=data.get("size", 0),
                            label=data.get("label", ""),
                            keywords=data.get("keywords", []),
                            metadata=data.get("metadata", {}),
                        )
                    )
                    total_tasks += data.get("size", 0)

            total_tasks += noise_count

            return ClusterListResponse(
                total_clusters=len(clusters),
                total_tasks=total_tasks,
                noise_count=noise_count,
                clusters=clusters,
            )

        # 如果没有缓存，返回空结果
        return ClusterListResponse(
            total_clusters=0,
            total_tasks=0,
            noise_count=0,
            clusters=[],
        )

    except Exception as error:
        logger.bind(exception_type=type(error).__name__).error("Cluster list fetch failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ClustersFetchFailed",
                "message": "Failed to fetch clusters due to an internal error",
                "detail": {},
            },
        ) from error


@router.get(
    "/clusters/{cluster_id}",
    response_model=ClusterDetailResponse,
    responses={
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    tags=["Clusters"],
)
async def get_cluster_detail(
    cluster_id: int,
    config_manager: ConfigManager = Depends(get_config_manager),
) -> Any:
    """
    获取聚类详情

    Args:
        cluster_id: 聚类ID
        config_manager: 配置管理器

    Returns:
        ClusterDetailResponse: 聚类详情
    """
    try:
        logger.info(f"Fetching cluster detail for cluster: {cluster_id}")

        # 检查缓存
        if not _cluster_cache or cluster_id not in _cluster_cache:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "ClusterNotFound",
                    "message": f"Cluster {cluster_id} not found",
                    "detail": {},
                },
            )

        cluster_data = _cluster_cache[cluster_id]

        # 转换任务信息
        tasks = []
        for task_data in cluster_data.get("tasks", []):
            tasks.append(
                ClusterTaskInfo(
                    task_id=str(task_data.get("task_id", "")),
                    title=task_data.get("title", ""),
                    description=task_data.get("description", ""),
                    similarity_score=task_data.get("similarity_score", 0.0),
                )
            )

        return ClusterDetailResponse(
            cluster_id=cluster_id,
            size=cluster_data.get("size", 0),
            label=cluster_data.get("label", ""),
            description=cluster_data.get("description", ""),
            keywords=cluster_data.get("keywords", []),
            tasks=tasks,
            metadata=cluster_data.get("metadata", {}),
        )

    except HTTPException:
        raise
    except Exception as error:
        logger.bind(cluster_id=cluster_id, exception_type=type(error).__name__).error(
            "Cluster detail fetch failed"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ClusterDetailFetchFailed",
                "message": "Failed to fetch cluster detail due to an internal error",
                "detail": {},
            },
        ) from error


def update_cluster_cache(cluster_results: dict[str, Any]) -> None:
    """
    更新聚类缓存

    Args:
        cluster_results: 聚类结果
    """
    # 按 cluster_id 分组任务
    clusters: dict[int, dict[str, Any]] = {}

    for task in cluster_results.get("tasks", []):
        cluster_id = task.get("cluster_id", -1)
        if cluster_id not in clusters:
            clusters[cluster_id] = {
                "size": 0,
                "tasks": [],
                "label": "",
                "keywords": [],
                "metadata": {},
            }
        clusters[cluster_id]["size"] += 1
        clusters[cluster_id]["tasks"].append(task)

    # 更新全局缓存
    global _cluster_cache
    _cluster_cache = clusters
