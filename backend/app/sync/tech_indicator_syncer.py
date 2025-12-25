"""
技术指标同步器

负责计算和存储技术指标数据
"""

import asyncio
from datetime import date, timedelta
from decimal import Decimal
from typing import Callable

import polars as pl

from app.config import settings
from app.core.database import get_db_session
from app.core.logging import get_logger
from app.repositories.market_data_repository import MarketDataRepository
from app.repositories.stock_repository import StockRepository
from app.repositories.tech_indicator_repository import TechIndicatorRepository
from app.services.indicator_calculator import indicator_calculator

logger = get_logger(__name__)


class TechIndicatorSyncer:
    """技术指标同步器"""

    async def calculate_for_stock(
        self,
        code: str,
        end_date: date | None = None,
    ) -> int:
        """
        为单只股票计算技术指标

        Args:
            code: 股票代码
            end_date: 结束日期（默认今天）

        Returns:
            计算的记录数
        """
        if end_date is None:
            end_date = date.today()

        # 计算起始日期（需要足够的历史数据）
        history_days = settings.tech_indicator_history_days
        start_date = end_date - timedelta(days=history_days * 2)  # 多取一些保证有足够数据

        logger.debug("计算技术指标", code=code, start_date=str(start_date), end_date=str(end_date))

        try:
            async with get_db_session() as session:
                market_repo = MarketDataRepository(session)
                indicator_repo = TechIndicatorRepository(session)

                # 获取历史行情
                quotes = await market_repo.get_daily_quotes(
                    code=code,
                    start_date=start_date,
                    end_date=end_date,
                )

                if len(quotes) < 60:
                    logger.debug("数据量不足，跳过", code=code, count=len(quotes))
                    return 0

                # 转换为 DataFrame
                df = pl.DataFrame([
                    {
                        "trade_date": q.trade_date,
                        "open": float(q.open) if q.open else 0.0,
                        "high": float(q.high) if q.high else 0.0,
                        "low": float(q.low) if q.low else 0.0,
                        "close": float(q.close) if q.close else 0.0,
                        "volume": q.volume if q.volume else 0,
                    }
                    for q in quotes
                ])

                # 计算指标
                df = indicator_calculator.calculate_all(df)

                # 只保留最近的记录（避免重复计算太多历史数据）
                # 保留最近 30 天的数据
                df = df.sort("trade_date", descending=True).head(30)

                # 转换为记录
                records = []
                for row in df.iter_rows(named=True):
                    record = {
                        "code": code,
                        "trade_date": row["trade_date"],
                    }

                    # 添加指标字段
                    for field in [
                        "ma5", "ma10", "ma20", "ma60",
                        "macd_dif", "macd_dea", "macd_bar",
                        "rsi_14",
                        "kdj_k", "kdj_d", "kdj_j",
                        "boll_upper", "boll_middle", "boll_lower",
                        "cci", "atr_14", "obv",
                    ]:
                        value = row.get(field)
                        if value is not None and not (isinstance(value, float) and (value != value)):  # 检查 NaN
                            if field == "obv":
                                record[field] = int(value) if value else None
                            else:
                                record[field] = Decimal(str(round(value, 4))) if value else None
                        else:
                            record[field] = None

                    records.append(record)

                # 存储
                count = await indicator_repo.upsert_many(records)
                return count

        except Exception as e:
            logger.error("技术指标计算失败", code=code, error=str(e))
            return 0

    async def calculate_all(
        self,
        end_date: date | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict:
        """
        计算全市场技术指标

        Args:
            end_date: 结束日期
            progress_callback: 进度回调函数
        """
        if end_date is None:
            end_date = date.today()

        logger.info("开始计算全市场技术指标", end_date=str(end_date))

        try:
            # 获取所有股票代码
            async with get_db_session() as session:
                stock_repo = StockRepository(session)
                codes = await stock_repo.get_all_codes()

            total = len(codes)
            batch_size = settings.tech_indicator_batch_size
            total_synced = 0
            failed = 0

            logger.info("待计算股票数", total=total)

            # 分批处理
            for i in range(0, total, batch_size):
                batch_codes = codes[i:i + batch_size]

                # 并发计算一批
                tasks = [
                    self.calculate_for_stock(code, end_date)
                    for code in batch_codes
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in results:
                    if isinstance(result, Exception):
                        failed += 1
                    else:
                        total_synced += result

                # 回调进度
                if progress_callback:
                    progress_callback(min(i + batch_size, total), total)

                # 批次间休息
                if i + batch_size < total:
                    await asyncio.sleep(0.5)

            logger.info(
                "技术指标计算完成",
                total=total,
                synced=total_synced,
                failed=failed,
            )

            return {
                "status": "success",
                "total": total,
                "synced": total_synced,
                "failed": failed,
            }

        except Exception as e:
            logger.error("技术指标批量计算失败", error=str(e))
            raise

    async def calculate_watchlist(self, end_date: date | None = None) -> dict:
        """
        计算自选股技术指标

        Args:
            end_date: 结束日期
        """
        if end_date is None:
            end_date = date.today()

        logger.info("开始计算自选股技术指标", end_date=str(end_date))

        try:
            # 获取自选股代码
            from app.repositories.watchlist_repository import WatchlistRepository

            async with get_db_session() as session:
                watchlist_repo = WatchlistRepository(session)
                watchlist = await watchlist_repo.get_all()
                codes = [w.code for w in watchlist]

            if not codes:
                logger.info("无自选股")
                return {"status": "no_watchlist", "synced": 0}

            total_synced = 0
            for code in codes:
                count = await self.calculate_for_stock(code, end_date)
                total_synced += count

            logger.info("自选股技术指标计算完成", count=total_synced)
            return {"status": "success", "synced": total_synced}

        except Exception as e:
            logger.error("自选股技术指标计算失败", error=str(e))
            raise


# 全局单例
tech_indicator_syncer = TechIndicatorSyncer()
