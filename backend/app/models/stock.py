"""
股票/ETF 基础信息模型
"""

from datetime import date
from typing import Optional

from sqlalchemy import String, Date, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Stock(Base, TimestampMixin):
    """
    股票/ETF 基础信息表

    存储 A 股市场的股票和 ETF 基本信息
    """

    __tablename__ = "stocks"

    # 股票代码 (主键)
    code: Mapped[str] = mapped_column(
        String(10),
        primary_key=True,
        comment="股票代码，如 000001, 600519",
    )

    # 股票名称
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="股票名称",
    )

    # 市场
    market: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="市场: SH-上海, SZ-深圳, BJ-北京",
    )

    # 资产类型
    asset_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="stock",
        comment="类型: stock-股票, etf-ETF",
    )

    # 行业
    industry: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="所属行业",
    )

    # 上市日期
    list_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="上市日期",
    )

    # 是否活跃 (是否正常交易)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="是否正常交易",
    )

    # 索引
    __table_args__ = (
        Index("ix_stocks_name", "name"),
        Index("ix_stocks_market", "market"),
        Index("ix_stocks_asset_type", "asset_type"),
        Index("ix_stocks_industry", "industry"),
        {"comment": "股票/ETF 基础信息表"},
    )

    def __repr__(self) -> str:
        return f"<Stock {self.code} {self.name}>"


class Watchlist(Base, TimestampMixin):
    """
    自选股表

    存储用户的自选股列表
    """

    __tablename__ = "watchlist"

    # 主键 ID
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 股票代码
    code: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="股票代码",
    )

    # 排序顺序
    sort_order: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="排序顺序",
    )

    # 备注
    note: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="备注",
    )

    __table_args__ = (
        Index("ix_watchlist_code", "code", unique=True),
        {"comment": "自选股表"},
    )

    def __repr__(self) -> str:
        return f"<Watchlist {self.code}>"
