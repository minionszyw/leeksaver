"""
Redis 缓存工具

提供装饰器和缓存管理功能
"""

import functools
import hashlib
import json
import random
from typing import Callable, Any

from app.core.logging import get_logger

logger = get_logger(__name__)


def cached(ttl: int = 300, key_prefix: str = "", add_jitter: bool = True):
    """
    Redis 缓存装饰器

    使用示例:
        @cached(ttl=300, key_prefix="valuation")
        async def get_all_valuations(self, trade_date: date) -> pl.DataFrame:
            # ... 实际逻辑 ...

    Args:
        ttl: 缓存过期时间（秒），默认 5 分钟
        key_prefix: 缓存键前缀，用于区分不同类型的缓存
        add_jitter: 是否添加随机抖动（±10%）防止缓存雪崩

    Returns:
        装饰后的函数
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # 动态导入避免循环依赖
            try:
                from app.core.redis_client import redis_client
            except ImportError:
                logger.warning("Redis 客户端不可用，跳过缓存")
                return await func(*args, **kwargs)

            # 生成缓存键
            cache_key = _generate_cache_key(key_prefix, func.__name__, args, kwargs)

            # 尝试从缓存获取
            try:
                cached_value = await redis_client.get(cache_key)
                if cached_value:
                    logger.debug(f"缓存命中: {cache_key}")
                    # 尝试解析 JSON
                    try:
                        return json.loads(cached_value)
                    except json.JSONDecodeError:
                        # 如果不是 JSON，直接返回字符串
                        return cached_value
            except Exception as e:
                logger.warning(f"读取缓存失败: {e}")
                # 缓存读取失败，继续执行原函数

            # 缓存未命中，执行原函数
            result = await func(*args, **kwargs)

            # 写入缓存
            try:
                # 计算实际 TTL（添加随机抖动）
                actual_ttl = ttl
                if add_jitter:
                    jitter = int(ttl * 0.1)  # ±10%
                    actual_ttl = ttl + random.randint(-jitter, jitter)

                # 序列化结果
                serialized_result = json.dumps(result, default=str, ensure_ascii=False)

                await redis_client.setex(cache_key, actual_ttl, serialized_result)
                logger.debug(f"写入缓存: {cache_key}, TTL={actual_ttl}s")
            except Exception as e:
                logger.warning(f"写入缓存失败: {e}")
                # 缓存写入失败不影响功能，继续返回结果

            return result

        return wrapper

    return decorator


def _generate_cache_key(prefix: str, func_name: str, args, kwargs) -> str:
    """
    生成缓存键（基于参数哈希）

    格式: prefix:func_name:params_hash

    Args:
        prefix: 前缀
        func_name: 函数名
        args: 位置参数
        kwargs: 关键字参数

    Returns:
        缓存键字符串
    """
    key_parts = [prefix, func_name] if prefix else [func_name]

    # 序列化参数（排除 self）
    filtered_args = tuple(arg for arg in args if not _is_self(arg))

    params_str = json.dumps(
        {"args": filtered_args, "kwargs": kwargs}, default=str, sort_keys=True
    )

    # 计算参数哈希（取前 8 位）
    params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]
    key_parts.append(params_hash)

    return ":".join(key_parts)


def _is_self(obj: Any) -> bool:
    """
    判断对象是否为实例方法的 self 参数

    Args:
        obj: 待检查对象

    Returns:
        是否为 self
    """
    # 简单判断：如果对象有 __dict__ 且不是基本类型，认为是 self
    return hasattr(obj, "__dict__") and not isinstance(
        obj, (str, int, float, bool, list, dict, tuple, set)
    )


async def clear_cache_by_prefix(prefix: str) -> int:
    """
    清除指定前缀的所有缓存

    Args:
        prefix: 缓存键前缀

    Returns:
        清除的缓存数量
    """
    try:
        from app.core.redis_client import redis_client

        # 获取所有匹配的键
        pattern = f"{prefix}:*"
        keys = await redis_client.keys(pattern)

        if not keys:
            return 0

        # 删除所有匹配的键
        deleted = await redis_client.delete(*keys)
        logger.info(f"清除缓存: {prefix}, 删除 {deleted} 条")
        return deleted

    except Exception as e:
        logger.error(f"清除缓存失败: {e}")
        return 0
