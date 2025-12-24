"""
Celery 应用配置

用于异步任务和定时任务调度
"""

from celery import Celery
from celery.schedules import crontab

from app.config import settings

# 创建 Celery 应用
celery_app = Celery(
    "leeksaver",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.sync_tasks",
    ],
)

# Celery 配置
celery_app.conf.update(
    # 任务序列化
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # 时区
    timezone="Asia/Shanghai",
    enable_utc=True,

    # 任务执行配置
    task_track_started=True,
    task_time_limit=3600,  # 1 小时超时

    # 结果过期时间
    result_expires=86400,  # 24 小时

    # Worker 配置
    worker_prefetch_multiplier=1,
    worker_concurrency=4,
)

# 定时任务配置 (Celery Beat)
celery_app.conf.beat_schedule = {
    # L1: 每日收盘后同步全市场日线数据 (16:00)
    "daily-market-sync": {
        "task": "app.tasks.sync_tasks.sync_daily_quotes",
        "schedule": crontab(hour=16, minute=0),
        "args": (),
    },
    # L2: 每小时同步自选股数据
    "watchlist-sync": {
        "task": "app.tasks.sync_tasks.sync_watchlist_quotes",
        "schedule": crontab(minute=0),
        "args": (),
    },
}
