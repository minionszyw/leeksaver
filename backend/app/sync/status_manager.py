"""
同步状态管理器

使用 Redis 存储和管理数据同步任务状态
"""

import json
from datetime import datetime
from enum import Enum
from typing import Any

import redis.asyncio as redis
from pydantic import BaseModel, Field

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class SyncTaskStatus(str, Enum):
    """同步任务状态"""

    IDLE = "idle"
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SyncTaskInfo(BaseModel):
    """同步任务信息"""

    task_name: str
    status: SyncTaskStatus = SyncTaskStatus.IDLE
    last_run: datetime | None = None
    last_success: datetime | None = None
    next_run: datetime | None = None
    progress: float | None = None
    message: str | None = None
    error: str | None = None
    records_processed: int = 0
    records_total: int | None = None

    def to_dict(self) -> dict:
        return {
            "task_name": self.task_name,
            "status": self.status.value,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "progress": self.progress,
            "message": self.message,
            "error": self.error,
            "records_processed": self.records_processed,
            "records_total": self.records_total,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SyncTaskInfo":
        return cls(
            task_name=data["task_name"],
            status=SyncTaskStatus(data.get("status", "idle")),
            last_run=datetime.fromisoformat(data["last_run"]) if data.get("last_run") else None,
            last_success=datetime.fromisoformat(data["last_success"]) if data.get("last_success") else None,
            next_run=datetime.fromisoformat(data["next_run"]) if data.get("next_run") else None,
            progress=data.get("progress"),
            message=data.get("message"),
            error=data.get("error"),
            records_processed=data.get("records_processed", 0),
            records_total=data.get("records_total"),
        )


class SyncStatusManager:
    """
    同步状态管理器

    用于追踪和管理各类数据同步任务的状态
    """

    TASK_NAMES = [
        "stock_list_sync",
        "daily_quote_sync",
        "single_stock_sync",
    ]

    def __init__(self, redis_url: str | None = None):
        self.redis_url = redis_url or settings.redis_url
        self._redis: redis.Redis | None = None

    async def _get_redis(self) -> redis.Redis:
        """获取 Redis 连接"""
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    def _get_key(self, task_name: str) -> str:
        """获取 Redis Key"""
        return f"leeksaver:sync:status:{task_name}"

    async def get_task_status(self, task_name: str) -> SyncTaskInfo:
        """获取任务状态"""
        r = await self._get_redis()
        key = self._get_key(task_name)

        data = await r.get(key)
        if data:
            try:
                return SyncTaskInfo.from_dict(json.loads(data))
            except Exception as e:
                logger.warning("解析任务状态失败", task_name=task_name, error=str(e))

        return SyncTaskInfo(task_name=task_name, message="等待首次同步")

    async def set_task_status(self, info: SyncTaskInfo) -> None:
        """设置任务状态"""
        r = await self._get_redis()
        key = self._get_key(info.task_name)
        data = json.dumps(info.to_dict(), ensure_ascii=False)
        await r.set(key, data, ex=86400)  # 24 小时过期

    async def get_all_status(self) -> list[SyncTaskInfo]:
        """获取所有任务状态"""
        result = []
        for task_name in self.TASK_NAMES:
            info = await self.get_task_status(task_name)
            result.append(info)
        return result

    async def start_task(
        self,
        task_name: str,
        total_records: int | None = None,
        message: str | None = None,
    ) -> None:
        """标记任务开始"""
        info = await self.get_task_status(task_name)
        info.status = SyncTaskStatus.RUNNING
        info.last_run = datetime.now()
        info.progress = 0.0
        info.records_processed = 0
        info.records_total = total_records
        info.message = message or "正在同步..."
        info.error = None
        await self.set_task_status(info)

    async def update_progress(
        self,
        task_name: str,
        processed: int,
        total: int | None = None,
        message: str | None = None,
    ) -> None:
        """更新任务进度"""
        info = await self.get_task_status(task_name)
        info.records_processed = processed

        if total:
            info.records_total = total
            info.progress = round((processed / total) * 100, 1) if total > 0 else 0.0

        if message:
            info.message = message

        await self.set_task_status(info)

    async def complete_task(
        self,
        task_name: str,
        message: str | None = None,
        next_run: datetime | None = None,
    ) -> None:
        """标记任务完成"""
        info = await self.get_task_status(task_name)
        info.status = SyncTaskStatus.COMPLETED
        info.last_success = datetime.now()
        info.progress = 100.0
        info.message = message or "同步完成"
        info.next_run = next_run
        await self.set_task_status(info)

    async def fail_task(
        self,
        task_name: str,
        error: str,
        message: str | None = None,
    ) -> None:
        """标记任务失败"""
        info = await self.get_task_status(task_name)
        info.status = SyncTaskStatus.FAILED
        info.error = error
        info.message = message or f"同步失败: {error}"
        await self.set_task_status(info)

    async def close(self) -> None:
        """关闭连接"""
        if self._redis:
            await self._redis.close()
            self._redis = None


# 全局实例
sync_status_manager = SyncStatusManager()
