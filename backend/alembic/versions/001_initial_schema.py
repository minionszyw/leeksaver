"""初始数据库 Schema

Revision ID: 001
Revises:
Create Date: 2024-01-01

创建基础表结构:
- stocks: 股票/ETF 基础信息
- watchlist: 自选股
- daily_quotes: 日线行情 (TimescaleDB Hypertable)
- minute_quotes: 分钟行情 (TimescaleDB Hypertable)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建 stocks 表
    op.create_table(
        "stocks",
        sa.Column("code", sa.String(10), primary_key=True, comment="股票代码"),
        sa.Column("name", sa.String(50), nullable=False, comment="股票名称"),
        sa.Column("market", sa.String(10), nullable=False, comment="市场: SH/SZ/BJ"),
        sa.Column(
            "asset_type",
            sa.String(10),
            nullable=False,
            server_default="stock",
            comment="类型: stock/etf",
        ),
        sa.Column("industry", sa.String(50), nullable=True, comment="行业"),
        sa.Column("list_date", sa.Date, nullable=True, comment="上市日期"),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default="true",
            comment="是否正常交易",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        comment="股票/ETF 基础信息表",
    )

    # stocks 索引
    op.create_index("ix_stocks_name", "stocks", ["name"])
    op.create_index("ix_stocks_market", "stocks", ["market"])
    op.create_index("ix_stocks_asset_type", "stocks", ["asset_type"])
    op.create_index("ix_stocks_industry", "stocks", ["industry"])

    # 创建 watchlist 表
    op.create_table(
        "watchlist",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(10), nullable=False, comment="股票代码"),
        sa.Column(
            "sort_order", sa.Integer, nullable=False, server_default="0", comment="排序"
        ),
        sa.Column("note", sa.String(200), nullable=True, comment="备注"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        comment="自选股表",
    )

    op.create_index("ix_watchlist_code", "watchlist", ["code"], unique=True)

    # 创建 daily_quotes 表
    op.create_table(
        "daily_quotes",
        sa.Column("code", sa.String(10), nullable=False, comment="股票代码"),
        sa.Column("trade_date", sa.Date, nullable=False, comment="交易日期"),
        sa.Column("open", sa.Numeric(10, 2), nullable=True, comment="开盘价"),
        sa.Column("high", sa.Numeric(10, 2), nullable=True, comment="最高价"),
        sa.Column("low", sa.Numeric(10, 2), nullable=True, comment="最低价"),
        sa.Column("close", sa.Numeric(10, 2), nullable=True, comment="收盘价"),
        sa.Column("volume", sa.BigInteger, nullable=True, comment="成交量"),
        sa.Column("amount", sa.Numeric(18, 2), nullable=True, comment="成交额"),
        sa.Column("change", sa.Numeric(10, 2), nullable=True, comment="涨跌额"),
        sa.Column("change_pct", sa.Numeric(8, 4), nullable=True, comment="涨跌幅"),
        sa.Column("turnover_rate", sa.Numeric(8, 4), nullable=True, comment="换手率"),
        sa.PrimaryKeyConstraint("code", "trade_date"),
        comment="日线行情表",
    )

    op.create_index("ix_daily_quotes_code", "daily_quotes", ["code"])
    op.create_index("ix_daily_quotes_trade_date", "daily_quotes", ["trade_date"])

    # 将 daily_quotes 转换为 TimescaleDB Hypertable
    op.execute(
        "SELECT create_hypertable('daily_quotes', 'trade_date', if_not_exists => TRUE)"
    )

    # 创建 minute_quotes 表
    op.create_table(
        "minute_quotes",
        sa.Column("code", sa.String(10), nullable=False, comment="股票代码"),
        sa.Column(
            "timestamp", sa.DateTime(timezone=True), nullable=False, comment="时间戳"
        ),
        sa.Column("open", sa.Numeric(10, 2), nullable=True, comment="开盘价"),
        sa.Column("high", sa.Numeric(10, 2), nullable=True, comment="最高价"),
        sa.Column("low", sa.Numeric(10, 2), nullable=True, comment="最低价"),
        sa.Column("close", sa.Numeric(10, 2), nullable=True, comment="收盘价"),
        sa.Column("volume", sa.BigInteger, nullable=True, comment="成交量"),
        sa.PrimaryKeyConstraint("code", "timestamp"),
        comment="分钟行情表",
    )

    op.create_index("ix_minute_quotes_code", "minute_quotes", ["code"])

    # 将 minute_quotes 转换为 TimescaleDB Hypertable
    op.execute(
        "SELECT create_hypertable('minute_quotes', 'timestamp', if_not_exists => TRUE)"
    )

    # 设置数据保留策略 (minute_quotes 保留 7 天)
    op.execute(
        "SELECT add_retention_policy('minute_quotes', INTERVAL '7 days', if_not_exists => TRUE)"
    )


def downgrade() -> None:
    # 删除保留策略
    op.execute("SELECT remove_retention_policy('minute_quotes', if_exists => TRUE)")

    # 删除表
    op.drop_table("minute_quotes")
    op.drop_table("daily_quotes")
    op.drop_table("watchlist")
    op.drop_table("stocks")
