"""API 依赖注入"""

from typing import AsyncGenerator

from src.analyzer.pipeline import AnalysisPipeline, PipelineConfig
from src.config.manager import ConfigManager


def get_config_manager() -> ConfigManager:
    """获取配置管理器"""
    return ConfigManager()


async def get_pipeline(
    config_manager: ConfigManager,
    pipeline_config: PipelineConfig | None = None,
) -> AsyncGenerator[AnalysisPipeline, None]:
    """
    获取分析流水线

    Args:
        config_manager: 配置管理器
        pipeline_config: 流水线配置

    Yields:
        AnalysisPipeline: 分析流水线实例
    """
    pipeline = AnalysisPipeline(config_manager, pipeline_config)
    try:
        yield pipeline
    finally:
        await pipeline.close()
