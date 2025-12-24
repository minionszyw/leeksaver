"""
数据同步 API 端点
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.sync.status_manager import sync_status_manager, SyncTaskInfo

router = APIRouter()


class SyncStatus(BaseModel):
    """同步状态"""

    task_name: str = Field(..., description="任务名称")
    status: str = Field(..., description="状态 (idle/running/completed/failed)")
    last_run: str | None = Field(None, description="上次运行时间")
    last_success: str | None = Field(None, description="上次成功时间")
    next_run: str | None = Field(None, description="下次运行时间")
    progress: float | None = Field(None, description="进度 (0-100)")
    message: str | None = Field(None, description="状态消息")
    error: str | None = Field(None, description="错误信息")
    records_processed: int = Field(0, description="已处理记录数")
    records_total: int | None = Field(None, description="总记录数")

    @classmethod
    def from_task_info(cls, info: SyncTaskInfo) -> "SyncStatus":
        return cls(
            task_name=info.task_name,
            status=info.status.value,
            last_run=info.last_run.isoformat() if info.last_run else None,
            last_success=info.last_success.isoformat() if info.last_success else None,
            next_run=info.next_run.isoformat() if info.next_run else None,
            progress=info.progress,
            message=info.message,
            error=info.error,
            records_processed=info.records_processed,
            records_total=info.records_total,
        )


class SyncStatusResponse(BaseModel):
    """同步状态响应"""

    tasks: list[SyncStatus]


class TriggerSyncResponse(BaseModel):
    """触发同步响应"""

    task_id: str
    message: str


@router.get("/status", response_model=SyncStatusResponse)
async def get_sync_status():
    """
    获取数据同步状态

    返回所有同步任务的当前状态
    """
    task_infos = await sync_status_manager.get_all_status()
    return SyncStatusResponse(
        tasks=[SyncStatus.from_task_info(info) for info in task_infos]
    )


@router.post("/trigger/{code}", response_model=TriggerSyncResponse)
async def trigger_sync(code: str):
    """
    触发按需同步 (L3)

    Args:
        code: 股票代码
    """
    from app.tasks.sync_tasks import sync_single_stock

    task = sync_single_stock.delay(code)
    return TriggerSyncResponse(
        task_id=task.id,
        message=f"已触发 {code} 数据同步",
    )


@router.post("/trigger-full", response_model=TriggerSyncResponse)
async def trigger_full_sync():
    """
    触发全市场同步 (L1)
    """
    from app.tasks.sync_tasks import sync_daily_quotes

    task = sync_daily_quotes.delay()
    return TriggerSyncResponse(
        task_id=task.id,
        message="已触发全市场数据同步",
    )


@router.post("/trigger-stock-list", response_model=TriggerSyncResponse)
async def trigger_stock_list_sync():
    """
    触发股票列表同步
    """
    from app.tasks.sync_tasks import sync_stock_list

    task = sync_stock_list.delay()
    return TriggerSyncResponse(
        task_id=task.id,
        message="已触发股票列表同步",
    )


@router.get("/status/{task_name}", response_model=SyncStatus)
async def get_task_status(task_name: str):
    """
    获取指定任务的同步状态

    Args:
        task_name: 任务名称 (stock_list_sync, daily_quote_sync, single_stock_sync)
    """
    if task_name not in sync_status_manager.TASK_NAMES:
        raise HTTPException(status_code=404, detail=f"未知任务: {task_name}")

    info = await sync_status_manager.get_task_status(task_name)
    return SyncStatus.from_task_info(info)


class CeleryTaskStatus(BaseModel):
    """Celery 任务状态"""

    task_id: str
    status: str
    result: dict | None = None


@router.get("/task/{task_id}", response_model=CeleryTaskStatus)
async def get_celery_task_status(task_id: str):
    """
    获取 Celery 任务状态

    Args:
        task_id: Celery 任务 ID
    """
    from app.tasks.celery_app import celery_app

    result = celery_app.AsyncResult(task_id)
    return CeleryTaskStatus(
        task_id=task_id,
        status=result.status,
        result=result.result if result.ready() else None,
    )
