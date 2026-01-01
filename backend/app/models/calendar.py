from datetime import date
from sqlalchemy import Date, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TradingCalendar(Base):
    """
    交易日历模型
    用于记录 A 股交易日，处理法定节假日
    """
    __tablename__ = "trading_calendar"

    trade_date: Mapped[date] = mapped_column(Date, primary_key=True, comment="交易日期")
    is_open: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否开市")

    def __repr__(self) -> str:
        return f"<TradingCalendar {self.trade_date} is_open={self.is_open}>"
