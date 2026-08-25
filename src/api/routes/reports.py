"""报告路由"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger

from src.analyzer.pipeline import AnalysisPipeline, PipelineConfig
from src.api.dependencies import get_config_manager
from src.api.server_models import ErrorResponse, ReportResponse
from src.config.manager import ConfigManager
from src.report.generator import ReportFormat

router = APIRouter()


@router.get(
    "/reports/{task_id}",
    response_model=ReportResponse,
    responses={
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    tags=["Reports"],
)
async def get_report(
    task_id: str,
    format: str = Query("html", description="报告格式: html/markdown/json"),
    use_cache: bool = Query(True, description="是否使用缓存"),
    config_manager: ConfigManager = Depends(get_config_manager),
) -> Any:
    """
    获取任务分析报告

    Args:
        task_id: 任务ID
        format: 报告格式
        use_cache: 是否使用缓存
        config_manager: 配置管理器

    Returns:
        ReportResponse: 报告响应
    """
    try:
        logger.info(f"Fetching report for task: {task_id}")

        # 验证格式
        valid_formats = ["html", "markdown", "json"]
        if format not in valid_formats:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "InvalidFormat",
                    "message": f"Invalid format. Supported formats: {valid_formats}",
                    "detail": {},
                },
            )

        # 创建流水线配置
        pipeline_config = PipelineConfig(
            use_cache=use_cache,
            use_llm=False,  # 生成报告不需要 LLM 重新分析
            generate_labels=False,
            analyze_root_cause=False,
            analyze_root_cause_deep=False,
            check_rules=False,
            match_standards=False,
            generate_report=True,
            report_format=ReportFormat(format),
        )

        # 执行分析获取报告
        async with AnalysisPipeline(config_manager, pipeline_config) as pipeline:
            result = await pipeline.run_single(int(task_id))

        if result.error:
            if "not found" in result.error.lower():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "TaskNotFound",
                        "message": f"Task {task_id} not found",
                        "detail": {},
                    },
                )
            logger.error(
                f"Report generation failed for task {task_id}: error_type=ReportGenerationFailed"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "ReportGenerationFailed",
                    "message": "An internal error occurred",
                    "detail": {},
                },
            )

        report_content = result.report

        return ReportResponse(
            task_id=task_id,
            report_format=format,
            content=report_content,
        )

    except HTTPException:
        raise
    except ValueError as e:
        # task_id 不是有效的整数
        logger.error(f"Invalid task ID {task_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "InvalidTaskId",
                "message": "Invalid task ID format",
                "detail": {},
            },
        ) from e
    except Exception as e:
        logger.error(f"Error fetching report for task {task_id}: exception_type={type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ReportFetchFailed",
                "message": "An internal error occurred",
                "detail": {},
            },
        ) from e
