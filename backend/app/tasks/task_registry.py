"""
Celery 任务注册表

统一管理所有定时任务的元数据和调度策略。
采用分层调度策略：L1（日更）、L2（日内）、L3（按需）。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TaskTier(str, Enum):
    """任务层级"""

    L0 = "L0"  # 周更组 - 财务/宏观/经营数据
    L1 = "L1"  # 低频/日更组 - 收盘后统一执行
    L2 = "L2"  # 高频/日内组 - 定时轮询
    L3 = "L3"  # 按需/实时组 - API 触发


class ScheduleType(str, Enum):
    """调度类型"""

    CRONTAB = "crontab"  # 固定时间点执行
    INTERVAL = "interval"  # 固定间隔执行


@dataclass
class TaskMetadata:
    """任务元数据"""

    # 任务标识
    name: str  # 任务名称（beat_schedule key）
    task_path: str  # 任务函数路径（如 "app.tasks.sync_tasks.sync_daily_quotes"）

    # 分层信息
    tier: TaskTier

    # 调度信息
    schedule_type: ScheduleType

    # L2 任务专用：错开间隔倍数（0 表示立即执行，1 表示延迟 1*offset）
    offset_multiplier: int = 0

    # 任务依赖（可选，用于未来优化）
    depends_on: Optional[list[str]] = None

    # 描述
    description: str = ""

    # 任务参数（传递给任务函数）
    args: tuple = field(default_factory=tuple)


# ==================== L1 任务：日更组（17:30 统一执行）====================

L1_TASKS = [
    TaskMetadata(
        name="daily-stock-list-sync",
        task_path="app.tasks.sync_tasks.sync_stock_list",
        tier=TaskTier.L1,
        schedule_type=ScheduleType.CRONTAB,
        description="股票列表同步（每日发现新股/ETF）",
    ),
    TaskMetadata(
        name="daily-market-sync",
        task_path="app.tasks.sync_tasks.sync_daily_quotes",
        tier=TaskTier.L1,
        schedule_type=ScheduleType.CRONTAB,
        description="全市场日线数据同步",
    ),
    TaskMetadata(
        name="daily-dragon-tiger-sync",
        task_path="app.tasks.sync_tasks.sync_dragon_tiger",
        tier=TaskTier.L1,
        schedule_type=ScheduleType.CRONTAB,
        description="龙虎榜数据同步",
    ),
    TaskMetadata(
        name="daily-valuation-sync",
        task_path="app.tasks.sync_tasks.sync_daily_valuation",
        tier=TaskTier.L1,
        schedule_type=ScheduleType.CRONTAB,
        description="估值数据同步",
    ),
    TaskMetadata(
        name="daily-northbound-flow-sync",
        task_path="app.tasks.sync_tasks.sync_northbound_flow",
        tier=TaskTier.L1,
        schedule_type=ScheduleType.CRONTAB,
        description="北向资金同步",
    ),
    TaskMetadata(
        name="daily-fund-flow-sync",
        task_path="app.tasks.sync_tasks.sync_stock_fund_flow",
        tier=TaskTier.L1,
        schedule_type=ScheduleType.CRONTAB,
        description="个股资金流向同步",
    ),
    TaskMetadata(
        name="daily-margin-trade-sync",
        task_path="app.tasks.sync_tasks.sync_margin_trade",
        tier=TaskTier.L1,
        schedule_type=ScheduleType.CRONTAB,
        description="两融数据同步",
    ),
    TaskMetadata(
        name="daily-market-sentiment-sync",
        task_path="app.tasks.sync_tasks.sync_market_sentiment",
        tier=TaskTier.L1,
        schedule_type=ScheduleType.CRONTAB,
        description="市场情绪同步",
    ),
    TaskMetadata(
        name="daily-tech-indicator-calc",
        task_path="app.tasks.sync_tasks.calculate_tech_indicators",
        tier=TaskTier.L1,
        schedule_type=ScheduleType.CRONTAB,
        depends_on=["daily-market-sync"],  # 依赖日线数据
        description="技术指标计算（依赖日线数据）",
    ),
    TaskMetadata(
        name="daily-news-cleanup",
        task_path="app.tasks.sync_tasks.cleanup_old_news",
        tier=TaskTier.L1,
        schedule_type=ScheduleType.CRONTAB,
        description="过期新闻数据清理（每日凌晨）",
    ),
]


# ==================== L2 任务：日内组（每 300 秒，错开执行）====================

L2_TASKS = [
    TaskMetadata(
        name="intraday-global-news-sync",
        task_path="app.tasks.sync_tasks.sync_global_news",
        tier=TaskTier.L2,
        schedule_type=ScheduleType.INTERVAL,
        offset_multiplier=0,
        description="全市快讯同步 (财联社单一源)",
    ),
    TaskMetadata(
        name="intraday-stock-news-rotation-sync",
        task_path="app.tasks.sync_tasks.sync_stock_news_rotation",
        tier=TaskTier.L2,
        schedule_type=ScheduleType.INTERVAL,
        offset_multiplier=1,
        description="全市场个股新闻轮询同步 (东方财富)",
    ),
    TaskMetadata(
        name="intraday-watchlist-quotes-sync",
        task_path="app.tasks.sync_tasks.sync_watchlist_quotes",
        tier=TaskTier.L2,
        schedule_type=ScheduleType.INTERVAL,
        offset_multiplier=2,  # offset: 2 * 120s = 240s
        description="自选股行情同步",
    ),
    TaskMetadata(
        name="intraday-minute-quotes-sync",
        task_path="app.tasks.sync_tasks.sync_minute_quotes",
        tier=TaskTier.L2,
        schedule_type=ScheduleType.INTERVAL,
        offset_multiplier=2.5,  # offset: 2.5 * 120s = 300s
        description="自选股分钟行情同步",
    ),
    TaskMetadata(
        name="intraday-sector-quotes-sync",
        task_path="app.tasks.sync_tasks.sync_sector_quotes",
        tier=TaskTier.L2,
        schedule_type=ScheduleType.INTERVAL,
        offset_multiplier=3,  # offset: 3 * 120s = 360s
        description="板块行情同步",
    ),
    TaskMetadata(
        name="intraday-news-embeddings-gen",
        task_path="app.tasks.sync_tasks.generate_news_embeddings",
        tier=TaskTier.L2,
        schedule_type=ScheduleType.INTERVAL,
        offset_multiplier=4,  # offset: 4 * 120s = 480s
        depends_on=["intraday-market-news-sync", "intraday-watchlist-news-sync"],
        description="新闻向量生成（依赖新闻同步）",
    ),
]


# ==================== L0 任务：周更组（独立配置） ====================

L0_TASKS = [
    TaskMetadata(
        name="weekly-financial-sync",
        task_path="app.tasks.sync_tasks.sync_financial_statements",
        tier=TaskTier.L0,
        schedule_type=ScheduleType.CRONTAB,
        description="财务报表同步（每周六 20:00）",
    ),
    TaskMetadata(
        name="weekly-macro-sync",
        task_path="app.tasks.sync_tasks.sync_macro_economic_data",
        tier=TaskTier.L0,
        schedule_type=ScheduleType.CRONTAB,
        description="宏观经济数据同步（每周六 21:00）",
    ),
    TaskMetadata(
        name="weekly-operation-sync",
        task_path="app.tasks.sync_tasks.sync_operation_data",
        tier=TaskTier.L0,
        schedule_type=ScheduleType.CRONTAB,
        description="经营数据同步（每周六 22:00）",
    ),
    TaskMetadata(
        name="daily-health-check",
        task_path="daily_data_health_check",
        tier=TaskTier.L0,
        schedule_type=ScheduleType.CRONTAB,
        description="数据健康巡检（每天 09:00）",
    ),
]


# 注册表汇总
ALL_TASKS = L1_TASKS + L2_TASKS + L0_TASKS
