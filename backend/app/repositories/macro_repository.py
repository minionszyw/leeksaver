"""
宏观经济指标仓库
"""

from typing import Optional, Sequence
from datetime import date

from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert

from app.models.macro import MacroIndicator
from app.repositories.base import BaseRepository


class MacroIndicatorRepository(BaseRepository[MacroIndicator]):
    """宏观经济指标仓库"""

    def __init__(self, session):
        super().__init__(session, MacroIndicator)

    async def upsert(self, data: dict) -> MacroIndicator:
        """
        插入或更新宏观指标

        根据 indicator_name + period 唯一键
        """
        stmt = insert(MacroIndicator).values(**data)
        stmt = stmt.on_conflict_do_update(
            index_elements=["indicator_name", "period"],
            set_={
                "value": stmt.excluded.value,
                "yoy_rate": stmt.excluded.yoy_rate,
                "mom_rate": stmt.excluded.mom_rate,
                "unit": stmt.excluded.unit,
                "updated_at": stmt.excluded.updated_at,
            },
        ).returning(MacroIndicator)

        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def upsert_many(self, records: list[dict]) -> int:
        """
        批量插入或更新
        """
        if not records:
            return 0

        stmt = insert(MacroIndicator).values(records)
        stmt = stmt.on_conflict_do_update(
            index_elements=["indicator_name", "period"],
            set_={
                "value": stmt.excluded.value,
                "yoy_rate": stmt.excluded.yoy_rate,
                "mom_rate": stmt.excluded.mom_rate,
                "unit": stmt.excluded.unit,
                "updated_at": stmt.excluded.updated_at,
            },
        )

        result = await self.session.execute(stmt)
        return result.rowcount

    async def get_by_category(
        self,
        category: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Sequence[MacroIndicator]:
        """按分类查询"""
        stmt = select(MacroIndicator).where(
            MacroIndicator.indicator_category == category
        )

        if start_date:
            stmt = stmt.where(MacroIndicator.period >= start_date)
        if end_date:
            stmt = stmt.where(MacroIndicator.period <= end_date)

        stmt = stmt.order_by(MacroIndicator.period.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()
