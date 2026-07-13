"""可观测性功能使用示例"""

from src.utils.logger import StructuredLogger, get_correlation_id, get_logger, setup_logger
from src.utils.metrics import MetricsCollector, get_metrics_collector


def example_logger():
    """结构化日志使用示例"""
    print("=== 结构化日志使用示例 ===")

    # 设置日志记录器，使用 JSON 格式
    setup_logger(level="INFO", json_format=True)

    # 方式1: 使用 get_logger
    logger = get_logger("api")
    correlation_id = get_correlation_id()

    logger.info(
        "Request received",
        task_id="12345",
        correlation_id=correlation_id,
        endpoint="/api/tasks",
        method="GET",
    )

    # 方式2: 使用 StructuredLogger
    structured_logger = StructuredLogger("analysis")
    structured_logger.info(
        "Clustering completed",
        cluster_count=5,
        task_count=100,
        correlation_id=correlation_id,
    )


def example_metrics():
    """性能指标使用示例"""
    print("\n=== 性能指标使用示例 ===")

    # 获取指标收集器
    metrics = MetricsCollector(namespace="fault_analyzer")

    # 模拟 API 请求处理
    # 1. 活跃请求数
    metrics.gauge("api_requests_active").inc()

    # 2. API 调用计数
    metrics.counter("api_requests_total", labels={"endpoint": "/tasks", "method": "GET"}).inc()
    metrics.counter("api_requests_total", labels={"endpoint": "/tasks", "method": "GET"}).inc()

    # 3. 响应时间直方图
    metrics.histogram("api_response_duration", labels={"endpoint": "/tasks"}).observe(0.123)
    metrics.histogram("api_response_duration", labels={"endpoint": "/tasks"}).observe(0.087)
    metrics.histogram("api_response_duration", labels={"endpoint": "/tasks"}).observe(0.156)

    # 减少活跃请求数
    metrics.gauge("api_requests_active").dec()

    # 导出 Prometheus 格式
    prometheus_data = metrics.export_prometheus()
    print("Prometheus 格式指标:")
    print("-" * 60)
    print(prometheus_data)
    print("-" * 60)


def example_global_metrics():
    """全局指标收集器示例"""
    print("\n=== 全局指标收集器示例 ===")

    # 使用全局指标收集器
    metrics = get_metrics_collector()

    # 记录一些指标
    metrics.counter("analysis_runs_total").inc()
    metrics.histogram("analysis_duration_seconds").observe(2.345)

    # 导出
    print(get_metrics_collector().export_prometheus())


if __name__ == "__main__":
    example_logger()
    example_metrics()
    example_global_metrics()
