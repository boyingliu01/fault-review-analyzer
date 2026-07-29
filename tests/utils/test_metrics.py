"""性能指标收集器测试"""

from src.utils.metrics import (
    Counter,
    Gauge,
    Histogram,
    HistogramData,
    MetricsCollector,
    MetricValue,
    get_metrics_collector,
)


class TestMetricValue:
    """测试 MetricValue 数据类"""

    def test_metric_value_defaults(self):
        """测试 MetricValue 默认值"""
        mv = MetricValue()
        assert mv.labels == {}
        assert mv.value == 0.0

    def test_metric_value_custom(self):
        """测试 MetricValue 自定义值"""
        mv = MetricValue(labels={"endpoint": "/tasks"}, value=42.0)
        assert mv.labels == {"endpoint": "/tasks"}
        assert mv.value == 42.0


class TestHistogramData:
    """测试 HistogramData 数据类"""

    def test_histogram_data_defaults(self):
        """测试 HistogramData 默认值"""
        data = HistogramData()
        assert data.count == 0
        assert data.sum == 0.0
        assert data.min == float("inf")
        assert data.max == -float("inf")
        assert data.buckets == {}

    def test_histogram_data_observe_single(self):
        """测试观察单个值"""
        data = HistogramData()
        data.observe(0.123)

        assert data.count == 1
        assert data.sum == 0.123
        assert data.min == 0.123
        assert data.max == 0.123

    def test_histogram_data_observe_multiple(self):
        """测试观察多个值"""
        data = HistogramData()
        data.observe(0.1)
        data.observe(0.2)
        data.observe(0.3)

        assert data.count == 3
        assert abs(data.sum - 0.6) < 1e-9
        assert data.min == 0.1
        assert data.max == 0.3

    def test_histogram_data_mean(self):
        """测试平均值计算"""
        data = HistogramData()
        assert data.mean() == 0.0

        data.observe(1.0)
        data.observe(2.0)
        data.observe(3.0)
        assert data.mean() == 2.0

    def test_histogram_data_buckets(self):
        """测试分桶"""
        data = HistogramData()
        data.observe(0.05)
        data.observe(0.1)
        data.observe(0.5)
        data.observe(1.5)

        assert 0.05 in data.buckets
        assert 0.1 in data.buckets
        assert 0.5 in data.buckets
        assert 1.0 in data.buckets
        assert 2.5 in data.buckets
        assert float("inf") in data.buckets


class TestCounter:
    """测试 Counter 指标"""

    def test_counter_inc(self):
        """测试计数器递增"""
        counter = Counter("test_counter")
        assert counter.get() == 0.0

        counter.inc()
        assert counter.get() == 1.0

        counter.inc(2.5)
        assert counter.get() == 3.5

    def test_counter_with_labels(self):
        """测试带标签的计数器"""
        counter = Counter("test_counter")
        counter.inc(1.0, labels={"endpoint": "/tasks", "method": "GET"})
        counter.inc(2.0, labels={"endpoint": "/tasks", "method": "POST"})

        assert counter.get({"endpoint": "/tasks", "method": "GET"}) == 1.0
        assert counter.get({"endpoint": "/tasks", "method": "POST"}) == 2.0

    def test_counter_with_base_labels(self):
        """测试带基础标签的计数器"""
        counter = Counter("test_counter", labels={"service": "api"})
        counter.inc(1.0, labels={"endpoint": "/tasks"})

        assert counter.get({"endpoint": "/tasks"}) == 1.0

    def test_counter_collect(self):
        """测试收集计数器值"""
        counter = Counter("test_counter")
        counter.inc(1.0, labels={"endpoint": "/a"})
        counter.inc(2.0, labels={"endpoint": "/b"})

        values = list(counter.collect())
        assert len(values) == 2

        values_dict = {tuple(mv.labels.items()): mv.value for mv in values}
        assert values_dict[(("endpoint", "/a"),)] == 1.0
        assert values_dict[(("endpoint", "/b"),)] == 2.0


