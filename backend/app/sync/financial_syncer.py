"""
财务数据同步器

负责同步股票财务报表数据及经营数据
"""

import asyncio
from datetime import date
from typing import Callable

from app.config import settings
from app.core.database import get_db_session
from app.core.logging import get_logger
from app.datasources.akshare_adapter import akshare_adapter
from app.repositories.stock_repository import StockRepository
from app.repositories.financial_repository import FinancialRepository, OperationDataRepository

logger = get_logger(__name__)


class FinancialSyncer:
    """财务数据同步器"""

    def __init__(self, batch_size: int | None = None):
        self.batch_size = batch_size or settings.sync_batch_size

    async def sync_single(self, code: str, limit: int = 8) -> int:
        """
        同步单只股票的财务数据
        """
        async with get_db_session() as session:
            repo = FinancialRepository(session)

            try:
                df = await akshare_adapter.get_financial_statements(code, limit)

                if len(df) == 0:
                    logger.debug("无财务数据", code=code)
                    return 0

                records = df.to_dicts()
                count = await repo.upsert_many(records)

                logger.debug("同步财务数据完成", code=code, count=count)
                return count

            except Exception as e:
                logger.warning("同步财务数据失败", code=code, error=str(e))
                return 0

    async def sync_operation_data(self, code: str) -> int:
        """
        同步单只股票的经营数据（目前使用基础资料接口）
        """
        async with get_db_session() as session:
            repo = OperationDataRepository(session)

            try:
                df = await akshare_adapter.get_operation_data(code)

                if len(df) == 0:
                    logger.debug("无经营数据", code=code)
                    return 0

                # 将基础资料数据转换为 OperationData KV 结构
                today_str = date.today().strftime("%Y-%m-%d")
                records = []
                for row in df.iter_rows(named=True):
                    records.append({
                        "code": code,
                        "period": today_str, # 基础资料使用当天日期作为报告期
                        "metric_name": row["metric_name"],
                        "metric_category": "basic_info",
                        "metric_value_text": row["metric_value_text"],
                        "source": "AkShare-个股资料"
                    })

                if not records:
                    return 0

                count = await repo.upsert_many(records)
                logger.debug("同步经营数据完成", code=code, count=count)
                return count

            except Exception as e:
                logger.warning("同步经营数据失败", code=code, error=str(e))
                return 0

    async def sync_batch(
        self,
        codes: list[str],
        sync_type: str = "financial", # "financial" or "operation"
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict:
        """
        批量同步数据
        """
        total = len(codes)
        stats = {
            "total": total,
            "success": 0,
            "failed": 0,
            "records": 0,
        }

        logger.info(f"开始批量同步{sync_type}数据", total=total)

        for i, code in enumerate(codes):
            try:
                if sync_type == "financial":
                    count = await self.sync_single(code)
                else:
                    count = await self.sync_operation_data(code)
                
                stats["records"] += count
                stats["success"] += 1
            except Exception as e:
                stats["failed"] += 1
                logger.warning(f"同步{sync_type}失败", code=code, error=str(e))

            if progress_callback:
                progress_callback(i + 1, total)

            if (i + 1) % self.batch_size == 0:
                await asyncio.sleep(1)

        logger.info(
            f"批量同步{sync_type}数据完成",
            success=stats["success"],
            failed=stats["failed"],
            records=stats["records"],
        )

        return stats

    async def sync_all(self, sync_type: str = "financial") -> dict:
        """
        同步全市场数据
        """
        async with get_db_session() as session:
            repo = StockRepository(session)
            codes = await repo.get_all_codes(asset_type="stock")

        return await self.sync_batch(codes, sync_type=sync_type)


# 全局单例
financial_syncer = FinancialSyncer()
