"""
技术指标预计算模型

存储预计算的技术指标，支持快速选股查询
"""

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, Date, Numeric, BigInteger, Index, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TechIndicator(Base):
    """
    预计算的技术指标

    存储每日每个股票的技术指标值，用于快速选股筛选
    """

    __tablename__ = "tech_indicators"

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

    # ==================== 均线 (MA) ====================
    ma5: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="5日均线",
    )
    ma10: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="10日均线",
    )
    ma20: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="20日均线",
    )
    ma60: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="60日均线",
    )

    # ==================== MACD ====================
    macd_dif: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        comment="MACD DIF",
    )
    macd_dea: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        comment="MACD DEA",
    )
    macd_bar: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        comment="MACD Bar (柱状)",
    )

    # ==================== RSI ====================
    rsi_14: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 4),
        nullable=True,
        comment="14日RSI",
    )

    # ==================== KDJ ====================
    kdj_k: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 4),
        nullable=True,
        comment="KDJ K值",
    )
    kdj_d: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 4),
        nullable=True,
        comment="KDJ D值",
    )
    kdj_j: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 4),
        nullable=True,
        comment="KDJ J值",
    )

    # ==================== 布林带 ====================
    boll_upper: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="布林带上轨",
    )
    boll_middle: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="布林带中轨",
    )
    boll_lower: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="布林带下轨",
    )

    # ==================== CCI ====================
    cci: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        comment="CCI指标",
    )

    # ==================== ATR ====================
    atr_14: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        comment="14日ATR",
    )

    # ==================== OBV ====================
    obv: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="OBV（累积成交量）",
    )

    # 复合主键
    __table_args__ = (
        PrimaryKeyConstraint("code", "trade_date"),
        Index("ix_tech_indicators_code", "code"),
        Index("ix_tech_indicators_date", "trade_date"),
        # 支持金叉死叉筛选的索引
        Index("ix_tech_indicators_macd", "trade_date", "macd_bar"),
        # 支持 RSI 超买超卖筛选
        Index("ix_tech_indicators_rsi", "trade_date", "rsi_14"),
        {"comment": "技术指标预计算表"},
    )

    def __repr__(self) -> str:
        return f"<TechIndicator {self.code} {self.trade_date}>"
