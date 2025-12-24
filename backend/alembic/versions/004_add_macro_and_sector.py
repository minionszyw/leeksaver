"""添加宏观经济和板块数据表

Revision ID: 004
Revises: 003
Create Date: 2024-01-17

创建数据表:
- macro_indicators: 宏观经济指标
- sectors: 板块基础信息
- sector_quotes: 板块行情数据
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建 macro_indicators 表
    op.create_table(
        "macro_indicators",
        # 主键
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),

        # 指标信息
        sa.Column(
            "indicator_name",
            sa.String(50),
            nullable=False,
            comment="指标名称: GDP, CPI, PPI, PMI, M2等",
        ),
        sa.Column(
            "indicator_category",
            sa.String(50),
            nullable=False,
            comment="指标分类: 国民经济, 价格指数, 货币供应等",
        ),

        # 周期信息
        sa.Column("period", sa.Date, nullable=False, comment="统计周期"),
        sa.Column(
            "period_type",
            sa.String(20),
            nullable=False,
            comment="周期类型: 月度, 季度, 年度",
        ),

        # 指标值
        sa.Column("value", sa.Numeric(20, 4), nullable=True, comment="指标值"),
        sa.Column("yoy_rate", sa.Numeric(10, 4), nullable=True, comment="同比增长率(%)"),
        sa.Column("mom_rate", sa.Numeric(10, 4), nullable=True, comment="环比增长率(%)"),
        sa.Column("unit", sa.String(50), nullable=True, comment="数据单位"),

        # 时间戳
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

        comment="宏观经济指标表",
    )

    # 创建宏观指标索引
    op.create_index("ix_macro_indicators_name", "macro_indicators", ["indicator_name"])
    op.create_index("ix_macro_indicators_period", "macro_indicators", ["period"])
    op.create_index("ix_macro_indicators_category", "macro_indicators", ["indicator_category"])
    op.create_index(
        "uq_macro_indicators_name_period",
        "macro_indicators",
        ["indicator_name", "period"],
        unique=True,
    )

    # 创建 sectors 表
    op.create_table(
        "sectors",
        # 主键
        sa.Column("code", sa.String(20), primary_key=True, comment="板块代码"),

        # 板块信息
        sa.Column("name", sa.String(100), nullable=False, comment="板块名称"),
        sa.Column(
            "sector_type",
            sa.String(20),
            nullable=False,
            comment="板块类型: industry/concept/region",
        ),
        sa.Column("level", sa.Integer, nullable=True, comment="板块级别"),
        sa.Column("parent_code", sa.String(20), nullable=True, comment="父板块代码"),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False, comment="是否活跃"),

        # 时间戳
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

        comment="板块基础信息表",
    )

    # 创建板块索引
    op.create_index("ix_sectors_name", "sectors", ["name"])
    op.create_index("ix_sectors_type", "sectors", ["sector_type"])
    op.create_index("ix_sectors_parent", "sectors", ["parent_code"])

    # 创建 sector_quotes 表
    op.create_table(
        "sector_quotes",
        # 主键
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),

        # 基本信息
        sa.Column("sector_code", sa.String(20), nullable=False, comment="板块代码"),
        sa.Column("trade_date", sa.Date, nullable=False, comment="交易日期"),

        # 行情数据
        sa.Column("index_value", sa.Numeric(10, 2), nullable=True, comment="板块指数"),
        sa.Column("change_pct", sa.Numeric(10, 4), nullable=True, comment="涨跌幅(%)"),
        sa.Column("change_amount", sa.Numeric(10, 2), nullable=True, comment="涨跌额"),
        sa.Column("total_volume", sa.Integer, nullable=True, comment="总成交量(手)"),
        sa.Column("total_amount", sa.Numeric(20, 2), nullable=True, comment="总成交额(元)"),

        # 涨跌统计
        sa.Column("rising_count", sa.Integer, nullable=True, comment="上涨家数"),
        sa.Column("falling_count", sa.Integer, nullable=True, comment="下跌家数"),

        # 领涨股
        sa.Column("leading_stock", sa.String(10), nullable=True, comment="领涨股代码"),
        sa.Column("leading_stock_pct", sa.Numeric(10, 4), nullable=True, comment="领涨股涨跌幅(%)"),

        # 时间戳
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

        comment="板块行情数据表",
    )

    # 创建板块行情索引
    op.create_index("ix_sector_quotes_code", "sector_quotes", ["sector_code"])
    op.create_index("ix_sector_quotes_date", "sector_quotes", ["trade_date"])
    op.create_index(
        "uq_sector_quotes_code_date",
        "sector_quotes",
        ["sector_code", "trade_date"],
        unique=True,
    )


def downgrade() -> None:
    # 删除表
    op.drop_table("sector_quotes")
    op.drop_table("sectors")
    op.drop_table("macro_indicators")
