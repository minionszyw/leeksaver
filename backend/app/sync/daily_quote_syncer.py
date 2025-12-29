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
from app.repositories.sync_error_repository import SyncErrorRepository
from app.models.sync_error import SyncError

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
        asset_type: str = "stock",
    ) -> int:
        """
        同步单只股票或 ETF 日线行情

        Args:
            code: 标的代码
            start_date: 起始日期
            end_date: 结束日期
            asset_type: 资产类型 (stock/etf)
        """
        async with get_db_session() as session:
            repo = MarketDataRepository(session)

            # 确定起始日期
            if start_date is None:
                latest_date = await repo.get_latest_trade_date(code)
                quote_count = await repo.get_quote_count(code)
                
                # 如果完全没数据，或者数据量太少（可能只有快照），强制补全 2 年历史
                if not latest_date or quote_count < 10:
                    start_date = date.today() - timedelta(days=730)
                else:
                    start_date = latest_date + timedelta(days=1)

            if end_date is None:
                end_date = date.today()

            # 如果起始日期已经是今天或之后，无需同步
            if start_date > end_date:
                logger.debug("数据已是最新", code=code)
                return 0

            # 获取行情数据
            try:
                df = await akshare_adapter.get_daily_quotes(
                    code, start_date, end_date, asset_type=asset_type
                )

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
        max_concurrent: int = 10,
    ) -> dict:
        """
        批量同步日线行情
        """
        total = len(codes)
        stats = {
            "total": total,
            "success": 0,
            "failed": 0,
            "records": 0,
        }

        # 批量获取资产类型以优化性能
        async with get_db_session() as session:
            stock_repo = StockRepository(session)
            asset_types = await stock_repo.get_asset_types_map(codes)

        logger.info("开始并发批量同步日线行情", total=total, max_concurrent=max_concurrent)

        # 使用 Semaphore 限制并发数
        semaphore = asyncio.Semaphore(max_concurrent)
        completed = 0
        success_codes = []

        async def sync_with_semaphore(code: str):
            nonlocal completed
            async with semaphore:
                try:
                    asset_type = asset_types.get(code, "stock")
                    count = await self.sync_single(code, asset_type=asset_type)
                    stats["records"] += count
                    stats["success"] += 1
                    success_codes.append(code)
                except Exception as e:
                    stats["failed"] += 1
                    await self._record_sync_error(
                        task_name="sync_daily_quotes",
                        target_code=code,
                        error=e
                    )
                    logger.warning("同步失败", code=code, error=str(e))
                finally:
                    completed += 1
                    if progress_callback:
                        progress_callback(completed, total)

        # 并发执行
        tasks = [sync_with_semaphore(code) for code in codes]
        await asyncio.gather(*tasks)

        if success_codes:
            await self._mark_errors_resolved(success_codes)

        return stats

    async def _record_sync_error(
        self, task_name: str, target_code: str, error: Exception
    ):
        """
        记录同步错误到数据库

        Args:
            task_name: 任务名称
            target_code: 目标股票代码
            error: 异常对象
        """
        try:
            async with get_db_session() as session:
                repo = SyncErrorRepository(session)
                await repo.create_or_increment(
                    task_name=task_name,
                    target_code=target_code,
                    error_type=type(error).__name__,
                    error_message=str(error),
                )
                await session.commit()
        except Exception as e:
            logger.error(f"记录同步错误失败: {e}")

    async def _mark_errors_resolved(self, target_codes: list[str]):
        """
        标记成功同步的股票错误为已解决

        Args:
            target_codes: 股票代码列表
        """
        try:
            async with get_db_session() as session:
                repo = SyncErrorRepository(session)
                count = await repo.mark_batch_as_resolved(
                    task_name="sync_daily_quotes",
                    target_codes=target_codes
                )
                if count > 0:
                    await session.commit()
                    logger.info(f"标记 {count} 个错误为已解决")
        except Exception as e:
            logger.error(f"标记错误为已解决失败: {e}")

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

    async def sync_all_realtime(self) -> dict:
        """
        极速同步：一次性获取全市场实时行情快照并入库
        解决单标的抓取过慢的问题
        """
        logger.info("开始极速全市场行情同步")
        try:
            df = await akshare_adapter.get_all_stock_quotes()
            if len(df) == 0:
                return {"status": "no_data", "synced": 0}
            
            records = df.to_dicts()
            async with get_db_session() as session:
                repo = MarketDataRepository(session)
                # 分批 upsert 防止 SQL 过长
                batch_size = 500
                total_synced = 0
                for i in range(0, len(records), batch_size):
                    batch = records[i:i+batch_size]
                    count = await repo.upsert_many(batch)
                    total_synced += count
                await session.commit()
            
            logger.info("极速全市场行情同步完成", count=total_synced)
            return {"status": "success", "synced": total_synced}
        except Exception as e:
            logger.error("极速全市场行情同步失败", error=str(e))
            return {"status": "failed", "error": str(e)}

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
