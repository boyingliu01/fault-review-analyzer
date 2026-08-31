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
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """获取请求令牌（按当前 QPS 间隔等待，协程安全）。"""
        async with self._lock:
            now = asyncio.get_running_loop().time()
            elapsed = now - self._last_request_time
            interval = 1.0 / self.current_qps
            wait = max(0.0, interval - elapsed)
            # 在锁内原子预约本次请求的放行时刻，
            # 保证并发协程严格按间隔依次放行（不持锁睡眠）
            self._last_request_time = now + wait
        if wait > 0:
            await asyncio.sleep(wait)

    def record_success(self) -> None:
        """记录成功请求（恢复 QPS）。"""
        self.current_qps = min(self.current_qps * self.recovery_factor, self.max_qps)

    def record_failure(self) -> None:
        """记录失败请求（触发退避）。"""
        self.current_qps = max(self.current_qps * self.backoff_factor, self.min_qps)