class TestGauge:
    """测试 Gauge 指标"""

    def test_gauge_set(self):
        """测试仪表盘设置"""
        gauge = Gauge("test_gauge")
        assert gauge.get() == 0.0

        gauge.set(42.0)
        assert gauge.get() == 42.0

    def test_gauge_inc_dec(self):
        """测试仪表盘增减"""
        gauge = Gauge("test_gauge")
        gauge.set(10.0)

        gauge.inc()
        assert gauge.get() == 11.0

        gauge.inc(2.5)
        assert gauge.get() == 13.5

        gauge.dec()
        assert gauge.get() == 12.5

        gauge.dec(3.5)
        assert gauge.get() == 9.0

    def test_gauge_with_labels(self):
        """测试带标签的仪表盘"""
        gauge = Gauge("test_gauge")
        gauge.set(5.0, labels={"queue": "high"})
        gauge.set(10.0, labels={"queue": "low"})

        assert gauge.get({"queue": "high"}) == 5.0
        assert gauge.get({"queue": "low"}) == 10.0

    def test_gauge_collect(self):
        """测试收集仪表盘值"""
        gauge = Gauge("test_gauge")
        gauge.set(5.0, labels={"queue": "high"})
        gauge.set(10.0, labels={"queue": "low"})

        values = list(gauge.collect())
        assert len(values) == 2


class TestHistogram:
    """测试 Histogram 指标"""

    def test_histogram_observe(self):
        """测试直方图观察"""
        histogram = Histogram("test_histogram")
        histogram.observe(0.123)

        data = histogram.get()
        assert data.count == 1
        assert data.sum == 0.123

    def test_histogram_with_labels(self):
        """测试带标签的直方图"""
        histogram = Histogram("test_histogram")
        histogram.observe(0.1, labels={"endpoint": "/a"})
        histogram.observe(0.2, labels={"endpoint": "/a"})
        histogram.observe(0.5, labels={"endpoint": "/b"})

        data_a = histogram.get({"endpoint": "/a"})
        data_b = histogram.get({"endpoint": "/b"})

        assert data_a.count == 2
        assert data_b.count == 1

    def test_histogram_collect(self):
        """测试收集直方图数据"""
        histogram = Histogram("test_histogram")
        histogram.observe(0.1, labels={"endpoint": "/a"})
        histogram.observe(0.5, labels={"endpoint": "/b"})

        collected = list(histogram.collect())
        assert len(collected) == 2


class TestMetricsCollector:
    """测试指标收集器"""

    def test_create_counter(self):
        """测试创建计数器"""
        collector = MetricsCollector()
        counter = collector.counter("requests_total")
        assert isinstance(counter, Counter)
        assert counter.name == "requests_total"

    def test_create_gauge(self):
        """测试创建仪表盘"""
        collector = MetricsCollector()
        gauge = collector.gauge("active_connections")
        assert isinstance(gauge, Gauge)
        assert gauge.name == "active_connections"

    def test_create_histogram(self):
        """测试创建直方图"""
        collector = MetricsCollector()
        histogram = collector.histogram("response_duration")
        assert isinstance(histogram, Histogram)
        assert histogram.name == "response_duration"

    def test_get_same_metric(self):
        """测试获取相同指标返回同一实例"""
        collector = MetricsCollector()
        counter1 = collector.counter("requests_total")
        counter2 = collector.counter("requests_total")
        assert counter1 is counter2

    def test_export_prometheus_format(self):
        """测试导出 Prometheus 格式"""
        collector = MetricsCollector(namespace="test")

        # 添加一些指标
        collector.counter("api_requests_total").inc(
            10.0, labels={"endpoint": "/tasks", "method": "GET"}
        )
        collector.gauge("active_requests").set(5.0, labels={"service": "api"})
        collector.histogram("response_time").observe(0.123, labels={"endpoint": "/tasks"})

        prom_text = collector.export_prometheus()

        # 验证基本格式
        assert "# TYPE test_api_requests_total counter" in prom_text
        assert "# TYPE test_active_requests gauge" in prom_text
        assert "# TYPE test_response_time histogram" in prom_text

        # 验证指标值行（允许标签中有空格）
        assert "test_api_requests_total{" in prom_text
        assert 'endpoint="/tasks"' in prom_text
        assert 'method="GET"' in prom_text
        assert "10.0" in prom_text

        assert "test_active_requests{" in prom_text
        assert 'service="api"' in prom_text
        assert "5.0" in prom_text

        # 验证直方图输出
        assert "test_response_time_sum{" in prom_text
        assert "test_response_time_count{" in prom_text

    def test_reset_metrics(self):
        """测试重置指标"""
        collector = MetricsCollector()
        collector.counter("requests").inc(10.0)
        collector.gauge("active").set(5.0)

        collector.reset()

        counter = collector.counter("requests")
        assert counter.get() == 0.0

    def test_with_namespace(self):
        """测试自定义命名空间"""
        collector = MetricsCollector(namespace="my_app")
        collector.counter("test").inc()

        prom_text = collector.export_prometheus()
        assert "# TYPE my_app_test counter" in prom_text


