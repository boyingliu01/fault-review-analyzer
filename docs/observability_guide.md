# 可观测性功能使用指南

本项目提供了完整的可观测性功能，包括结构化日志记录和性能指标收集，帮助您监控和分析系统运行状态。

## 结构化日志记录 (Logger)

### 基本使用

```python
from src.utils.logger import setup_logger, get_logger, get_correlation_id

# 设置日志记录器 - 使用 JSON 格式
setup_logger(level="INFO", json_format=True)

# 获取命名日志记录器
logger = get_logger("api")
correlation_id = get_correlation_id()

# 记录日志
logger.info(
    "Request received",
    task_id="12345",
    correlation_id=correlation_id,
    endpoint="/api/tasks",
    method="GET",
)
```

### 输出格式

**JSON 格式 (生产环境推荐):**
```json
{"timestamp":"2026-03-31T00:00:18.072171+08:00","level":"INFO","message":"Request received","name":"api","file":"example_observability.py:18","function":"example_logger","task_id":"12345","correlation_id":"abc-123","endpoint":"/api/tasks","method":"GET"}
```

**控制台格式 (开发环境):**
```
2026-03-31 00:00:18 | INFO     | api:example_logger:18 - Request received
```

### 高级功能

```python
from src.utils.logger import StructuredLogger

# 使用 StructuredLogger 简化调用
logger = StructuredLogger("analysis")
logger.info(
    "Clustering completed",
    cluster_count=5,
    task_count=100,
    correlation_id=correlation_id,
)

# 支持所有日志级别
logger.debug("Debug message")
logger.warning("Warning message")
logger.error("Error message")
logger.critical("Critical message")
logger.exception("Exception occurred")
```

### 配置选项

```python
setup_logger(
    level="DEBUG",              # 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    log_file="app.log",        # 日志文件路径 (可选)
    format_str="custom format", # 自定义格式 (可选)
    json_format=False,         # 是否使用 JSON 格式 (可选)
)
```

## 性能指标收集 (Metrics)

### 基本使用

```python
from src.utils.metrics import MetricsCollector

metrics = MetricsCollector(namespace="fault_analyzer")

# 计数器 - 记录 API 请求数
metrics.counter("api_requests_total", labels={"endpoint": "/tasks", "method": "GET"}).inc()

# 直方图 - 记录响应时间
metrics.histogram("api_response_duration", labels={"endpoint": "/tasks"}).observe(0.123)

# 仪表盘 - 记录活跃请求数
metrics.gauge("api_requests_active").inc()
```

### 指标类型

#### 1. Counter (计数器)
用于累计值，只增不减：
```python
# 记录 API 错误数
metrics.counter("api_errors_total", labels={"endpoint": "/tasks", "status_code": "500"}).inc()
```

#### 2. Histogram (直方图)
用于记录分布情况：
```python
# 记录查询时间
metrics.histogram("db_query_duration", labels={"table": "users"}).observe(0.042)
```

#### 3. Gauge (仪表盘)
用于记录当前值，可以增或减：
```python
# 记录队列长度
metrics.gauge("queue_length").set(15)
```

### 导出 Prometheus 格式

```python
prometheus_data = metrics.export_prometheus()
print(prometheus_data)

# 输出格式
# # TYPE fault_analyzer_api_requests_total counter
# fault_analyzer_api_requests_total{endpoint="/tasks",method="GET"} 2.0 1774886418073
# # TYPE fault_analyzer_api_response_duration histogram
# fault_analyzer_api_response_duration_bucket{le="0.1"} 1 1774886418073
# fault_analyzer_api_response_duration_sum 0.366 1774886418073
# fault_analyzer_api_response_duration_count 3 1774886418073
```

### 全局收集器

```python
from src.utils.metrics import get_metrics_collector

# 全局共享的收集器实例
metrics = get_metrics_collector(namespace="fault_analyzer")
```

## 使用场景示例

### API 服务监控

```python
from src.utils.logger import get_logger, get_correlation_id
from src.utils.metrics import get_metrics_collector

logger = get_logger("api")
metrics = get_metrics_collector()

async def handle_request(request):
    correlation_id = get_correlation_id()
    logger.info("Request received", correlation_id=correlation_id, **request.info)

    metrics.gauge("api_requests_active").inc()

    try:
        # 处理请求...
        duration = await process_request()

        metrics.counter("api_requests_total", labels={"endpoint": "/tasks", "method": "GET"}).inc()
        metrics.histogram("api_response_duration", labels={"endpoint": "/tasks"}).observe(duration)

        return {"success": True, "correlation_id": correlation_id}

    finally:
        metrics.gauge("api_requests_active").dec()
```

### 数据处理流程监控

```python
from src.utils.logger import StructuredLogger
from src.utils.metrics import MetricsCollector

logger = StructuredLogger("analysis")
metrics = MetricsCollector()

def run_clustering(tasks):
    logger.info("Clustering started", task_count=len(tasks))
    metrics.counter("clustering_runs_total").inc()

    try:
        start_time = time.time()

        # 执行聚类算法...

        duration = time.time() - start_time
        metrics.histogram("clustering_duration_seconds").observe(duration)

        logger.info(
            "Clustering completed",
            duration=duration,
            cluster_count=len(clusters)
        )

    except Exception as e:
        logger.error("Clustering failed", error=str(e))
        metrics.counter("clustering_errors_total").inc()
```

## 测试

运行可观测性功能的测试：

```bash
pytest tests/utils/test_logger.py -v
pytest tests/utils/test_metrics.py -v
```

或运行所有 utils 模块测试：

```bash
pytest tests/utils/ -v --cov=src/utils --cov-report=term
```

## 开发规范

- **日志记录原则：**
  - 使用有意义的消息
  - 包含 correlation_id 以便追踪请求
  - 避免在高频代码路径中记录过多调试日志

- **指标设计原则：**
  - 使用清晰且有描述性的名称
  - 合理使用标签来增加维度
  - 避免过度使用标签导致基数爆炸
  - 为关键操作添加指标，如 API 调用、数据库查询等
