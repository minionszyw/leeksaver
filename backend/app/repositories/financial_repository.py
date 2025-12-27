"""
财务数据仓库
"""

from datetime import date
from typing import Optional, Sequence

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial import FinancialStatement
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

        性能提升：使用 BaseRepository.upsert_many() 替代逐行 merge
        预期性能提升：10-50 倍（取决于数据量）

        Args:
            statements: 财务报表数据列表

        Returns:
            插入/更新的记录数
        """
        if not statements:
            return 0

        # 调用父类的高性能 upsert_many
        # 财务报表的主键是 (code, end_date)
        return await super().upsert_many(
            records=statements,
            conflict_columns=["code", "end_date"],
            # update_columns=None 会自动更新所有非主键列
        )