class TestGlobalMetricsCollector:
    """测试全局指标收集器"""

    def test_get_metrics_collector(self):
        """测试获取全局指标收集器"""
        import src.utils.metrics as metrics_module

        metrics_module._metrics_collector = None

        collector1 = get_metrics_collector()
        collector2 = get_metrics_collector()
        assert collector1 is collector2

    def test_get_metrics_collector_namespace(self):
        """测试带命名空间的全局指标收集器"""
        # 先重置
        import src.utils.metrics as metrics_module

        metrics_module._metrics_collector = None

        collector = get_metrics_collector("custom_namespace")
        assert collector.namespace == "custom_namespace"


class TestIntegration:
    """集成测试"""

    def test_full_usage_example(self):
        """测试完整的使用示例"""
        metrics = MetricsCollector()

        # 模拟 API 请求处理
        metrics.gauge("api_requests_active").inc()

        metrics.counter("api_requests_total", labels={"endpoint": "/tasks", "method": "GET"}).inc()
        metrics.counter("api_requests_total", labels={"endpoint": "/tasks", "method": "GET"}).inc()

        metrics.histogram("api_response_duration", labels={"endpoint": "/tasks"}).observe(0.123)
        metrics.histogram("api_response_duration", labels={"endpoint": "/tasks"}).observe(0.087)

        metrics.gauge("api_requests_active").dec()

        # 验证
        assert metrics.gauge("api_requests_active").get() == 0.0
        assert (
            metrics.counter("api_requests_total").get({"endpoint": "/tasks", "method": "GET"})
            == 2.0
        )

        hist_data = metrics.histogram("api_response_duration").get({"endpoint": "/tasks"})
        assert hist_data.count == 2
        assert abs(hist_data.sum - 0.21) < 1e-9

    def test_prometheus_export_format_validity(self):
        """测试 Prometheus 导出格式的有效性"""
        metrics = MetricsCollector(namespace="fa")

        # 添加各种指标
        metrics.counter("http_requests_total").inc(5, labels={"code": "200", "method": "GET"})
        metrics.counter("http_requests_total").inc(2, labels={"code": "500", "method": "POST"})

        metrics.gauge("in_progress_requests").set(3, labels={"service": "auth"})

        metrics.histogram("request_duration_seconds").observe(0.1, labels={"path": "/api/v1/login"})
        metrics.histogram("request_duration_seconds").observe(0.2, labels={"path": "/api/v1/login"})

        prometheus_output = metrics.export_prometheus()

        # 验证基本 Prometheus 格式特征
        lines = prometheus_output.strip().splitlines()

        # 验证类型注释
        type_lines = [line for line in lines if line.startswith("# TYPE")]
        assert len(type_lines) == 3  # 三个指标类型

        # 验证所有非注释行都有值和时间戳
        data_lines = [line for line in lines if not line.startswith("#")]
        for line in data_lines:
            # 格式: metric_name{labels} value timestamp
            # 从后往前拆分，因为标签可能很复杂
            parts = line.rsplit(" ", 2)
            assert len(parts) == 3, f"Line should have 3 parts: {line}"
            name_part, value_part, timestamp_part = parts

            # 验证值是数字
            float(value_part)

            # 验证时间戳是整数
            int(timestamp_part)
