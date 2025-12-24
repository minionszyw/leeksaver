"""
财务数据模型

存储股票的季度财务报表数据
"""

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, Date, Numeric, Index, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class FinancialStatement(Base, TimestampMixin):
    """
    财务报表数据表

    存储股票的季度/年度财务指标
    """

    __tablename__ = "financial_statements"

    # 股票代码
    code: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="股票代码",
    )

    # 报告期截止日 (例如 2023-12-31)
    end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="报告期截止日",
    )

    # 报告发布日期
    pub_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="公告日期",
    )

    # 报告类型
    report_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="报告类型: 一季报/中报/三季报/年报",
    )

    # --- 核心指标 ---

    # 营业收入 (元)
    total_revenue: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(20, 2),
        nullable=True,
        comment="营业总收入",
    )

    # 归母净利润 (元)
    net_profit: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(20, 2),
        nullable=True,
        comment="归母净利润",
    )

    # 扣非净利润 (元)
    deduct_net_profit: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(20, 2),
        nullable=True,
        comment="扣非净利润",
    )

    # 经营现金流 (元)
    net_cash_flow_oper: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(20, 2),
        nullable=True,
        comment="经营活动产生的现金流量净额",
    )

    # --- 盈利能力 ---

    # 净资产收益率 (ROE, %)
    roe_weighted: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        comment="加权净资产收益率 (%)",
    )

    # 毛利率 (%)
    gross_profit_margin: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        comment="毛利率 (%)",
    )

    # 净利率 (%)
    net_profit_margin: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        comment="净利率 (%)",
    )

    # --- 成长能力 (同比 %) ---

    # 营收同比增长
    revenue_yoy: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        comment="营业收入同比增长率 (%)",
    )

    # 净利润同比增长
    net_profit_yoy: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        comment="归母净利润同比增长率 (%)",
    )

    # --- 偿债与运营 ---

    # 资产负债率 (%)
    debt_asset_ratio: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        comment="资产负债率 (%)",
    )

    # 每股收益 (元)
    eps: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        comment="基本每股收益",
    )

    # 每股净资产 (元)
    bps: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        comment="每股净资产",
    )

    # 复合主键
    __table_args__ = (
        PrimaryKeyConstraint("code", "end_date"),
        Index("ix_financial_code", "code"),
        Index("ix_financial_end_date", "end_date"),
        Index("ix_financial_report_type", "report_type"),
        {"comment": "财务报表数据表"},
    )

    def __repr__(self) -> str:
        return f"<FinancialStatement {self.code} {self.end_date} {self.report_type}>"
