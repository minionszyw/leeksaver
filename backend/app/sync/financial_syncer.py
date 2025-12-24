"""
财务数据同步器

负责同步股票财务报表数据
"""

import asyncio
from typing import Callable

from app.config import settings
from app.core.database import get_db_session
from app.core.logging import get_logger
from app.datasources.akshare_adapter import akshare_adapter
from app.repositories.stock_repository import StockRepository
from app.repositories.financial_repository import FinancialRepository

logger = get_logger(__name__)


class FinancialSyncer:
    """财务数据同步器"""

    def __init__(self, batch_size: int | None = None):
        self.batch_size = batch_size or settings.sync_batch_size

    async def sync_single(self, code: str, limit: int = 8) -> int:
        """
        同步单只股票的财务数据

        Args:
            code: 股票代码
            limit: 获取最近 N 个报告期数据，默认 8 个（最近 2 年）

        Returns:
            同步的记录数
        """
        async with get_db_session() as session:
            repo = FinancialRepository(session)

            # 获取财务数据
            try:
                df = await akshare_adapter.get_financial_statements(code, limit)

                if len(df) == 0:
                    logger.debug("无财务数据", code=code)
                    return 0

                # 写入数据库
                records = df.to_dicts()
                count = await repo.upsert_many(records)

                logger.debug("同步财务数据完成", code=code, count=count)
                return count

            except Exception as e:
                logger.warning("同步财务数据失败", code=code, error=str(e))
                return 0

    async def sync_batch(
        self,
        codes: list[str],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict:
        """
        批量同步财务数据

        Args:
            codes: 股票代码列表
            progress_callback: 进度回调函数 (current, total)

        Returns:
            同步结果统计
        """
        total = len(codes)
        stats = {
            "total": total,
            "success": 0,
            "failed": 0,
            "records": 0,
        }

        logger.info("开始批量同步财务数据", total=total)

        for i, code in enumerate(codes):
            try:
                count = await self.sync_single(code)
                stats["records"] += count
                stats["success"] += 1
            except Exception as e:
                stats["failed"] += 1
                logger.warning("同步失败", code=code, error=str(e))

            # 进度回调
            if progress_callback:
                progress_callback(i + 1, total)

            # 每批次后休息 2 秒（财务数据为低频数据，降低请求频率）
            if (i + 1) % self.batch_size == 0:
                await asyncio.sleep(2)

        logger.info(
            "批量同步财务数据完成",
            success=stats["success"],
            failed=stats["failed"],
            records=stats["records"],
        )

        return stats

    async def sync_all(
        self,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict:
        """
        同步全市场财务数据（不包括 ETF）

        Args:
            progress_callback: 进度回调
        """
        async with get_db_session() as session:
            repo = StockRepository(session)
            # 只同步股票，不同步 ETF（ETF 无财务数据）
            codes = await repo.get_all_codes(asset_type="stock")

        logger.info("开始全市场财务数据同步", total=len(codes))
        return await self.sync_batch(codes, progress_callback)


# 全局单例
financial_syncer = FinancialSyncer()
