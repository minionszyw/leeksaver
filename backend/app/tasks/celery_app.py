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

# 定时任务配置 (Celery Beat) - 从配置读取 CRON 表达式
celery_app.conf.beat_schedule = {
    # L1: 每日收盘后同步全市场日线数据
    "daily-market-sync": {
        "task": "app.tasks.sync_tasks.sync_daily_quotes",
        "schedule": crontab(
            hour=settings.sync_daily_quotes_hour,
            minute=settings.sync_daily_quotes_minute,
        ),
        "args": (),
    },
    # L2: 每小时同步自选股数据
    "watchlist-sync": {
        "task": "app.tasks.sync_tasks.sync_watchlist_quotes",
        "schedule": crontab(minute=settings.sync_watchlist_quotes_minute),
        "args": (),
    },
    # 每周同步全市场财务报表数据
    "weekly-financial-sync": {
        "task": "app.tasks.sync_tasks.sync_financial_statements",
        "schedule": crontab(
            day_of_week=settings.sync_financial_day_of_week,
            hour=settings.sync_financial_hour,
            minute=settings.sync_financial_minute,
        ),
        "args": (),
    },
    # 早间同步全市场新闻
    "morning-market-news-sync": {
        "task": "app.tasks.sync_tasks.sync_market_news",
        "schedule": crontab(
            hour=settings.sync_market_news_morning_hour,
            minute=settings.sync_market_news_morning_minute,
        ),
        "args": (),
    },
    # 晚间同步全市场新闻
    "evening-market-news-sync": {
        "task": "app.tasks.sync_tasks.sync_market_news",
        "schedule": crontab(
            hour=settings.sync_market_news_evening_hour,
            minute=settings.sync_market_news_evening_minute,
        ),
        "args": (),
    },
    # 早间同步自选股新闻
    "morning-watchlist-news-sync": {
        "task": "app.tasks.sync_tasks.sync_watchlist_news",
        "schedule": crontab(
            hour=settings.sync_watchlist_news_morning_hour,
            minute=settings.sync_watchlist_news_morning_minute,
        ),
        "args": (),
    },
    # 晚间同步自选股新闻
    "evening-watchlist-news-sync": {
        "task": "app.tasks.sync_tasks.sync_watchlist_news",
        "schedule": crontab(
            hour=settings.sync_watchlist_news_evening_hour,
            minute=settings.sync_watchlist_news_evening_minute,
        ),
        "args": (),
    },
    # 每小时生成新闻向量
    "hourly-news-embeddings": {
        "task": "app.tasks.sync_tasks.generate_news_embeddings",
        "schedule": crontab(minute=settings.generate_embeddings_minute),
        "args": (),
    },
    # 每日收盘后同步板块行情
    "daily-sector-sync": {
        "task": "app.tasks.sync_tasks.sync_sector_quotes",
        "schedule": crontab(
            hour=settings.sync_sector_quotes_hour,
            minute=settings.sync_sector_quotes_minute,
        ),
        "args": (),
    },
    # 每周清理过期新闻
    "weekly-news-cleanup": {
        "task": "app.tasks.sync_tasks.cleanup_old_news",
        "schedule": crontab(
            day_of_week=settings.cleanup_news_day_of_week,
            hour=settings.cleanup_news_hour,
            minute=settings.cleanup_news_minute,
        ),
        "args": (),
    },
    # ==================== 资金面同步任务 ====================
    # 每日收盘后同步北向资金
    "daily-northbound-flow-sync": {
        "task": "app.tasks.sync_tasks.sync_northbound_flow",
        "schedule": crontab(
            hour=settings.sync_northbound_flow_hour,
            minute=settings.sync_northbound_flow_minute,
        ),
        "args": (),
    },
    # 每日收盘后同步个股资金流向
    "daily-fund-flow-sync": {
        "task": "app.tasks.sync_tasks.sync_stock_fund_flow",
        "schedule": crontab(
            hour=settings.sync_fund_flow_hour,
            minute=settings.sync_fund_flow_minute,
        ),
        "args": (),
    },
    # 每日晚间同步龙虎榜
    "daily-dragon-tiger-sync": {
        "task": "app.tasks.sync_tasks.sync_dragon_tiger",
        "schedule": crontab(
            hour=settings.sync_dragon_tiger_hour,
            minute=settings.sync_dragon_tiger_minute,
        ),
        "args": (),
    },
    # 每日晚间同步两融数据
    "daily-margin-trade-sync": {
        "task": "app.tasks.sync_tasks.sync_margin_trade",
        "schedule": crontab(
            hour=settings.sync_margin_trade_hour,
            minute=settings.sync_margin_trade_minute,
        ),
        "args": (),
    },
    # ==================== 情绪面同步任务 ====================
    # 每日收盘后同步市场情绪
    "daily-market-sentiment-sync": {
        "task": "app.tasks.sync_tasks.sync_market_sentiment",
        "schedule": crontab(
            hour=settings.sync_market_sentiment_hour,
            minute=settings.sync_market_sentiment_minute,
        ),
        "args": (),
    },
    # ==================== 估值同步任务 ====================
    # 每日收盘后同步估值数据
    "daily-valuation-sync": {
        "task": "app.tasks.sync_tasks.sync_daily_valuation",
        "schedule": crontab(
            hour=settings.sync_valuation_hour,
            minute=settings.sync_valuation_minute,
        ),
        "args": (),
    },
    # ==================== 技术指标任务 ====================
    # 每日收盘后计算技术指标
    "daily-tech-indicator-calc": {
        "task": "app.tasks.sync_tasks.calculate_tech_indicators",
        "schedule": crontab(
            hour=settings.calc_tech_indicators_hour,
            minute=settings.calc_tech_indicators_minute,
        ),
        "args": (),
    },
}
