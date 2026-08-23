"""分析路由"""

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from src.analyzer.pipeline import AnalysisPipeline, PipelineConfig, PipelineResult
from src.api.dependencies import get_config_manager
from src.api.server_models import (
    BatchAnalyzeRequest,
    BatchAnalyzeResponse,
    ErrorResponse,
    SingleAnalyzeRequest,
    SingleAnalyzeResponse,
)
from src.config.manager import ConfigManager

router = APIRouter()


def convert_pipeline_result_to_response(
    task_id: str, pipeline_result: PipelineResult
) -> SingleAnalyzeResponse:
    """
    将 PipelineResult 转换为 API 响应格式

    Args:
        task_id: 任务ID
        pipeline_result: 流水线结果

    Returns:
        SingleAnalyzeResponse: API 响应
    """
    if pipeline_result.error:
        return SingleAnalyzeResponse(
            task_id=task_id,
            status="failed",
            error=pipeline_result.error,
        )

    return SingleAnalyzeResponse(
        task_id=task_id,
        status="completed",
        error="",
        labels=pipeline_result.labels or [],
        root_causes=pipeline_result.root_causes or [],
        deep_root_causes=pipeline_result.deep_root_causes or {},
        violations=pipeline_result.violations or [],
        suggestions=[],  # 目前没有单独的建议字段
        report=pipeline_result.report,
        analysis_time=0.0,  # 暂时不计算时间
        cached=True,
    )


@router.post(
    "/analyze",
    response_model=SingleAnalyzeResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    tags=["Analysis"],
)
async def analyze_task(
    request: SingleAnalyzeRequest,
    config_manager: ConfigManager = Depends(get_config_manager),
) -> Any:
    """
    分析单个任务

    Args:
        request: 分析请求
        config_manager: 配置管理器

    Returns:
        SingleAnalyzeResponse: 分析结果
    """
    task_id = str(request.task_id)

    try:
        logger.info(f"Starting analysis for task: {task_id}")
        start_time = time.time()

        # 创建流水线配置
        pipeline_config = PipelineConfig(
            use_cache=request.options.use_cache,
            use_llm=request.options.use_llm,
            generate_labels=request.options.generate_labels,
            analyze_root_cause=request.options.analyze_root_cause,
            analyze_root_cause_deep=request.options.analyze_root_cause_deep,
            check_rules=request.options.check_rules,
            generate_report=request.options.generate_report,
        )

        # 执行分析
        async with AnalysisPipeline(config_manager, pipeline_config) as pipeline:
            result = await pipeline.run_single(int(task_id))

        analysis_time = time.time() - start_time
        logger.info(f"Analysis completed for task {task_id} in {analysis_time:.2f}s")

        response = convert_pipeline_result_to_response(task_id, result)
        response.analysis_time = analysis_time

        return response

    except Exception as error:
        logger.bind(task_id=task_id, exception_type=type(error).__name__).error(
            "Task analysis failed"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "AnalysisFailed",
                "message": "Analysis failed due to an internal error",
                "detail": {},
            },
        ) from error


@router.post(
    "/analyze/batch",
    response_model=BatchAnalyzeResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    tags=["Analysis"],
)
async def analyze_batch(
    request: BatchAnalyzeRequest,
    config_manager: ConfigManager = Depends(get_config_manager),
) -> Any:
    """
    批量分析任务

    Args:
        request: 批量分析请求
        config_manager: 配置管理器

    Returns:
        BatchAnalyzeResponse: 分析结果
    """
    task_ids = request.task_ids
    logger.info(f"Starting batch analysis for tasks: {task_ids}")
    start_time = time.time()

    try:
        # 创建流水线配置
        pipeline_config = PipelineConfig(
            use_cache=request.options.use_cache,
            use_llm=request.options.use_llm,
            generate_labels=request.options.generate_labels,
            analyze_root_cause=request.options.analyze_root_cause,
            analyze_root_cause_deep=request.options.analyze_root_cause_deep,
            check_rules=request.options.check_rules,
            generate_report=request.options.generate_report,
        )

        # 执行批量分析
        async with AnalysisPipeline(config_manager, pipeline_config) as pipeline:
            results = await pipeline.run_batch(task_ids)

        analysis_time = time.time() - start_time
        logger.info(f"Batch analysis completed for {len(results)} tasks in {analysis_time:.2f}s")

        # 转换结果格式
        responses = []
        completed = 0
        failed = 0

        for i, result in enumerate(results):
            task_id = str(task_ids[i])
            response = convert_pipeline_result_to_response(task_id, result)
            responses.append(response)
            if response.status == "completed":
                completed += 1
            else:
                failed += 1

        return BatchAnalyzeResponse(
            total_requested=len(task_ids),
            total_completed=completed,
            total_failed=failed,
            results=responses,
            analysis_time=analysis_time,
        )

    except Exception as error:
        logger.bind(task_ids=task_ids, exception_type=type(error).__name__).error(
            "Batch analysis failed"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "BatchAnalysisFailed",
                "message": "Batch analysis failed due to an internal error",
                "detail": {},
            },
        ) from error
