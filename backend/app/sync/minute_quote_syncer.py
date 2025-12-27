"""
分钟线行情同步器
"""

import asyncio
from datetime import datetime, timedelta
from typing import Callable

from app.config import settings
from app.core.database import get_db_session
from app.core.logging import get_logger
from app.datasources.akshare_adapter import akshare_adapter
from app.repositories.stock_repository import WatchlistRepository
from app.repositories.market_data_repository import MinuteQuoteRepository
from app.repositories.sync_error_repository import SyncErrorRepository

logger = get_logger(__name__)


class MinuteQuoteSyncer:
    """分钟线行情同步器 (主要用于 L2 自选股同步)"""

    async def sync_single(
        self,
        code: str,
        period: str = "1",
    ) -> int:
        """同步单只股票分钟线行情"""
        async with get_db_session() as session:
            repo = MinuteQuoteRepository(session)
            
            # 获取最新时间戳，用于去重或增量过滤（如果接口支持）
            # AkShare stock_zh_a_minute 返回最近的数据，通常只需覆盖即可
            
            try:
                df = await akshare_adapter.get_minute_quotes(code, period=period)

                if len(df) == 0:
                    return 0

                # 写入数据库 (upsert)
                records = df.to_dicts()
                count = await repo.upsert_many(records)

                return count

            except Exception as e:
                logger.warning("同步分钟行情失败", code=code, error=str(e))
                return 0

    async def sync_watchlist(
        self,
        period: str = "1",
        max_concurrent: int = 5,
    ) -> dict:
        """同步自选股分钟行情"""
        async with get_db_session() as session:
            repo = WatchlistRepository(session)
            codes = await repo.get_codes()

        if not codes:
            return {"total": 0, "success": 0, "failed": 0, "records": 0}

        stats = {"total": len(codes), "success": 0, "failed": 0, "records": 0}
        semaphore = asyncio.Semaphore(max_concurrent)

        async def sync_with_semaphore(code: str):
            async with semaphore:
                try:
                    count = await self.sync_single(code, period=period)
                    stats["records"] += count
                    stats["success"] += 1
                except Exception:
                    stats["failed"] += 1

        tasks = [sync_with_semaphore(code) for code in codes]
        await asyncio.gather(*tasks)

        return stats


# 全局单例
minute_quote_syncer = MinuteQuoteSyncer()
