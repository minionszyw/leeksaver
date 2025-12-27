"""
Repository 基类 - 提供通用的 CRUD 和批量操作
"""

from typing import TypeVar, Generic, Type, Any

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    """
    Repository 基类

    提供统一的批量操作、查询方法，消除代码重复
    所有 Repository 应继承此类
    """

    def __init__(self, session: AsyncSession, model: Type[ModelType]):
        """
        初始化 Repository

        Args:
            session: 数据库会话
            model: ORM 模型类
        """
        self.session = session
        self.model = model
        self.logger = get_logger(self.__class__.__name__)

    async def upsert_many(
        self,
        records: list[dict],
        conflict_columns: list[str],
        update_columns: list[str] | None = None,
    ) -> int:
        """
        高性能批量 upsert（使用 PostgreSQL insert on_conflict）

        性能优势:
        - 使用 insert on_conflict 比逐行 merge 快 10-50 倍
        - 自动分批处理，避免超过 PostgreSQL 参数限制（65535）
        - 一次性提交，减少数据库往返

        Args:
            records: 数据字典列表
            conflict_columns: 冲突检测的列（主键或唯一索引）
            update_columns: 需要更新的列（None 则更新所有非主键列）

        Returns:
            影响的行数

        Example:
            >>> repo = StockRepository(session)
            >>> records = [
            ...     {"code": "000001", "name": "平安银行", "industry": "银行"},
            ...     {"code": "000002", "name": "万科A", "industry": "房地产"},
            ... ]
            >>> count = await repo.upsert_many(
            ...     records,
            ...     conflict_columns=["code"],
            ...     update_columns=["name", "industry"]
            ... )
        """
        if not records:
            return 0

        # 分批处理（避免超过 PostgreSQL 参数限制 32767）
        # 每条记录约 10 个参数，32767 / 10 ≈ 3276，保守设置 3000
        batch_size = 3000
        total_count = 0

        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            stmt = insert(self.model).values(batch)

            # 自动推断更新列
            if update_columns is None:
                # 更新所有列，除了冲突检测列
                update_columns = [
                    col for col in batch[0].keys() if col not in conflict_columns
                ]

            # 构建 on_conflict_do_update
            update_dict = {col: getattr(stmt.excluded, col) for col in update_columns}

            stmt = stmt.on_conflict_do_update(
                index_elements=conflict_columns, set_=update_dict
            )

            await self.session.execute(stmt)
            total_count += len(batch)

        await self.session.flush()
        self.logger.debug("批量 upsert 完成", count=total_count)
        return total_count

    async def count_total(self) -> int:
        """
        高性能计数（使用 SQL COUNT 而非加载所有行）

        避免使用 len(scalars().all())，那会加载所有数据到内存
        """
        result = await self.session.execute(
            select(func.count()).select_from(self.model)
        )
        return result.scalar() or 0

    async def get_by_code(self, code: str) -> ModelType | None:
        """
        按代码查询单条记录

        假设模型有 code 字段，如果模型没有 code 字段，子类应重写此方法
        """
        if not hasattr(self.model, "code"):
            raise NotImplementedError(
                f"{self.model.__name__} 没有 code 字段，请在子类中重写 get_by_code 方法"
            )

        stmt = select(self.model).where(self.model.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, limit: int | None = None) -> list[ModelType]:
        """
        获取所有记录

        Args:
            limit: 返回数量限制

        Returns:
            记录列表
        """
        stmt = select(self.model)
        if limit:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())
