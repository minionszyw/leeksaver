"""
日线行情同步器
"""

import asyncio
from datetime import date, timedelta
from typing import Callable

from app.config import settings
from app.core.database import get_db_session
from app.core.logging import get_logger
from app.datasources.akshare_adapter import akshare_adapter
from app.repositories.stock_repository import StockRepository, WatchlistRepository
from app.repositories.market_data_repository import MarketDataRepository

logger = get_logger(__name__)


class DailyQuoteSyncer:
    """日线行情同步器"""

    def __init__(self, batch_size: int | None = None):
        self.batch_size = batch_size or settings.sync_batch_size

    async def sync_single(
        self,
        code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> int:
        """
        同步单只股票日线行情

        Args:
            code: 股票代码
            start_date: 起始日期 (默认从最新记录开始)
            end_date: 结束日期 (默认今天)

        Returns:
            同步的记录数
        """
        async with get_db_session() as session:
            repo = MarketDataRepository(session)

            # 确定起始日期
            if start_date is None:
                latest_date = await repo.get_latest_trade_date(code)
                if latest_date:
                    start_date = latest_date + timedelta(days=1)
                else:
                    # 无历史数据，获取最近 2 年
                    start_date = date.today() - timedelta(days=730)

            if end_date is None:
                end_date = date.today()

            # 如果起始日期已经是今天或之后，无需同步
            if start_date > end_date:
                logger.debug("数据已是最新", code=code)
                return 0

            # 获取行情数据
            try:
                df = await akshare_adapter.get_daily_quotes(code, start_date, end_date)

                if len(df) == 0:
                    logger.debug("无新数据", code=code)
                    return 0

                # 写入数据库
                records = df.to_dicts()
                count = await repo.upsert_many(records)

                logger.debug("同步日线行情完成", code=code, count=count)
                return count

            except Exception as e:
                logger.warning("同步日线行情失败", code=code, error=str(e))
                return 0

    async def sync_batch(
        self,
        codes: list[str],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict:
        """
        批量同步日线行情

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

        logger.info("开始批量同步日线行情", total=total)

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

            # 每批次后短暂休息
            if (i + 1) % self.batch_size == 0:
                await asyncio.sleep(1)

        logger.info(
            "批量同步日线行情完成",
            success=stats["success"],
            failed=stats["failed"],
            records=stats["records"],
        )

        return stats

    async def sync_all(
        self,
        asset_type: str | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict:
        """
        同步全市场日线行情 (L1)

        Args:
            asset_type: 资产类型筛选 (stock/etf)
            progress_callback: 进度回调
        """
        async with get_db_session() as session:
            repo = StockRepository(session)
            codes = await repo.get_all_codes(asset_type)

        logger.info("开始全市场同步", total=len(codes), asset_type=asset_type)
        return await self.sync_batch(codes, progress_callback)

    async def sync_watchlist(
        self,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict:
        """
        同步自选股日线行情 (L2)
        """
        async with get_db_session() as session:
            repo = WatchlistRepository(session)
            codes = await repo.get_codes()

        if not codes:
            logger.info("自选股为空，跳过同步")
            return {"total": 0, "success": 0, "failed": 0, "records": 0}

        logger.info("开始同步自选股", total=len(codes))
        return await self.sync_batch(codes, progress_callback)


# 全局单例
daily_quote_syncer = DailyQuoteSyncer()
