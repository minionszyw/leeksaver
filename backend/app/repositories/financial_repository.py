"""
财务数据仓库
"""

from datetime import date
from typing import Optional, Sequence

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial import FinancialStatement, OperationData
from app.repositories.base import BaseRepository


class FinancialRepository(BaseRepository[FinancialStatement]):
    """财务数据仓库"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, FinancialStatement)

    async def get_latest_statement(self, code: str) -> Optional[FinancialStatement]:
        """获取最新的财务报表"""
        stmt = (
            select(FinancialStatement)
            .where(FinancialStatement.code == code)
            .order_by(desc(FinancialStatement.end_date))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_statements(
        self, code: str, limit: int = 4
    ) -> Sequence[FinancialStatement]:
        """获取最近的财务报表列表"""
        stmt = (
            select(FinancialStatement)
            .where(FinancialStatement.code == code)
            .order_by(desc(FinancialStatement.end_date))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def upsert(self, statement: FinancialStatement) -> FinancialStatement:
        """更新或插入财务报表"""
        await self.session.merge(statement)
        await self.session.flush()
        return statement

    async def upsert_many(self, statements: list[dict]) -> int:
        """
        批量更新或插入（使用高性能 insert on_conflict）
        """
        if not statements:
            return 0

        return await super().upsert_many(
            records=statements,
            conflict_columns=["code", "end_date"],
        )


class OperationDataRepository(BaseRepository[OperationData]):
    """经营数据仓库"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, OperationData)

    async def upsert_many(self, records: list[dict]) -> int:
        """
        批量更新或插入经营数据
        
        主键/约束: (code, period, metric_name)
        """
        if not records:
            return 0

        return await super().upsert_many(
            records=records,
            conflict_columns=["code", "period", "metric_name"],
        )