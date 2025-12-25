"""
市场情绪数据模型

包含市场情绪指标和涨停股票详情
"""

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, Date, Numeric, BigInteger, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class MarketSentiment(Base, TimestampMixin):
    """
    市场情绪指标（每日）

    记录每日市场涨跌统计、连板情况、换手率分布等
    """

    __tablename__ = "market_sentiments"

    # 交易日期 (主键)
    trade_date: Mapped[date] = mapped_column(
        Date,
        primary_key=True,
        comment="交易日期",
    )

    # 涨跌统计
    rising_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="上涨家数",
    )
    falling_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="下跌家数",
    )
    flat_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="平盘家数",
    )
    limit_up_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="涨停家数",
    )
    limit_down_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="跌停家数",
    )

    # 涨跌比
    advance_decline_ratio: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 4),
        nullable=True,
        comment="涨跌比（上涨/下跌）",
    )

    # 连板统计
    continuous_limit_up_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="连板家数（2板及以上）",
    )
    max_continuous_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="最高连板天数",
    )
    highest_board_stock: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="最高连板股票代码",
    )

    # 换手率分布
    turnover_gt_10_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="换手率>10%家数",
    )
    turnover_5_10_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="换手率5-10%家数",
    )
    turnover_lt_1_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="换手率<1%家数",
    )
    avg_turnover_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 4),
        nullable=True,
        comment="全市场平均换手率（%）",
    )

    # 市场总成交
    total_volume: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="市场总成交量（手）",
    )
    total_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(20, 2),
        nullable=True,
        comment="市场总成交额（亿元）",
    )

    __table_args__ = ({"comment": "市场情绪指标表"},)

    def __repr__(self) -> str:
        return f"<MarketSentiment {self.trade_date}>"


class LimitUpStock(Base, TimestampMixin):
    """
    涨停股票详情

    记录每日涨停股票的详细信息
    """

    __tablename__ = "limit_up_stocks"

    # 自增主键
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # 股票代码
    code: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="股票代码",
    )

    # 股票名称
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="股票名称",
    )

    # 交易日期
    trade_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="交易日期",
    )

    # 涨停信息
    limit_up_time: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="首次涨停时间（HH:MM:SS）",
    )
    open_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="开板次数",
    )
    continuous_days: Mapped[int] = mapped_column(
        Integer,
        default=1,
        comment="连板天数",
    )

    # 板块
    industry: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="所属行业",
    )
    concept: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="涨停概念（多个用逗号分隔）",
    )

    # 成交数据
    turnover_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 4),
        nullable=True,
        comment="换手率（%）",
    )
    amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        comment="成交额（万元）",
    )

    # 封单
    seal_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        comment="封单金额（万元）",
    )

    __table_args__ = (
        Index("ix_limit_up_stocks_date", "trade_date"),
        Index("ix_limit_up_stocks_code", "code"),
        Index("uq_limit_up_code_date", "code", "trade_date", unique=True),
        {"comment": "涨停股票详情表"},
    )

    def __repr__(self) -> str:
        return f"<LimitUpStock {self.code} {self.trade_date}>"
