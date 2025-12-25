"""
估值数据 Repository
"""

from datetime import date
from typing import Sequence

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.valuation import DailyValuation
from app.core.logging import get_logger

logger = get_logger(__name__)


class ValuationRepository:
    """估值数据访问层"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_code_date(
        self,
        code: str,
        trade_date: date,
    ) -> DailyValuation | None:
        """获取指定股票指定日期的估值"""
        result = await self.session.execute(
            select(DailyValuation).where(
                DailyValuation.code == code,
                DailyValuation.trade_date == trade_date,
            )
        )
        return result.scalar_one_or_none()

    async def get_latest(self, code: str) -> DailyValuation | None:
        """获取股票最新估值"""
        result = await self.session.execute(
            select(DailyValuation)
            .where(DailyValuation.code == code)
            .order_by(DailyValuation.trade_date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_code(
        self,
        code: str,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int | None = None,
    ) -> Sequence[DailyValuation]:
        """获取股票的估值历史"""
        query = select(DailyValuation).where(DailyValuation.code == code)

        if start_date:
            query = query.where(DailyValuation.trade_date >= start_date)
        if end_date:
            query = query.where(DailyValuation.trade_date <= end_date)

        query = query.order_by(DailyValuation.trade_date.desc())

        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_date(
        self,
        trade_date: date,
        order_by: str = "pe_ttm",
        ascending: bool = True,
        limit: int | None = None,
    ) -> Sequence[DailyValuation]:
        """获取指定日期所有股票的估值"""
        query = select(DailyValuation).where(DailyValuation.trade_date == trade_date)

        # 排序
        if order_by == "pe_ttm":
            col = DailyValuation.pe_ttm
        elif order_by == "pb":
            col = DailyValuation.pb
        elif order_by == "dv_ttm":
            col = DailyValuation.dv_ttm
        elif order_by == "total_mv":
            col = DailyValuation.total_mv
        else:
            col = DailyValuation.pe_ttm

        if ascending:
            query = query.order_by(col.asc().nullslast())
        else:
            query = query.order_by(col.desc().nullslast())

        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_latest_date(self) -> date | None:
        """获取最新交易日期"""
        result = await self.session.execute(
            select(func.max(DailyValuation.trade_date))
        )
        return result.scalar()

    async def upsert_many(self, records: list[dict]) -> int:
        """批量插入或更新估值数据"""
        if not records:
            return 0

        stmt = insert(DailyValuation).values(records)
        stmt = stmt.on_conflict_do_update(
            index_elements=["code", "trade_date"],
            set_={
                "pe_ttm": stmt.excluded.pe_ttm,
                "pe_static": stmt.excluded.pe_static,
                "pb": stmt.excluded.pb,
                "ps_ttm": stmt.excluded.ps_ttm,
                "peg": stmt.excluded.peg,
                "total_mv": stmt.excluded.total_mv,
                "circ_mv": stmt.excluded.circ_mv,
                "dv_ttm": stmt.excluded.dv_ttm,
            },
        )

        await self.session.execute(stmt)
        await self.session.commit()

        logger.debug("批量更新估值数据", count=len(records))
        return len(records)
