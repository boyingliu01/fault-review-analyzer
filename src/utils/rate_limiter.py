"""自适应速率限制器 - 用于外部 API 调用的 QPS 控制。

支持成功时加速、失败时退避，避免压垮下游服务。
"""

from __future__ import annotations

import asyncio


class AdaptiveRateLimiter:
    """自适应速率限制器"""

    def __init__(
        self,
        initial_qps: float = 10.0,
        min_qps: float = 1.0,
        max_qps: float = 50.0,
        backoff_factor: float = 0.5,
        recovery_factor: float = 1.1,
    ):
        self.min_qps = min_qps
        self.max_qps = max_qps
        self.backoff_factor = backoff_factor
        self.recovery_factor = recovery_factor
        self.current_qps = initial_qps
        self._last_request_time: float = 0.0
        self._min_interval = 1.0 / max_qps

    async def acquire(self) -> None:
        """获取请求令牌（按当前 QPS 间隔等待）。"""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        interval = 1.0 / self.current_qps
        if elapsed < interval:
            await asyncio.sleep(interval - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()

    def record_success(self) -> None:
        """记录成功请求（恢复 QPS）。"""
        self.current_qps = min(self.current_qps * self.recovery_factor, self.max_qps)

    def record_failure(self) -> None:
        """记录失败请求（触发退避）。"""
        self.current_qps = max(self.current_qps * self.backoff_factor, self.min_qps)
