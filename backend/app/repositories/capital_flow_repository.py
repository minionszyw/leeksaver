"""
资金面数据 Repository

包含北向资金、个股资金流向、龙虎榜、两融数据的数据访问
"""

from datetime import date
from typing import Sequence

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.capital_flow import (
    NorthboundFlow,
    StockFundFlow,
    DragonTiger,
    MarginTrade,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class NorthboundFlowRepository:
    """北向资金数据访问层"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_date(self, trade_date: date) -> NorthboundFlow | None:
        """获取指定日期的北向资金"""
        result = await self.session.execute(
            select(NorthboundFlow).where(NorthboundFlow.trade_date == trade_date)
        )
        return result.scalar_one_or_none()

    async def get_range(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
    ) -> Sequence[NorthboundFlow]:
        """获取日期范围内的北向资金"""
        query = select(NorthboundFlow)

        if start_date:
            query = query.where(NorthboundFlow.trade_date >= start_date)
        if end_date:
            query = query.where(NorthboundFlow.trade_date <= end_date)

        query = query.order_by(NorthboundFlow.trade_date.desc())

        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_latest_date(self) -> date | None:
        """获取最新交易日期"""
        result = await self.session.execute(
            select(func.max(NorthboundFlow.trade_date))
        )
        return result.scalar()

    async def upsert(self, data: dict) -> NorthboundFlow:
        """插入或更新北向资金数据"""
        stmt = insert(NorthboundFlow).values(**data)
        stmt = stmt.on_conflict_do_update(
            index_elements=["trade_date"],
            set_={
                "sh_net_inflow": stmt.excluded.sh_net_inflow,
                "sh_buy_amount": stmt.excluded.sh_buy_amount,
                "sh_sell_amount": stmt.excluded.sh_sell_amount,
                "sz_net_inflow": stmt.excluded.sz_net_inflow,
                "sz_buy_amount": stmt.excluded.sz_buy_amount,
                "sz_sell_amount": stmt.excluded.sz_sell_amount,
                "total_net_inflow": stmt.excluded.total_net_inflow,
            },
        )

        await self.session.execute(stmt)
        await self.session.commit()

        return await self.get_by_date(data["trade_date"])

    async def upsert_many(self, records: list[dict]) -> int:
        """批量插入或更新北向资金数据"""
        if not records:
            return 0

        stmt = insert(NorthboundFlow).values(records)
        stmt = stmt.on_conflict_do_update(
            index_elements=["trade_date"],
            set_={
                "sh_net_inflow": stmt.excluded.sh_net_inflow,
                "sh_buy_amount": stmt.excluded.sh_buy_amount,
                "sh_sell_amount": stmt.excluded.sh_sell_amount,
                "sz_net_inflow": stmt.excluded.sz_net_inflow,
                "sz_buy_amount": stmt.excluded.sz_buy_amount,
                "sz_sell_amount": stmt.excluded.sz_sell_amount,
                "total_net_inflow": stmt.excluded.total_net_inflow,
            },
        )

        await self.session.execute(stmt)
        await self.session.commit()

        logger.debug("批量更新北向资金", count=len(records))
        return len(records)


class StockFundFlowRepository:
    """个股资金流向数据访问层"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_code_date(self, code: str, trade_date: date) -> StockFundFlow | None:
        """获取指定股票指定日期的资金流向"""
        result = await self.session.execute(
            select(StockFundFlow).where(
                StockFundFlow.code == code,
                StockFundFlow.trade_date == trade_date,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_code(
        self,
        code: str,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
    ) -> Sequence[StockFundFlow]:
        """获取股票的资金流向历史"""
        query = select(StockFundFlow).where(StockFundFlow.code == code)

        if start_date:
            query = query.where(StockFundFlow.trade_date >= start_date)
        if end_date:
            query = query.where(StockFundFlow.trade_date <= end_date)

        query = query.order_by(StockFundFlow.trade_date.desc())

        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_date(
        self,
        trade_date: date,
        order_by: str = "main_net_inflow",
        limit: int | None = None,
    ) -> Sequence[StockFundFlow]:
        """获取指定日期的资金流向排行"""
        query = select(StockFundFlow).where(StockFundFlow.trade_date == trade_date)

        # 按指定字段排序
        if order_by == "main_net_inflow":
            query = query.order_by(StockFundFlow.main_net_inflow.desc().nullslast())
        elif order_by == "main_net_pct":
            query = query.order_by(StockFundFlow.main_net_pct.desc().nullslast())

        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def upsert_many(self, records: list[dict]) -> int:
        """批量插入或更新资金流向数据"""
        if not records:
            return 0

        stmt = insert(StockFundFlow).values(records)
        stmt = stmt.on_conflict_do_update(
            index_elements=["code", "trade_date"],
            set_={
                "main_net_inflow": stmt.excluded.main_net_inflow,
                "main_inflow": stmt.excluded.main_inflow,
                "main_outflow": stmt.excluded.main_outflow,
                "super_large_net": stmt.excluded.super_large_net,
                "large_net": stmt.excluded.large_net,
                "medium_net": stmt.excluded.medium_net,
                "small_net": stmt.excluded.small_net,
                "main_net_pct": stmt.excluded.main_net_pct,
            },
        )

        await self.session.execute(stmt)
        await self.session.commit()

        logger.debug("批量更新资金流向", count=len(records))
        return len(records)


class DragonTigerRepository:
    """龙虎榜数据访问层"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_date(
        self,
        trade_date: date,
        limit: int | None = None,
    ) -> Sequence[DragonTiger]:
        """获取指定日期的龙虎榜"""
        query = select(DragonTiger).where(DragonTiger.trade_date == trade_date)
        query = query.order_by(DragonTiger.net_amount.desc().nullslast())

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
    ) -> Sequence[DragonTiger]:
        """获取股票的龙虎榜历史"""
        query = select(DragonTiger).where(DragonTiger.code == code)

        if start_date:
            query = query.where(DragonTiger.trade_date >= start_date)
        if end_date:
            query = query.where(DragonTiger.trade_date <= end_date)

        query = query.order_by(DragonTiger.trade_date.desc())

        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_latest_date(self) -> date | None:
        """获取最新交易日期"""
        result = await self.session.execute(
            select(func.max(DragonTiger.trade_date))
        )
        return result.scalar()

    async def upsert_many(self, records: list[dict]) -> int:
        """批量插入或更新龙虎榜数据"""
        if not records:
            return 0

        stmt = insert(DragonTiger).values(records)
        stmt = stmt.on_conflict_do_update(
            index_elements=["code", "trade_date", "reason"],
            set_={
                "name": stmt.excluded.name,
                "buy_amount": stmt.excluded.buy_amount,
                "sell_amount": stmt.excluded.sell_amount,
                "net_amount": stmt.excluded.net_amount,
                "close": stmt.excluded.close,
                "change_pct": stmt.excluded.change_pct,
                "turnover_rate": stmt.excluded.turnover_rate,
            },
        )

        await self.session.execute(stmt)
        await self.session.commit()

        logger.debug("批量更新龙虎榜", count=len(records))
        return len(records)


class MarginTradeRepository:
    """两融数据访问层"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_code_date(self, code: str, trade_date: date) -> MarginTrade | None:
        """获取指定股票指定日期的两融数据"""
        result = await self.session.execute(
            select(MarginTrade).where(
                MarginTrade.code == code,
                MarginTrade.trade_date == trade_date,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_code(
        self,
        code: str,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
    ) -> Sequence[MarginTrade]:
        """获取股票的两融历史"""
        query = select(MarginTrade).where(MarginTrade.code == code)

        if start_date:
            query = query.where(MarginTrade.trade_date >= start_date)
        if end_date:
            query = query.where(MarginTrade.trade_date <= end_date)

        query = query.order_by(MarginTrade.trade_date.desc())

        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_date(
        self,
        trade_date: date,
        order_by: str = "rzjme",
        limit: int | None = None,
    ) -> Sequence[MarginTrade]:
        """获取指定日期的两融排行"""
        query = select(MarginTrade).where(MarginTrade.trade_date == trade_date)

        if order_by == "rzjme":
            query = query.order_by(MarginTrade.rzjme.desc().nullslast())
        elif order_by == "rzye":
            query = query.order_by(MarginTrade.rzye.desc().nullslast())

        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_latest_date(self) -> date | None:
        """获取最新交易日期"""
        result = await self.session.execute(
            select(func.max(MarginTrade.trade_date))
        )
        return result.scalar()

    async def upsert_many(self, records: list[dict]) -> int:
        """批量插入或更新两融数据"""
        if not records:
            return 0

        stmt = insert(MarginTrade).values(records)
        stmt = stmt.on_conflict_do_update(
            index_elements=["code", "trade_date"],
            set_={
                "rzye": stmt.excluded.rzye,
                "rzmre": stmt.excluded.rzmre,
                "rzche": stmt.excluded.rzche,
                "rzjme": stmt.excluded.rzjme,
                "rqye": stmt.excluded.rqye,
                "rqmcl": stmt.excluded.rqmcl,
                "rqchl": stmt.excluded.rqchl,
                "rzrqye": stmt.excluded.rzrqye,
            },
        )

        await self.session.execute(stmt)
        await self.session.commit()

        logger.debug("批量更新两融数据", count=len(records))
        return len(records)
