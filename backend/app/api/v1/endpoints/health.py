"""
健康检查 API 端点

提供系统各组件的健康状态检查
"""

import asyncio
from datetime import datetime
from enum import Enum

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


class ComponentStatus(str, Enum):
    """组件状态"""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class ComponentHealth(BaseModel):
    """组件健康状态"""

    name: str
    status: ComponentStatus
    latency_ms: float | None = None
    message: str | None = None


class HealthResponse(BaseModel):
    """健康检查响应"""

    status: ComponentStatus
    app_name: str
    version: str
    timestamp: str
    components: list[ComponentHealth]


async def check_database() -> ComponentHealth:
    """检查数据库连接"""
    from app.core.database import get_db_session

    start = datetime.now()
    try:
        async with get_db_session() as session:
            result = await session.execute(text("SELECT 1"))
            _ = result.scalar()
        latency = (datetime.now() - start).total_seconds() * 1000
        return ComponentHealth(
            name="database",
            status=ComponentStatus.HEALTHY,
            latency_ms=round(latency, 2),
            message="PostgreSQL 连接正常",
        )
    except Exception as e:
        latency = (datetime.now() - start).total_seconds() * 1000
        logger.error("数据库健康检查失败", error=str(e))
        return ComponentHealth(
            name="database",
            status=ComponentStatus.UNHEALTHY,
            latency_ms=round(latency, 2),
            message=f"连接失败: {str(e)[:100]}",
        )


async def check_redis() -> ComponentHealth:
    """检查 Redis 连接"""
    import redis.asyncio as redis

    start = datetime.now()
    try:
        r = redis.from_url(settings.redis_url, decode_responses=True)
        await r.ping()
        await r.close()
        latency = (datetime.now() - start).total_seconds() * 1000
        return ComponentHealth(
            name="redis",
            status=ComponentStatus.HEALTHY,
            latency_ms=round(latency, 2),
            message="Redis 连接正常",
        )
    except Exception as e:
        latency = (datetime.now() - start).total_seconds() * 1000
        logger.error("Redis 健康检查失败", error=str(e))
        return ComponentHealth(
            name="redis",
            status=ComponentStatus.UNHEALTHY,
            latency_ms=round(latency, 2),
            message=f"连接失败: {str(e)[:100]}",
        )


async def check_llm() -> ComponentHealth:
    """检查 LLM API 连接（轻量级检查）"""
    start = datetime.now()
    try:
        # 只检查配置是否存在，不实际调用 API
        if settings.llm_provider == "deepseek":
            has_key = bool(settings.deepseek_api_key)
        elif settings.llm_provider == "openai":
            has_key = bool(settings.openai_api_key)
        elif settings.llm_provider == "ollama":
            has_key = True  # Ollama 不需要 API Key
        else:
            has_key = False

        latency = (datetime.now() - start).total_seconds() * 1000

        if has_key:
            return ComponentHealth(
                name="llm",
                status=ComponentStatus.HEALTHY,
                latency_ms=round(latency, 2),
                message=f"LLM 配置正常 ({settings.llm_provider})",
            )
        else:
            return ComponentHealth(
                name="llm",
                status=ComponentStatus.DEGRADED,
                latency_ms=round(latency, 2),
                message=f"LLM API Key 未配置 ({settings.llm_provider})",
            )
    except Exception as e:
        latency = (datetime.now() - start).total_seconds() * 1000
        return ComponentHealth(
            name="llm",
            status=ComponentStatus.UNKNOWN,
            latency_ms=round(latency, 2),
            message=f"检查失败: {str(e)[:100]}",
        )


def _check_celery_sync() -> ComponentHealth:
    """同步检查 Celery 工作进程"""
    from app.tasks.celery_app import celery_app

    start = datetime.now()
    try:
        # 使用同步调用，设置超时
        inspect = celery_app.control.inspect(timeout=2)
        stats = inspect.stats()
        latency = (datetime.now() - start).total_seconds() * 1000

        if stats:
            workers = list(stats.keys())
            return ComponentHealth(
                name="celery",
                status=ComponentStatus.HEALTHY,
                latency_ms=round(latency, 2),
                message=f"Celery 运行中，{len(workers)} 个 worker",
            )
        else:
            return ComponentHealth(
                name="celery",
                status=ComponentStatus.DEGRADED,
                latency_ms=round(latency, 2),
                message="没有活跃的 Celery worker",
            )
    except Exception as e:
        latency = (datetime.now() - start).total_seconds() * 1000
        logger.warning("Celery 健康检查失败", error=str(e))
        return ComponentHealth(
            name="celery",
            status=ComponentStatus.DEGRADED,
            latency_ms=round(latency, 2),
            message="Celery 检查超时或未运行",
        )


@router.get("", response_model=HealthResponse)
async def health_check():
    """
    完整健康检查

    检查所有关键组件的健康状态
    """
    # 并行检查所有组件
    results = await asyncio.gather(
        check_database(),
        check_redis(),
        check_llm(),
        return_exceptions=True,
    )

    # Celery 检查可能较慢，在线程池中运行
    try:
        celery_result = await asyncio.wait_for(
            asyncio.to_thread(_check_celery_sync),
            timeout=5.0,
        )
    except asyncio.TimeoutError:
        celery_result = ComponentHealth(
            name="celery",
            status=ComponentStatus.DEGRADED,
            message="Celery 检查超时",
        )
    except Exception as e:
        celery_result = ComponentHealth(
            name="celery",
            status=ComponentStatus.DEGRADED,
            message=f"检查失败: {str(e)[:50]}",
        )

    components = []
    for result in results:
        if isinstance(result, Exception):
            components.append(
                ComponentHealth(
                    name="unknown",
                    status=ComponentStatus.UNKNOWN,
                    message=str(result),
                )
            )
        else:
            components.append(result)

    components.append(celery_result)

    # 确定整体状态
    unhealthy = any(c.status == ComponentStatus.UNHEALTHY for c in components)
    degraded = any(c.status == ComponentStatus.DEGRADED for c in components)

    if unhealthy:
        overall_status = ComponentStatus.UNHEALTHY
    elif degraded:
        overall_status = ComponentStatus.DEGRADED
    else:
        overall_status = ComponentStatus.HEALTHY

    return HealthResponse(
        status=overall_status,
        app_name=settings.app_name,
        version="0.1.0",
        timestamp=datetime.now().isoformat(),
        components=components,
    )


@router.get("/liveness")
async def liveness():
    """
    存活检查

    用于 Kubernetes 存活探针，只检查应用是否在运行
    """
    return {"status": "alive"}


@router.get("/readiness")
async def readiness():
    """
    就绪检查

    用于 Kubernetes 就绪探针，检查应用是否准备好接收流量
    """
    # 只检查关键依赖：数据库和 Redis
    db_health, redis_health = await asyncio.gather(
        check_database(),
        check_redis(),
    )

    is_ready = (
        db_health.status == ComponentStatus.HEALTHY
        and redis_health.status == ComponentStatus.HEALTHY
    )

    if is_ready:
        return {"status": "ready", "database": "ok", "redis": "ok"}
    else:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "database": db_health.status.value,
                "redis": redis_health.status.value,
            },
        )


@router.get("/ready")
async def readiness_check():
    """就绪检查 (别名)"""
    return await readiness()
