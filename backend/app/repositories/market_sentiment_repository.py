"""
市场情绪数据 Repository

包含市场情绪指标和涨停股票详情的数据访问
"""

from datetime import date
from typing import Sequence

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_sentiment import MarketSentiment, LimitUpStock
from app.core.logging import get_logger

logger = get_logger(__name__)


class MarketSentimentRepository:
    """市场情绪数据访问层"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_date(self, trade_date: date) -> MarketSentiment | None:
        """获取指定日期的市场情绪"""
        result = await self.session.execute(
            select(MarketSentiment).where(MarketSentiment.trade_date == trade_date)
        )
        return result.scalar_one_or_none()

    async def get_range(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
    ) -> Sequence[MarketSentiment]:
        """获取日期范围内的市场情绪"""
        query = select(MarketSentiment)

        if start_date:
            query = query.where(MarketSentiment.trade_date >= start_date)
        if end_date:
            query = query.where(MarketSentiment.trade_date <= end_date)

        query = query.order_by(MarketSentiment.trade_date.desc())

        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_latest_date(self) -> date | None:
        """获取最新交易日期"""
        result = await self.session.execute(
            select(func.max(MarketSentiment.trade_date))
        )
        return result.scalar()

    async def upsert(self, data: dict) -> MarketSentiment:
        """插入或更新市场情绪数据"""
        stmt = insert(MarketSentiment).values(**data)
        stmt = stmt.on_conflict_do_update(
            index_elements=["trade_date"],
            set_={
                "rising_count": stmt.excluded.rising_count,
                "falling_count": stmt.excluded.falling_count,
                "flat_count": stmt.excluded.flat_count,
                "limit_up_count": stmt.excluded.limit_up_count,
                "limit_down_count": stmt.excluded.limit_down_count,
                "advance_decline_ratio": stmt.excluded.advance_decline_ratio,
                "continuous_limit_up_count": stmt.excluded.continuous_limit_up_count,
                "max_continuous_days": stmt.excluded.max_continuous_days,
                "highest_board_stock": stmt.excluded.highest_board_stock,
                "turnover_gt_10_count": stmt.excluded.turnover_gt_10_count,
                "turnover_5_10_count": stmt.excluded.turnover_5_10_count,
                "turnover_lt_1_count": stmt.excluded.turnover_lt_1_count,
                "avg_turnover_rate": stmt.excluded.avg_turnover_rate,
                "total_volume": stmt.excluded.total_volume,
                "total_amount": stmt.excluded.total_amount,
            },
        )

        await self.session.execute(stmt)
        await self.session.commit()

        return await self.get_by_date(data["trade_date"])


class LimitUpStockRepository:
    """涨停股票数据访问层"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_date(
        self,
        trade_date: date,
        order_by: str = "continuous_days",
        limit: int | None = None,
    ) -> Sequence[LimitUpStock]:
        """获取指定日期的涨停股票"""
        query = select(LimitUpStock).where(LimitUpStock.trade_date == trade_date)

        if order_by == "continuous_days":
            query = query.order_by(
                LimitUpStock.continuous_days.desc(),
                LimitUpStock.limit_up_time.asc().nullslast(),
            )
        elif order_by == "limit_up_time":
            query = query.order_by(LimitUpStock.limit_up_time.asc().nullslast())
        elif order_by == "amount":
            query = query.order_by(LimitUpStock.amount.desc().nullslast())

        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_code(
        self,
        code: str,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
    ) -> Sequence[LimitUpStock]:
        """获取股票的涨停历史"""
        query = select(LimitUpStock).where(LimitUpStock.code == code)

        if start_date:
            query = query.where(LimitUpStock.trade_date >= start_date)
        if end_date:
            query = query.where(LimitUpStock.trade_date <= end_date)

        query = query.order_by(LimitUpStock.trade_date.desc())

        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_continuous_limit_up(
        self,
        trade_date: date,
        min_days: int = 2,
    ) -> Sequence[LimitUpStock]:
        """获取连板股票（指定连板天数以上）"""
        result = await self.session.execute(
            select(LimitUpStock)
            .where(
                LimitUpStock.trade_date == trade_date,
                LimitUpStock.continuous_days >= min_days,
            )
            .order_by(LimitUpStock.continuous_days.desc())
        )
        return result.scalars().all()

    async def upsert_many(self, records: list[dict]) -> int:
        """批量插入或更新涨停股票数据"""
        if not records:
            return 0

        stmt = insert(LimitUpStock).values(records)
        stmt = stmt.on_conflict_do_update(
            index_elements=["code", "trade_date"],
            set_={
                "name": stmt.excluded.name,
                "limit_up_time": stmt.excluded.limit_up_time,
                "open_count": stmt.excluded.open_count,
                "continuous_days": stmt.excluded.continuous_days,
                "industry": stmt.excluded.industry,
                "concept": stmt.excluded.concept,
                "turnover_rate": stmt.excluded.turnover_rate,
                "amount": stmt.excluded.amount,
                "seal_amount": stmt.excluded.seal_amount,
            },
        )

        await self.session.execute(stmt)
        await self.session.commit()

        logger.debug("批量更新涨停股票", count=len(records))
        return len(records)
