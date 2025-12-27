"""
Celery 应用配置

用于异步任务和定时任务调度
"""

from datetime import timedelta

from celery import Celery
from celery.schedules import crontab

from app.config import settings
from app.tasks.schedules import OffsetSchedule
from app.tasks.task_registry import ALL_TASKS, TaskTier, ScheduleType

# 创建 Celery 应用
celery_app = Celery(
    "leeksaver",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.sync_tasks",
        "app.tasks.monitoring_tasks",  # 监控任务
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


def generate_beat_schedule() -> dict:
    """
    动态生成 Celery Beat 调度配置

    根据任务注册表和配置生成 beat_schedule。
    支持 L1（日更）、L2（日内）、SPECIAL（特殊）三种任务类型。

    Returns:
        dict: Celery Beat 调度配置字典
    """
    beat_schedule = {}

    for task_meta in ALL_TASKS:
        schedule_config = None

        # L1 任务：固定时间（从配置读取）
        if task_meta.tier == TaskTier.L1:
            schedule_config = crontab(
                hour=settings.l1_schedule_hour,
                minute=settings.l1_schedule_minute,
            )

        # L2 任务：固定间隔 + offset
        elif task_meta.tier == TaskTier.L2:
            offset_seconds = (
                task_meta.offset_multiplier * settings.sync_l2_task_offset_seconds
            )
            schedule_config = OffsetSchedule(
                run_every=timedelta(seconds=settings.sync_l2_interval_seconds),
                offset=timedelta(seconds=offset_seconds),
            )

        # 特殊任务：使用独立配置
        elif task_meta.tier == TaskTier.SPECIAL:
            if "financial" in task_meta.name:
                # 财报同步（每周六 20:00）
                schedule_config = crontab(
                    day_of_week=settings.sync_financial_day_of_week,
                    hour=settings.sync_financial_hour,
                    minute=settings.sync_financial_minute,
                )
            elif "cleanup" in task_meta.name:
                # 新闻清理（每周一 02:00）
                schedule_config = crontab(
                    day_of_week=settings.cleanup_news_day_of_week,
                    hour=settings.cleanup_news_hour,
                    minute=settings.cleanup_news_minute,
                )
            elif "health" in task_meta.name:
                # 数据健康巡检（每天 09:00）
                schedule_config = crontab(
                    hour=settings.health_check_hour,
                    minute=settings.health_check_minute,
                )

        # 添加到 beat_schedule
        if schedule_config:
            beat_schedule[task_meta.name] = {
                "task": task_meta.task_path,
                "schedule": schedule_config,
                "args": task_meta.args,
            }

    return beat_schedule


# 动态生成并配置 Celery Beat 调度
celery_app.conf.beat_schedule = generate_beat_schedule()
