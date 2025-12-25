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
    # 每周六晚 20:00 同步全市场财务报表数据
    "weekly-financial-sync": {
        "task": "app.tasks.sync_tasks.sync_financial_statements",
        "schedule": crontab(day_of_week=6, hour=20, minute=0),
        "args": (),
    },
    # 每天早 8:00 同步全市场新闻
    "morning-market-news-sync": {
        "task": "app.tasks.sync_tasks.sync_market_news",
        "schedule": crontab(hour=8, minute=0),
        "args": (),
    },
    # 每天晚 18:00 同步全市场新闻
    "evening-market-news-sync": {
        "task": "app.tasks.sync_tasks.sync_market_news",
        "schedule": crontab(hour=18, minute=0),
        "args": (),
    },
    # 每天早 8:05 同步自选股新闻
    "morning-watchlist-news-sync": {
        "task": "app.tasks.sync_tasks.sync_watchlist_news",
        "schedule": crontab(hour=8, minute=5),
        "args": (),
    },
    # 每天晚 18:05 同步自选股新闻
    "evening-watchlist-news-sync": {
        "task": "app.tasks.sync_tasks.sync_watchlist_news",
        "schedule": crontab(hour=18, minute=5),
        "args": (),
    },
    # 每小时生成新闻向量
    "hourly-news-embeddings": {
        "task": "app.tasks.sync_tasks.generate_news_embeddings",
        "schedule": crontab(minute=30),  # 每小时的第 30 分钟
        "args": (),
    },
    # 每日收盘后同步板块行情（16:30）
    "daily-sector-sync": {
        "task": "app.tasks.sync_tasks.sync_sector_quotes",
        "schedule": crontab(hour=16, minute=30),
        "args": (),
    },
    # 每周一凌晨 2:00 清理过期新闻
    "weekly-news-cleanup": {
        "task": "app.tasks.sync_tasks.cleanup_old_news",
        "schedule": crontab(day_of_week=0, hour=2, minute=0),
        "args": (),
    },
}
