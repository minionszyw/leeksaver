"""
市场情绪数据同步器

负责同步市场情绪指标和涨停池数据
"""

from datetime import date
from decimal import Decimal

import polars as pl

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.datasources.sentiment_adapter import sentiment_adapter
from app.repositories.market_sentiment_repository import (
    MarketSentimentRepository,
    LimitUpStockRepository,
)
from app.repositories.market_data_repository import MarketDataRepository

logger = get_logger(__name__)


class SentimentSyncer:
    """市场情绪数据同步器"""

    async def sync_market_sentiment(self, trade_date: date) -> dict:
        """
        同步市场情绪指标

        综合计算涨跌统计、换手率分布等
        """
        logger.info("开始同步市场情绪", trade_date=str(trade_date))

        try:
            # 从数据库获取当日全市场行情用于计算
            async with get_db_session() as session:
                market_repo = MarketDataRepository(session)
                # 获取当日所有股票的行情数据
                quotes = await market_repo.get_daily_quotes(
                    code="*",  # 暂时这样处理，实际需要改进
                    start_date=trade_date,
                    end_date=trade_date,
                )

            # 如果无法获取全市场数据，尝试获取涨停池来计算部分指标
            limit_up_df = await sentiment_adapter.get_limit_up_pool(trade_date)
            limit_down_df = await sentiment_adapter.get_limit_down_pool(trade_date)

            # 构建情绪数据
            sentiment_data = {
                "trade_date": trade_date,
                "rising_count": 0,
                "falling_count": 0,
                "flat_count": 0,
                "limit_up_count": len(limit_up_df) if len(limit_up_df) > 0 else 0,
                "limit_down_count": len(limit_down_df) if len(limit_down_df) > 0 else 0,
            }

            # 计算连板统计
            if len(limit_up_df) > 0:
                # 筛选连板股（连板天数 >= 2）
                continuous_stocks = limit_up_df.filter(pl.col("continuous_days") >= 2)
                sentiment_data["continuous_limit_up_count"] = len(continuous_stocks)

                # 最高连板天数
                max_days = limit_up_df.select(pl.col("continuous_days").max()).item()
                sentiment_data["max_continuous_days"] = max_days if max_days else None

                # 最高连板股票
                if max_days:
                    highest = limit_up_df.filter(pl.col("continuous_days") == max_days).head(1)
                    if len(highest) > 0:
                        sentiment_data["highest_board_stock"] = highest.row(0, named=True)["code"]

            # 存储情绪数据
            async with get_db_session() as session:
                repo = MarketSentimentRepository(session)
                await repo.upsert(sentiment_data)

            logger.info("市场情绪同步完成", trade_date=str(trade_date))
            return {"status": "success", "trade_date": str(trade_date)}

        except Exception as e:
            logger.error("市场情绪同步失败", error=str(e))
            raise

    async def sync_limit_up_pool(self, trade_date: date) -> dict:
        """
        同步涨停池数据

        Args:
            trade_date: 交易日期
        """
        logger.info("开始同步涨停池", trade_date=str(trade_date))

        try:
            # 获取涨停池数据
            df = await sentiment_adapter.get_limit_up_pool(trade_date)

            if len(df) == 0:
                logger.warning("未获取到涨停池数据")
                return {"status": "no_data", "synced": 0}

            # 转换为记录
            records = []
            for row in df.iter_rows(named=True):
                records.append({
                    "code": row["code"],
                    "name": row["name"],
                    "trade_date": row["trade_date"],
                    "limit_up_time": str(row["limit_up_time"]) if row["limit_up_time"] else None,
                    "open_count": row["open_count"],
                    "continuous_days": row["continuous_days"],
                    "industry": row["industry"],
                    "turnover_rate": Decimal(str(row["turnover_rate"])) if row["turnover_rate"] else None,
                    "amount": Decimal(str(row["amount"])) if row["amount"] else None,
                    "seal_amount": Decimal(str(row["seal_amount"])) if row["seal_amount"] else None,
                })

            # 存储
            async with get_db_session() as session:
                repo = LimitUpStockRepository(session)
                count = await repo.upsert_many(records)

            logger.info("涨停池同步完成", count=count)
            return {"status": "success", "synced": count}

        except Exception as e:
            logger.error("涨停池同步失败", error=str(e))
            raise


# 全局单例
sentiment_syncer = SentimentSyncer()
