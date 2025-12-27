"""
数据库连接管理
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# 创建异步引擎
# 注意：在 Celery 环境中使用 NullPool 避免 event loop 冲突
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    poolclass=NullPool,  # 禁用连接池，避免 Celery 中的 event loop 问题
)

# 创建会话工厂
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话 (依赖注入)"""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话 (上下文管理器)"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """初始化数据库连接"""
    logger.info("初始化数据库连接", database_url=settings.database_url[:50] + "...")
    # 测试连接
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("数据库连接成功")


async def close_db() -> None:
    """关闭数据库连接"""
    logger.info("关闭数据库连接")
    await engine.dispose()
