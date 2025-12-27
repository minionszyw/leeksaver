"""
限频与随机抖动机制

防止触发数据源风控
"""

import asyncio
import random
import time
from collections import deque
from typing import Callable, TypeVar, ParamSpec

from app.core.logging import get_logger

logger = get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


class RateLimiter:
    """
    滑动窗口限频器

    基于令牌桶算法，支持随机抖动
    """

    def __init__(
        self,
        max_requests: int = 5,
        window_seconds: float = 1.0,
        jitter_range: tuple[float, float] = (0.1, 0.5),
    ):
        """
        初始化限频器

        Args:
            max_requests: 时间窗口内最大请求数
            window_seconds: 时间窗口大小 (秒)
            jitter_range: 随机抖动范围 (最小, 最大) 秒
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.jitter_range = jitter_range
        self.request_times: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """
        获取执行许可

        如果超过限频，会自动等待
        """
        async with self._lock:
            now = time.monotonic()

            # 清理过期的请求记录
            while self.request_times and self.request_times[0] < now - self.window_seconds:
                self.request_times.popleft()

            # 检查是否超过限制
            if len(self.request_times) >= self.max_requests:
                # 计算需要等待的时间
                oldest = self.request_times[0]
                wait_time = oldest + self.window_seconds - now

                # 添加随机抖动
                jitter = random.uniform(*self.jitter_range)
                total_wait = wait_time + jitter

                logger.debug(
                    "限频等待",
                    wait_time=f"{total_wait:.2f}s",
                    current_requests=len(self.request_times),
                )
                await asyncio.sleep(total_wait)

                # 递归调用，确保限频条件满足
                await self.acquire()
                return

            # 记录本次请求
            self.request_times.append(now)

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


# 全局限频器实例 (用于 AkShare)
akshare_limiter = RateLimiter(
    max_requests=5,
    window_seconds=1,
    jitter_range=(0.1, 0.3),
)


def with_rate_limit(limiter: RateLimiter | None = None):
    """
    限频装饰器

    Args:
        limiter: 限频器实例，默认使用 akshare_limiter
    """
    _limiter = limiter or akshare_limiter

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            async with _limiter:
                return await func(*args, **kwargs)

        return wrapper

    return decorator
