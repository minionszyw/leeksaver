"""
估值数据模型

存储每日个股的估值指标（PE、PB、PEG、股息率等）
"""

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, Date, Numeric, Index, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DailyValuation(Base):
    """
    每日估值数据

    记录每日个股的估值指标
    """

    __tablename__ = "daily_valuations"

    # 股票代码
    code: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="股票代码",
    )

    # 交易日期
    trade_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="交易日期",
    )

    # 估值指标
    pe_ttm: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 4),
        nullable=True,
        comment="市盈率（TTM）",
    )
    pe_static: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 4),
        nullable=True,
        comment="市盈率（静态）",
    )
    pb: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 4),
        nullable=True,
        comment="市净率",
    )
    ps_ttm: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 4),
        nullable=True,
        comment="市销率（TTM）",
    )
    peg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 4),
        nullable=True,
        comment="PEG",
    )

    # 市值
    total_mv: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        comment="总市值（亿元）",
    )
    circ_mv: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        comment="流通市值（亿元）",
    )

    # 股息率
    dv_ttm: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 4),
        nullable=True,
        comment="股息率（TTM）（%）",
    )

    # 复合主键
    __table_args__ = (
        PrimaryKeyConstraint("code", "trade_date"),
        Index("ix_daily_valuations_code", "code"),
        Index("ix_daily_valuations_date", "trade_date"),
        {"comment": "每日估值数据表"},
    )

    def __repr__(self) -> str:
        return f"<DailyValuation {self.code} {self.trade_date}>"
