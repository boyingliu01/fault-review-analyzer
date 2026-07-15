"""结构化日志记录模块"""

import json
import sys
from pathlib import Path
from typing import Any

from loguru import logger


def _json_serializer(record: dict[str, Any]) -> str:
    """自定义 JSON 序列化器，输出简化的日志格式"""
    log_data = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "name": record["extra"].get("name"),
        "file": f"{record['file'].name}:{record['line']}",
        "function": record["function"],
    }

    # 添加 extra 字段中的其他数据
    for key, value in record["extra"].items():
        if key not in log_data:
            log_data[key] = value

    # 如果有异常，添加异常信息
    if record["exception"] is not None:
        log_data["exception"] = str(record["exception"])

    return json.dumps(log_data, ensure_ascii=False)


def setup_logger(
    level: str = "INFO",
    log_file: str | None = None,
    format_str: str | None = None,
    json_format: bool = False,
) -> None:
    """
    设置日志记录器

    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 日志文件路径 (可选)
        format_str: 日志格式字符串 (可选)
        json_format: 是否使用 JSON 格式输出 (可选)
    """
    logger.remove()

    if json_format:
        # JSON 格式输出 - 使用自定义序列化器
        def json_sink(message):
            record = message.record
            print(_json_serializer(record), file=sys.stderr)

        logger.add(
            json_sink,
            level=level,
            colorize=False,
        )
    else:
        # 控制台格式输出
        if format_str is None:
            format_str = (
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                "<level>{message}</level>"
            )

        logger.add(
            sys.stderr,
            format=format_str,
            level=level,
            colorize=True,
        )

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        if json_format:
            # JSON 文件格式
            def json_file_sink(message):
                record = message.record
                with log_path.open("a", encoding="utf-8") as f:
                    f.write(_json_serializer(record) + "\n")

            logger.add(
                json_file_sink,
                level=level,
            )
        else:
            # 普通文件格式
            logger.add(
                log_file,
                format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
                level=level,
                rotation="10 MB",
                retention="7 days",
                encoding="utf-8",
            )


def get_logger(name: str = __name__) -> Any:
    """
    获取命名的日志记录器

    Args:
        name: 日志记录器名称

    Returns:
        配置好的 loguru 日志记录器
    """
    return logger.bind(name=name)


def get_correlation_id() -> str:
    """
    生成一个简单的 correlation_id (用于请求追踪)

    Returns:
        生成的 correlation_id
    """
    import uuid

    return str(uuid.uuid4())


class StructuredLogger:
    """结构化日志记录器包装类，提供更简洁的接口。

    支持 correlation_id 绑定和上下文结构化字段，用于全链路追踪。

    Usage:
        log = StructuredLogger("my.module")
        bound = log.with_correlation()  # auto-generates correlation_id
        bound.info("processing", task_id=123)

        # Or with explicit correlation_id:
        bound = log.with_correlation("my-cid").context(task_id=123)
        bound.info("processing")
    """

    def __init__(
        self,
        name: str = __name__,
        correlation_id: str | None = None,
        extra_context: dict[str, Any] | None = None,
    ) -> None:
        self._name = name
        self._correlation_id = correlation_id
        self._extra_context: dict[str, Any] = extra_context or {}
        self.logger = get_logger(name)
        if correlation_id:
            self.logger = self.logger.bind(correlation_id=correlation_id)
        if self._extra_context:
            self.logger = self.logger.bind(**self._extra_context)

    def with_correlation(self, correlation_id: str | None = None) -> "StructuredLogger":
        """Return a new StructuredLogger bound to a correlation_id.

        Args:
            correlation_id: Explicit correlation ID. Auto-generated if None.

        Returns:
            New StructuredLogger instance with correlation_id bound.
        """
        cid = correlation_id or get_correlation_id()
        return StructuredLogger(
            name=self._name,
            correlation_id=cid,
            extra_context=self._extra_context,
        )

    def context(self, **kwargs: Any) -> "StructuredLogger":
        """Return a new StructuredLogger with additional context fields.

        Args:
            **kwargs: Key-value pairs to include in log context.

        Returns:
            New StructuredLogger instance with extra context bound.
        """
        merged = {**self._extra_context, **kwargs}
        return StructuredLogger(
            name=self._name,
            correlation_id=self._correlation_id,
            extra_context=merged,
        )

    def debug(self, message: str, **kwargs: Any) -> None:
        """Debug 级别日志"""
        self.logger.debug(message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Info 级别日志"""
        self.logger.info(message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Warning 级别日志"""
        self.logger.warning(message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Error 级别日志"""
        self.logger.error(message, **kwargs)

    def critical(self, message: str, **kwargs: Any) -> None:
        """Critical 级别日志"""
        self.logger.critical(message, **kwargs)

    def exception(self, message: str, **kwargs: Any) -> None:
        """Exception 级别日志"""
        self.logger.exception(message, **kwargs)
