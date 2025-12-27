"""
Alembic 环境配置
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# 导入应用配置和模型
from app.config import settings
from app.models.base import Base
from app.models.stock import Stock, Watchlist
from app.models.market_data import DailyQuote, MinuteQuote
from app.models.financial import FinancialStatement
from app.models.news import NewsArticle
from app.models.macro import MacroIndicator
from app.models.sector import Sector, SectorQuote
from app.models.capital_flow import NorthboundFlow, StockFundFlow, DragonTiger, MarginTrade
from app.models.market_sentiment import MarketSentiment, LimitUpStock
from app.models.valuation import DailyValuation
from app.models.tech_indicator import TechIndicator
from app.models.sync_error import SyncError

# Alembic Config 对象
config = context.config

# 设置数据库 URL
config.set_main_option("sqlalchemy.url", settings.sync_database_url)

# 配置日志
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 目标元数据
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    离线模式运行迁移

    生成 SQL 脚本而不连接数据库
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    在线模式运行迁移

    连接数据库并执行迁移
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
