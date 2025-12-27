"""
同步错误记录 Repository
"""

from datetime import datetime
from typing import Sequence

from sqlalchemy import select, desc, and_

from app.models.sync_error import SyncError
from app.repositories.base import BaseRepository
from sqlalchemy.ext.asyncio import AsyncSession


class SyncErrorRepository(BaseRepository[SyncError]):
    """同步错误记录访问层"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, SyncError)

    async def create_or_increment(
        self,
        task_name: str,
        target_code: str,
        error_type: str,
        error_message: str,
    ) -> SyncError:
        """
        创建新错误记录或增加重试次数

        如果相同 task_name + target_code 的错误已存在且未解决，则增加 retry_count
        否则创建新记录

        Args:
            task_name: 任务名称
            target_code: 目标代码
            error_type: 错误类型
            error_message: 错误信息

        Returns:
            同步错误记录
        """
        # 查找未解决的同类错误
        stmt = select(SyncError).where(
            and_(
                SyncError.task_name == task_name,
                SyncError.target_code == target_code,
                SyncError.resolved_at.is_(None),  # 未解决
            )
        )
        result = await self.session.execute(stmt)
        existing_error = result.scalar_one_or_none()

        if existing_error:
            # 增加重试次数
            existing_error.retry_count += 1
            existing_error.last_retry_at = datetime.utcnow()
            existing_error.error_type = error_type  # 更新错误类型
            existing_error.error_message = error_message  # 更新错误信息
            await self.session.flush()
            return existing_error
        else:
            # 创建新记录
            new_error = SyncError(
                task_name=task_name,
                target_code=target_code,
                error_type=error_type,
                error_message=error_message,
                retry_count=0,
                created_at=datetime.utcnow(),
            )
            self.session.add(new_error)
            await self.session.flush()
            return new_error

    async def mark_as_resolved(self, error_id: int) -> bool:
        """
        标记错误为已解决

        Args:
            error_id: 错误记录 ID

        Returns:
            是否成功标记
        """
        stmt = select(SyncError).where(SyncError.id == error_id)
        result = await self.session.execute(stmt)
        error = result.scalar_one_or_none()

        if error:
            error.resolved_at = datetime.utcnow()
            await self.session.flush()
            return True
        return False

    async def mark_batch_as_resolved(
        self, task_name: str, target_codes: list[str]
    ) -> int:
        """
        批量标记错误为已解决

        Args:
            task_name: 任务名称
            target_codes: 目标代码列表

        Returns:
            标记数量
        """
        stmt = select(SyncError).where(
            and_(
                SyncError.task_name == task_name,
                SyncError.target_code.in_(target_codes),
                SyncError.resolved_at.is_(None),
            )
        )
        result = await self.session.execute(stmt)
        errors = result.scalars().all()

        count = 0
        for error in errors:
            error.resolved_at = datetime.utcnow()
            count += 1

        await self.session.flush()
        return count

    async def get_unresolved_errors(
        self, task_name: str | None = None, max_retry_count: int | None = None
    ) -> Sequence[SyncError]:
        """
        获取未解决的错误

        Args:
            task_name: 任务名称过滤（可选）
            max_retry_count: 最大重试次数过滤（可选）

        Returns:
            未解决的错误列表
        """
        conditions = [SyncError.resolved_at.is_(None)]

        if task_name:
            conditions.append(SyncError.task_name == task_name)

        if max_retry_count is not None:
            conditions.append(SyncError.retry_count <= max_retry_count)

        stmt = (
            select(SyncError)
            .where(and_(*conditions))
            .order_by(desc(SyncError.created_at))
        )

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_retry_candidates(
        self, task_name: str, max_retry_count: int = 3
    ) -> Sequence[SyncError]:
        """
        获取需要重试的错误（重试次数未达上限）

        Args:
            task_name: 任务名称
            max_retry_count: 最大重试次数

        Returns:
            需要重试的错误列表
        """
        return await self.get_unresolved_errors(task_name, max_retry_count)

    async def get_stats(self, task_name: str | None = None) -> dict:
        """
        获取错误统计

        Args:
            task_name: 任务名称过滤（可选）

        Returns:
            统计信息字典
        """
        from sqlalchemy import func

        conditions = []
        if task_name:
            conditions.append(SyncError.task_name == task_name)

        # 总错误数
        total_stmt = select(func.count(SyncError.id))
        if conditions:
            total_stmt = total_stmt.where(and_(*conditions))
        total_result = await self.session.execute(total_stmt)
        total_count = total_result.scalar() or 0

        # 未解决错误数
        unresolved_conditions = conditions + [SyncError.resolved_at.is_(None)]
        unresolved_stmt = select(func.count(SyncError.id)).where(
            and_(*unresolved_conditions)
        )
        unresolved_result = await self.session.execute(unresolved_stmt)
        unresolved_count = unresolved_result.scalar() or 0

        # 已解决错误数
        resolved_count = total_count - unresolved_count

        return {
            "total": total_count,
            "unresolved": unresolved_count,
            "resolved": resolved_count,
            "resolution_rate": (
                resolved_count / total_count if total_count > 0 else 0.0
            ),
        }
