"""
行情数据 Repository
"""

from datetime import date, timedelta
from typing import Sequence

from sqlalchemy import select, delete, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_data import DailyQuote, MinuteQuote
from app.repositories.base import BaseRepository
from app.core.logging import get_logger

logger = get_logger(__name__)


class MarketDataRepository(BaseRepository[DailyQuote]):
    """行情数据访问层"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, DailyQuote)

    async def get_daily_quotes(
        self,
        code: str,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
    ) -> Sequence[DailyQuote]:
        """
        获取日线行情

        Args:
            code: 股票代码
            start_date: 起始日期
            end_date: 结束日期
            limit: 返回数量限制
        """
        query = select(DailyQuote).where(DailyQuote.code == code)

        if start_date:
            query = query.where(DailyQuote.trade_date >= start_date)
        if end_date:
            query = query.where(DailyQuote.trade_date <= end_date)

        query = query.order_by(DailyQuote.trade_date.desc())

        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return result.scalars().all()


class MinuteQuoteRepository(BaseRepository[MinuteQuote]):
    """分钟行情数据访问层"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, MinuteQuote)

    async def get_latest_timestamp(self, code: str) -> "datetime | None":
        """获取股票最新分钟线时间戳"""
        from datetime import datetime
        result = await self.session.execute(
            select(func.max(MinuteQuote.timestamp)).where(MinuteQuote.code == code)
        )
        return result.scalar()

    async def upsert_many(self, quotes: list[dict]) -> int:
        """批量插入或更新分钟行情"""
        count = await super().upsert_many(
            records=quotes,
            conflict_columns=["code", "timestamp"],
        )
        await self.session.commit()
        return count
    async def get_latest_quote(self, code: str) -> DailyQuote | None:
        """获取最新日线行情"""
        result = await self.session.execute(
            select(DailyQuote)
            .where(DailyQuote.code == code)
            .order_by(DailyQuote.trade_date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_trade_date(self, code: str) -> date | None:
        """获取股票最新交易日期"""
        result = await self.session.execute(
            select(func.max(DailyQuote.trade_date)).where(DailyQuote.code == code)
        )
        return result.scalar()

    async def upsert_many(self, quotes: list[dict]) -> int:
        """
        批量插入或更新日线行情（使用高性能 BaseRepository）

        Args:
            quotes: 行情数据列表，每个元素包含 code, trade_date 等字段
        """
        count = await super().upsert_many(
            records=quotes,
            conflict_columns=["code", "trade_date"],
        )
        await self.session.commit()
        return count

    async def delete_old_data(self, before_date: date) -> int:
        """删除指定日期之前的数据"""
        result = await self.session.execute(
            delete(DailyQuote).where(DailyQuote.trade_date < before_date)
        )
        await self.session.commit()

        deleted = result.rowcount
        if deleted:
            logger.info("清理历史数据", before_date=before_date.isoformat(), count=deleted)
        return deleted

    async def get_quote_count(self, code: str) -> int:
        """获取股票的行情记录数"""
        result = await self.session.execute(
            select(func.count()).where(DailyQuote.code == code)
        )
        return result.scalar() or 0

    async def check_data_freshness(self, code: str, max_age_days: int = 1) -> bool:
        """
        检查数据新鲜度

        Args:
            code: 股票代码
            max_age_days: 最大允许天数

        Returns:
            True 表示数据新鲜，False 表示需要更新
        """
        latest_date = await self.get_latest_trade_date(code)
        if latest_date is None:
            return False

        # 计算工作日差异 (简化处理，不考虑节假日)
        today = date.today()
        days_diff = (today - latest_date).days

        # 周末不算过期
        if today.weekday() >= 5:  # 周六或周日
            max_age_days += 2

        return days_diff <= max_age_days

    async def get_market_quotes(
        self,
        trade_date: date,
    ) -> Sequence[DailyQuote]:
        """
        获取指定日期全市场的日线行情

        Args:
            trade_date: 交易日期

        Returns:
            该交易日所有股票的行情数据
        """
        query = select(DailyQuote).where(DailyQuote.trade_date == trade_date)
        result = await self.session.execute(query)
        return result.scalars().all()
