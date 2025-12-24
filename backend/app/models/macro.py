"""
宏观经济数据模型
"""

from datetime import date
from typing import Optional

from sqlalchemy import String, Date, Numeric, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class MacroIndicator(Base, TimestampMixin):
    """
    宏观经济指标表

    存储中国宏观经济数据（GDP、CPI、PMI、M2 等）
    """

    __tablename__ = "macro_indicators"

    # 主键 ID
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 指标名称
    indicator_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="指标名称: GDP, CPI, PPI, PMI, M2, 社融, 外汇储备等",
    )

    # 指标分类
    indicator_category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="指标分类: 国民经济, 价格指数, 货币供应, 对外经济等",
    )

    # 统计周期
    period: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="统计周期（月度/季度）",
    )

    # 周期类型
    period_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="周期类型: 月度, 季度, 年度",
    )

    # 指标值
    value: Mapped[Optional[Numeric]] = mapped_column(
        Numeric(20, 4),
        nullable=True,
        comment="指标值",
    )

    # 同比增长率
    yoy_rate: Mapped[Optional[Numeric]] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        comment="同比增长率 (%)",
    )

    # 环比增长率
    mom_rate: Mapped[Optional[Numeric]] = mapped_column(
        Numeric(10, 4),
        nullable=True,
        comment="环比增长率 (%)",
    )

    # 数据单位
    unit: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="数据单位: 亿元, 百分点, 点等",
    )

    # 索引
    __table_args__ = (
        Index("ix_macro_indicators_name", "indicator_name"),
        Index("ix_macro_indicators_period", "period"),
        Index("ix_macro_indicators_category", "indicator_category"),
        # 复合唯一索引：同一指标的同一周期只能有一条记录
        Index(
            "uq_macro_indicators_name_period",
            "indicator_name",
            "period",
            unique=True,
        ),
        {"comment": "宏观经济指标表"},
    )

    def __repr__(self) -> str:
        return f"<MacroIndicator {self.indicator_name} {self.period}>"
