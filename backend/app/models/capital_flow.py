"""
资金面数据模型

包含北向资金、个股资金流向、龙虎榜、两融数据
"""

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, Date, Numeric, BigInteger, Integer, Index, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class NorthboundFlow(Base, TimestampMixin):
    """
    北向资金（沪股通+深股通）

    记录每日北向资金净流入情况
    """

    __tablename__ = "northbound_flows"

    # 交易日期 (主键)
    trade_date: Mapped[date] = mapped_column(
        Date,
        primary_key=True,
        comment="交易日期",
    )

    # 沪股通
    sh_net_inflow: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        comment="沪股通净流入（亿元）",
    )
    sh_buy_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        comment="沪股通买入金额（亿元）",
    )
    sh_sell_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        comment="沪股通卖出金额（亿元）",
    )

    # 深股通
    sz_net_inflow: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        comment="深股通净流入（亿元）",
    )
    sz_buy_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        comment="深股通买入金额（亿元）",
    )
    sz_sell_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        comment="深股通卖出金额（亿元）",
    )

    # 汇总
    total_net_inflow: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        comment="北向资金净流入合计（亿元）",
    )

    __table_args__ = ({"comment": "北向资金表"},)

    def __repr__(self) -> str:
        return f"<NorthboundFlow {self.trade_date} {self.total_net_inflow}>"


class StockFundFlow(Base):
    """
    个股主力资金流向

    记录每日个股的主力资金净流入情况
    """

    __tablename__ = "stock_fund_flows"

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

    # 主力资金（超大单+大单）
    main_net_inflow: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        comment="主力净流入（万元）",
    )
    main_inflow: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        comment="主力流入（万元）",
    )
    main_outflow: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        comment="主力流出（万元）",
    )

    # 超大单（>100万）
    super_large_net: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        comment="超大单净流入（万元）",
    )

    # 大单（20-100万）
    large_net: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        comment="大单净流入（万元）",
    )

    # 中单（4-20万）
    medium_net: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        comment="中单净流入（万元）",
    )

    # 小单（<4万）
    small_net: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        comment="小单净流入（万元）",
    )

    # 主力净占比
    main_net_pct: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 4),
        nullable=True,
        comment="主力净占比（%）",
    )

    # 复合主键
    __table_args__ = (
        PrimaryKeyConstraint("code", "trade_date"),
        Index("ix_stock_fund_flows_code", "code"),
        Index("ix_stock_fund_flows_date", "trade_date"),
        {"comment": "个股主力资金流向表"},
    )

    def __repr__(self) -> str:
        return f"<StockFundFlow {self.code} {self.trade_date}>"


class DragonTiger(Base, TimestampMixin):
    """
    龙虎榜数据

    记录当日上榜的股票及买卖金额
    """

    __tablename__ = "dragon_tiger"

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

    # 上榜原因
    reason: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="上榜原因",
    )

    # 龙虎榜成交
    buy_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        comment="龙虎榜买入额（万元）",
    )
    sell_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        comment="龙虎榜卖出额（万元）",
    )
    net_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        comment="龙虎榜净买入（万元）",
    )

    # 当日行情
    close: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="收盘价",
    )
    change_pct: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 4),
        nullable=True,
        comment="涨跌幅（%）",
    )
    turnover_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 4),
        nullable=True,
        comment="换手率（%）",
    )

    __table_args__ = (
        Index("ix_dragon_tiger_code", "code"),
        Index("ix_dragon_tiger_date", "trade_date"),
        Index("uq_dragon_tiger", "code", "trade_date", "reason", unique=True),
        {"comment": "龙虎榜数据表"},
    )

    def __repr__(self) -> str:
        return f"<DragonTiger {self.code} {self.trade_date} {self.reason}>"


class MarginTrade(Base):
    """
    两融数据（融资融券）

    记录每日个股的融资融券余额及变动
    """

    __tablename__ = "margin_trades"

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

    # 融资数据
    rzye: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        comment="融资余额（元）",
    )
    rzmre: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        comment="融资买入额（元）",
    )
    rzche: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        comment="融资偿还额（元）",
    )
    rzjme: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        comment="融资净买入（元）",
    )

    # 融券数据
    rqye: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        comment="融券余额（元）",
    )
    rqyl: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="融券余量（股）",
    )
    rqmcl: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="融券卖出量（股）",
    )
    rqchl: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="融券偿还量（股）",
    )

    # 两融汇总
    rzrqye: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2),
        nullable=True,
        comment="融资融券余额（元）",
    )

    # 复合主键
    __table_args__ = (
        PrimaryKeyConstraint("code", "trade_date"),
        Index("ix_margin_trades_code", "code"),
        Index("ix_margin_trades_date", "trade_date"),
        {"comment": "融资融券数据表"},
    )

    def __repr__(self) -> str:
        return f"<MarginTrade {self.code} {self.trade_date}>"
