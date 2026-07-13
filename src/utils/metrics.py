"""性能指标收集模块"""

from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class MetricValue:
    """指标值"""

    labels: dict[str, str] = field(default_factory=dict)
    value: float = 0.0


@dataclass
class HistogramData:
    """直方图数据"""

    count: int = 0
    sum: float = 0.0
    min: float = float("inf")
    max: float = -float("inf")
    buckets: dict[float, int] = field(default_factory=dict)

    def observe(self, value: float) -> None:
        """记录一个观察值"""
        self.count += 1
        self.sum += value
        if value < self.min:
            self.min = value
        if value > self.max:
            self.max = value

        # 默认分桶
        for bucket in [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]:
            if value <= bucket:
                self.buckets[bucket] = self.buckets.get(bucket, 0) + 1
        # 无穷大桶
        self.buckets[float("inf")] = self.buckets.get(float("inf"), 0) + 1

    def mean(self) -> float:
        """计算平均值"""
        if self.count == 0:
            return 0.0
        return self.sum / self.count

    def stddev(self) -> float:
        """计算标准差（简化版，不存储所有样本）"""
        return 0.0


class Counter:
    """计数器指标"""

    def __init__(self, name: str, labels: dict[str, str] | None = None):
        self.name = name
        self._values: dict[tuple[tuple[str, str], ...], float] = defaultdict(float)
        self._base_labels = labels or {}

    def _get_key(self, labels: dict[str, str]) -> tuple[tuple[str, str], ...]:
        """获取标签的哈希键"""
        merged = {**self._base_labels, **labels}
        return tuple(sorted(merged.items()))

    def inc(self, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """增加计数器"""
        key = self._get_key(labels or {})
        self._values[key] += value

    def get(self, labels: dict[str, str] | None = None) -> float:
        """获取计数器值"""
        key = self._get_key(labels or {})
        return self._values.get(key, 0.0)

    def collect(self) -> Iterator[MetricValue]:
        """收集所有指标值"""
        for key, value in self._values.items():
            yield MetricValue(labels=dict(key), value=value)


class Gauge:
    """仪表盘指标"""

    def __init__(self, name: str, labels: dict[str, str] | None = None):
        self.name = name
        self._values: dict[tuple[tuple[str, str], ...], float] = defaultdict(float)
        self._base_labels = labels or {}

    def _get_key(self, labels: dict[str, str]) -> tuple[tuple[str, str], ...]:
        """获取标签的哈希键"""
        merged = {**self._base_labels, **labels}
        return tuple(sorted(merged.items()))

    def set(self, value: float, labels: dict[str, str] | None = None) -> None:
        """设置仪表盘值"""
        key = self._get_key(labels or {})
        self._values[key] = value

    def inc(self, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """增加仪表盘值"""
        key = self._get_key(labels or {})
        self._values[key] += value

    def dec(self, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """减少仪表盘值"""
        key = self._get_key(labels or {})
        self._values[key] -= value

    def get(self, labels: dict[str, str] | None = None) -> float:
        """获取仪表盘值"""
        key = self._get_key(labels or {})
        return self._values.get(key, 0.0)

    def collect(self) -> Iterator[MetricValue]:
        """收集所有指标值"""
        for key, value in self._values.items():
            yield MetricValue(labels=dict(key), value=value)


class Histogram:
    """直方图指标"""

    def __init__(self, name: str, labels: dict[str, str] | None = None):
        self.name = name
        self._data: dict[tuple[tuple[str, str], ...], HistogramData] = defaultdict(HistogramData)
        self._base_labels = labels or {}

    def _get_key(self, labels: dict[str, str]) -> tuple[tuple[str, str], ...]:
        """获取标签的哈希键"""
        merged = {**self._base_labels, **labels}
        return tuple(sorted(merged.items()))

    def observe(self, value: float, labels: dict[str, str] | None = None) -> None:
        """记录一个观察值"""
        key = self._get_key(labels or {})
        self._data[key].observe(value)

    def get(self, labels: dict[str, str] | None = None) -> HistogramData:
        """获取直方图数据"""
        key = self._get_key(labels or {})
        return self._data[key]

    def collect(self) -> Iterator[tuple[dict[str, str], HistogramData]]:
        """收集所有直方图数据"""
        for key, data in self._data.items():
            yield dict(key), data


class MetricsCollector:
    """指标收集器"""

    def __init__(self, namespace: str = "fault_analyzer"):
        self.namespace = namespace
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}

    def counter(
        self,
        name: str,
        labels: dict[str, str] | None = None,
    ) -> Counter:
        """获取或创建一个计数器"""
        if name not in self._counters:
            self._counters[name] = Counter(name, labels)
        return self._counters[name]

    def gauge(
        self,
        name: str,
        labels: dict[str, str] | None = None,
    ) -> Gauge:
        """获取或创建一个仪表盘"""
        if name not in self._gauges:
            self._gauges[name] = Gauge(name, labels)
        return self._gauges[name]

    def histogram(
        self,
        name: str,
        labels: dict[str, str] | None = None,
    ) -> Histogram:
        """获取或创建一个直方图"""
        if name not in self._histograms:
            self._histograms[name] = Histogram(name, labels)
        return self._histograms[name]

    def export_prometheus(self) -> str:
        """导出 Prometheus 格式的指标"""
        lines: list[str] = []
        timestamp = int(datetime.now().timestamp() * 1000)

        # 导出计数器
        for name, counter in self._counters.items():
            full_name = f"{self.namespace}_{name}"
            lines.append(f"# TYPE {full_name} counter")
            for mv in counter.collect():
                label_str = self._format_labels(mv.labels)
                lines.append(f"{full_name}{label_str} {mv.value} {timestamp}")

        # 导出仪表盘
        for name, gauge in self._gauges.items():
            full_name = f"{self.namespace}_{name}"
            lines.append(f"# TYPE {full_name} gauge")
            for mv in gauge.collect():
                label_str = self._format_labels(mv.labels)
                lines.append(f"{full_name}{label_str} {mv.value} {timestamp}")

        # 导出直方图
        for name, histogram in self._histograms.items():
            full_name = f"{self.namespace}_{name}"
            lines.append(f"# TYPE {full_name} histogram")
            for labels, data in histogram.collect():
                # 分桶
                for bucket_le, bucket_count in sorted(data.buckets.items()):
                    bucket_labels = {**labels, "le": str(bucket_le)}
                    label_str = self._format_labels(bucket_labels)
                    lines.append(f"{full_name}_bucket{label_str} {bucket_count} {timestamp}")
                # 总和
                label_str = self._format_labels(labels)
                lines.append(f"{full_name}_sum{label_str} {data.sum} {timestamp}")
                lines.append(f"{full_name}_count{label_str} {data.count} {timestamp}")

        return "\n".join(lines) + "\n" if lines else ""

    def _format_labels(self, labels: dict[str, str]) -> str:
        """格式化 Prometheus 标签"""
        if not labels:
            return ""
        items = [f'{k}="{v}"' for k, v in sorted(labels.items())]
        return "{" + ",".join(items) + "}"

    def reset(self) -> None:
        """重置所有指标"""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()


# 全局指标收集器实例
_metrics_collector: MetricsCollector | None = None


def get_metrics_collector(namespace: str = "fault_analyzer") -> MetricsCollector:
    """获取全局指标收集器"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector(namespace)
    return _metrics_collector
