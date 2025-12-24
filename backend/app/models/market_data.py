"""
行情数据模型

使用 TimescaleDB 存储时间序列数据
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, Date, Numeric, BigInteger, Index, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DailyQuote(Base):
    """
    日线行情表 (TimescaleDB Hypertable)

    存储股票/ETF 的日线行情数据
    """

    __tablename__ = "daily_quotes"

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

    # OHLC 数据
    open: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="开盘价",
    )
    high: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="最高价",
    )
    low: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="最低价",
    )
    close: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="收盘价",
    )

    # 成交量/成交额
    volume: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="成交量 (股)",
    )
    amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        comment="成交额 (元)",
    )

    # 涨跌
    change: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="涨跌额",
    )
    change_pct: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 4),
        nullable=True,
        comment="涨跌幅 (%)",
    )

    # 换手率
    turnover_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 4),
        nullable=True,
        comment="换手率 (%)",
    )

    # 复合主键
    __table_args__ = (
        PrimaryKeyConstraint("code", "trade_date"),
        Index("ix_daily_quotes_code", "code"),
        Index("ix_daily_quotes_trade_date", "trade_date"),
        {"comment": "日线行情表 (TimescaleDB Hypertable)"},
    )

    def __repr__(self) -> str:
        return f"<DailyQuote {self.code} {self.trade_date}>"


class MinuteQuote(Base):
    """
    分钟行情表 (TimescaleDB Hypertable)

    存储股票/ETF 的分钟级行情数据，仅保留短期数据
    """

    __tablename__ = "minute_quotes"

    # 股票代码
    code: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="股票代码",
    )

    # 时间戳
    timestamp: Mapped[datetime] = mapped_column(
        nullable=False,
        comment="时间戳",
    )

    # OHLC 数据
    open: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="开盘价",
    )
    high: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="最高价",
    )
    low: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="最低价",
    )
    close: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="收盘价",
    )

    # 成交量
    volume: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="成交量",
    )

    # 复合主键
    __table_args__ = (
        PrimaryKeyConstraint("code", "timestamp"),
        Index("ix_minute_quotes_code", "code"),
        {"comment": "分钟行情表 (TimescaleDB Hypertable)"},
    )

    def __repr__(self) -> str:
        return f"<MinuteQuote {self.code} {self.timestamp}>"
