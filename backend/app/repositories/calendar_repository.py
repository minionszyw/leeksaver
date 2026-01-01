from datetime import date
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calendar import TradingCalendar
from app.repositories.base import BaseRepository


class CalendarRepository(BaseRepository[TradingCalendar]):
    """
    交易日历仓库
    """

    def __init__(self, session: AsyncSession):
        super().__init__(TradingCalendar, session)

    async def is_trading_day(self, check_date: date) -> bool:
        """
        判断指定日期是否为交易日
        """
        stmt = select(TradingCalendar).where(
            TradingCalendar.trade_date == check_date,
            TradingCalendar.is_open == True
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_latest_trading_day(self, before_date: date | None = None) -> date | None:
        """
        获取指定日期之前的最近一个交易日
        """
        if before_date is None:
            before_date = date.today()
            
        stmt = (
            select(func.max(TradingCalendar.trade_date))
            .where(
                TradingCalendar.trade_date < before_date,
                TradingCalendar.is_open == True
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar()

    async def get_trading_days(self, start_date: date, end_date: date) -> list[date]:
        """
        获取指定范围内的所有交易日
        """
        stmt = (
            select(TradingCalendar.trade_date)
            .where(
                TradingCalendar.trade_date >= start_date,
                TradingCalendar.trade_date <= end_date,
                TradingCalendar.is_open == True
            )
            .order_by(TradingCalendar.trade_date.asc())
        )
        result = await self.session.execute(stmt)
        return [row[0] for row in result.fetchall()]
