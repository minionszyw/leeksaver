"""
板块数据模型
"""

from datetime import date
from typing import Optional

from sqlalchemy import String, Date, Numeric, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Sector(Base, TimestampMixin):
    """
    板块基础信息表

    存储行业板块、概念板块、地域板块等基础信息
    """

    __tablename__ = "sectors"

    # 板块代码（主键）
    code: Mapped[str] = mapped_column(
        String(20),
        primary_key=True,
        comment="板块代码",
    )

    # 板块名称
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="板块名称",
    )

    # 板块类型
    sector_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="板块类型: industry-行业, concept-概念, region-地域",
    )

    # 板块级别
    level: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="板块级别: 1-一级行业, 2-二级行业, 3-三级行业",
    )

    # 父板块代码
    parent_code: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="父板块代码（用于多级行业分类）",
    )

    # 是否活跃
    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
        comment="是否活跃",
    )

    # 索引
    __table_args__ = (
        Index("ix_sectors_name", "name"),
        Index("ix_sectors_type", "sector_type"),
        Index("ix_sectors_parent", "parent_code"),
        {"comment": "板块基础信息表"},
    )

    def __repr__(self) -> str:
        return f"<Sector {self.code} {self.name}>"


class SectorQuote(Base, TimestampMixin):
    """
    板块行情数据表

    存储板块的日线行情数据
    """

    __tablename__ = "sector_quotes"

    # 主键 ID
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 板块代码
    sector_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="板块代码",
    )

    # 交易日期
    trade_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="交易日期",
    )

    # 板块指数
    index_value: Mapped[Optional[Numeric]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="板块指数",
    )

    # 涨跌幅
    change_pct: Mapped[Optional[Numeric]] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        comment="涨跌幅 (%)",
    )

    # 涨跌额
    change_amount: Mapped[Optional[Numeric]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="涨跌额",
    )

    # 总成交量
    total_volume: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="总成交量（手）",
    )

    # 总成交额
    total_amount: Mapped[Optional[Numeric]] = mapped_column(
        Numeric(20, 2),
        nullable=True,
        comment="总成交额（元）",
    )

    # 上涨家数
    rising_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="上涨家数",
    )

    # 下跌家数
    falling_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="下跌家数",
    )

    # 领涨股代码
    leading_stock: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="领涨股代码",
    )

    # 领涨股涨跌幅
    leading_stock_pct: Mapped[Optional[Numeric]] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        comment="领涨股涨跌幅 (%)",
    )

    # 索引
    __table_args__ = (
        Index("ix_sector_quotes_code", "sector_code"),
        Index("ix_sector_quotes_date", "trade_date"),
        # 复合唯一索引：同一板块同一日期只能有一条记录
        Index(
            "uq_sector_quotes_code_date",
            "sector_code",
            "trade_date",
            unique=True,
        ),
        {"comment": "板块行情数据表"},
    )

    def __repr__(self) -> str:
        return f"<SectorQuote {self.sector_code} {self.trade_date}>"
