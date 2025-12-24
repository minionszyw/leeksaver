"""添加财务报表数据表

Revision ID: 002
Revises: 001
Create Date: 2024-01-15

创建财务报表表:
- financial_statements: 股票季度/年度财务指标
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建 financial_statements 表
    op.create_table(
        "financial_statements",
        # 主键字段
        sa.Column("code", sa.String(10), nullable=False, comment="股票代码"),
        sa.Column("end_date", sa.Date, nullable=False, comment="报告期截止日"),

        # 基础信息
        sa.Column("pub_date", sa.Date, nullable=True, comment="公告日期"),
        sa.Column(
            "report_type",
            sa.String(20),
            nullable=False,
            comment="报告类型: 一季报/中报/三季报/年报",
        ),

        # 核心指标
        sa.Column("total_revenue", sa.Numeric(20, 2), nullable=True, comment="营业总收入"),
        sa.Column("net_profit", sa.Numeric(20, 2), nullable=True, comment="归母净利润"),
        sa.Column("deduct_net_profit", sa.Numeric(20, 2), nullable=True, comment="扣非净利润"),
        sa.Column(
            "net_cash_flow_oper",
            sa.Numeric(20, 2),
            nullable=True,
            comment="经营活动产生的现金流量净额",
        ),

        # 盈利能力指标
        sa.Column(
            "roe_weighted",
            sa.Numeric(10, 4),
            nullable=True,
            comment="加权净资产收益率 (%)",
        ),
        sa.Column("gross_profit_margin", sa.Numeric(10, 4), nullable=True, comment="毛利率 (%)"),
        sa.Column("net_profit_margin", sa.Numeric(10, 4), nullable=True, comment="净利率 (%)"),

        # 成长能力指标
        sa.Column(
            "revenue_yoy",
            sa.Numeric(10, 4),
            nullable=True,
            comment="营业收入同比增长率 (%)",
        ),
        sa.Column(
            "net_profit_yoy",
            sa.Numeric(10, 4),
            nullable=True,
            comment="归母净利润同比增长率 (%)",
        ),

        # 偿债与运营指标
        sa.Column(
            "debt_asset_ratio",
            sa.Numeric(10, 4),
            nullable=True,
            comment="资产负债率 (%)",
        ),
        sa.Column("eps", sa.Numeric(10, 4), nullable=True, comment="基本每股收益"),
        sa.Column("bps", sa.Numeric(10, 4), nullable=True, comment="每股净资产"),

        # 时间戳字段
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

        # 主键约束
        sa.PrimaryKeyConstraint("code", "end_date"),
        comment="财务报表数据表",
    )

    # 创建索引
    op.create_index("ix_financial_code", "financial_statements", ["code"])
    op.create_index("ix_financial_end_date", "financial_statements", ["end_date"])
    op.create_index("ix_financial_report_type", "financial_statements", ["report_type"])


def downgrade() -> None:
    # 删除表
    op.drop_table("financial_statements")
