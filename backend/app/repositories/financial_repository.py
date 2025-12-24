"""
财务数据仓库
"""

from datetime import date
from typing import Optional, Sequence

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial import FinancialStatement


class FinancialRepository:
    """财务数据仓库"""

    def __init__(self, session: AsyncSession):
        self.session = session

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
        批量更新或插入 (使用 merge)
        """
        # 注意：这里简单遍历 merge，对于大量数据可能需要优化
        for data in statements:
            # 转换为模型对象
            # 确保日期类型正确
            obj = FinancialStatement(**data)
            await self.session.merge(obj)
        
        await self.session.flush()
        return len(statements)
