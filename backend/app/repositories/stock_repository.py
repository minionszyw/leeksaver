"""
股票数据 Repository
"""

from datetime import date
from typing import Sequence

from sqlalchemy import select, update, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import Stock, Watchlist
from app.core.logging import get_logger

logger = get_logger(__name__)


class StockRepository:
    """股票数据访问层"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_code(self, code: str) -> Stock | None:
        """根据代码获取股票"""
        result = await self.session.execute(
            select(Stock).where(Stock.code == code)
        )
        return result.scalar_one_or_none()

    async def get_all(self, active_only: bool = True) -> Sequence[Stock]:
        """获取所有股票"""
        query = select(Stock)
        if active_only:
            query = query.where(Stock.is_active == True)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def search(
        self, keyword: str, limit: int = 10
    ) -> Sequence[Stock]:
        """搜索股票 (按代码或名称)"""
        result = await self.session.execute(
            select(Stock)
            .where(
                (Stock.code.contains(keyword)) | (Stock.name.contains(keyword))
            )
            .where(Stock.is_active == True)
            .limit(limit)
        )
        return result.scalars().all()

    async def upsert_many(self, stocks: list[dict]) -> int:
        """批量插入或更新股票"""
        if not stocks:
            return 0

        stmt = insert(Stock).values(stocks)
        stmt = stmt.on_conflict_do_update(
            index_elements=["code"],
            set_={
                "name": stmt.excluded.name,
                "market": stmt.excluded.market,
                "asset_type": stmt.excluded.asset_type,
                "industry": stmt.excluded.industry,
                "is_active": stmt.excluded.is_active,
            },
        )

        await self.session.execute(stmt)
        await self.session.commit()

        logger.info("批量更新股票", count=len(stocks))
        return len(stocks)

    async def get_codes_by_market(self, market: str) -> list[str]:
        """获取指定市场的所有股票代码"""
        result = await self.session.execute(
            select(Stock.code)
            .where(Stock.market == market)
            .where(Stock.is_active == True)
        )
        return [row[0] for row in result.all()]

    async def get_all_codes(self, asset_type: str | None = None) -> list[str]:
        """获取所有股票代码"""
        query = select(Stock.code).where(Stock.is_active == True)
        if asset_type:
            query = query.where(Stock.asset_type == asset_type)
        result = await self.session.execute(query)
        return [row[0] for row in result.all()]


class WatchlistRepository:
    """自选股数据访问层"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self) -> Sequence[Watchlist]:
        """获取所有自选股"""
        result = await self.session.execute(
            select(Watchlist).order_by(Watchlist.sort_order)
        )
        return result.scalars().all()

    async def get_codes(self) -> list[str]:
        """获取所有自选股代码"""
        result = await self.session.execute(select(Watchlist.code))
        return [row[0] for row in result.all()]

    async def add(self, code: str, note: str | None = None) -> Watchlist:
        """添加自选股"""
        # 获取当前最大排序号
        result = await self.session.execute(
            select(Watchlist.sort_order).order_by(Watchlist.sort_order.desc()).limit(1)
        )
        max_order = result.scalar() or 0

        watchlist = Watchlist(code=code, sort_order=max_order + 1, note=note)
        self.session.add(watchlist)
        await self.session.commit()
        await self.session.refresh(watchlist)

        logger.info("添加自选股", code=code)
        return watchlist

    async def remove(self, code: str) -> bool:
        """移除自选股"""
        result = await self.session.execute(
            delete(Watchlist).where(Watchlist.code == code)
        )
        await self.session.commit()

        deleted = result.rowcount > 0
        if deleted:
            logger.info("移除自选股", code=code)
        return deleted

    async def exists(self, code: str) -> bool:
        """检查是否已在自选"""
        result = await self.session.execute(
            select(Watchlist.id).where(Watchlist.code == code)
        )
        return result.scalar_one_or_none() is not None
