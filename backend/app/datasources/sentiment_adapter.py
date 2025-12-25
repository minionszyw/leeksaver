"""
市场情绪数据源适配器

封装 AkShare 市场情绪相关接口（涨跌统计、涨停池等）
"""

import asyncio
from datetime import date
from decimal import Decimal

import akshare as ak
import polars as pl

from app.core.logging import get_logger
from app.datasources.rate_limiter import akshare_limiter

logger = get_logger(__name__)


class SentimentAdapter:
    """
    市场情绪数据源适配器

    封装涨跌统计、涨停池、连板统计等接口
    """

    def __init__(self):
        self._loop = asyncio.get_event_loop()

    async def _run_sync(self, func, *args, **kwargs):
        """在线程池中运行同步函数"""
        async with akshare_limiter:
            return await asyncio.to_thread(func, *args, **kwargs)

    async def get_limit_up_pool(self, trade_date: date) -> pl.DataFrame:
        """
        获取涨停池数据

        使用 stock_zt_pool_em 接口
        """
        logger.info("获取涨停池数据", trade_date=str(trade_date))

        try:
            df = await self._run_sync(
                ak.stock_zt_pool_em,
                date=trade_date.strftime("%Y%m%d"),
            )

            if df.empty:
                logger.warning("涨停池数据为空", trade_date=str(trade_date))
                return pl.DataFrame()

            result = pl.from_pandas(df)

            # 规范化列名
            # 原始列名：序号,代码,名称,涨跌幅,最新价,成交额,流通市值,总市值,换手率,
            # 封板资金,首次封板时间,最后封板时间,炸板次数,涨停统计,连板数,所属行业
            result = result.select(
                pl.col("代码").alias("code"),
                pl.col("名称").alias("name"),
                pl.col("首次封板时间").alias("limit_up_time"),
                pl.col("炸板次数").alias("open_count"),
                pl.col("连板数").alias("continuous_days"),
                pl.col("所属行业").alias("industry"),
                pl.col("换手率").alias("turnover_rate"),
                pl.col("成交额").alias("amount"),
                pl.col("封板资金").alias("seal_amount"),
            ).with_columns(
                pl.lit(trade_date).alias("trade_date"),
            )

            # 转换数据类型
            result = result.with_columns(
                pl.col("open_count").cast(pl.Int32).fill_null(0),
                pl.col("continuous_days").cast(pl.Int32).fill_null(1),
                # 成交额和封单金额可能是以万元为单位
                pl.col("amount").cast(pl.Float64).fill_null(0.0),
                pl.col("seal_amount").cast(pl.Float64).fill_null(0.0),
                pl.col("turnover_rate").cast(pl.Float64).fill_null(0.0),
            )

            logger.info("获取涨停池数据成功", count=len(result))
            return result

        except Exception as e:
            logger.error("获取涨停池数据失败", error=str(e))
            raise

    async def get_limit_down_pool(self, trade_date: date) -> pl.DataFrame:
        """
        获取跌停池数据

        使用 stock_zt_pool_dtgc_em 接口（跌停股池）
        """
        logger.info("获取跌停池数据", trade_date=str(trade_date))

        try:
            df = await self._run_sync(
                ak.stock_zt_pool_dtgc_em,
                date=trade_date.strftime("%Y%m%d"),
            )

            if df.empty:
                logger.warning("跌停池数据为空", trade_date=str(trade_date))
                return pl.DataFrame()

            result = pl.from_pandas(df)

            logger.info("获取跌停池数据成功", count=len(result))
            return result

        except Exception as e:
            logger.error("获取跌停池数据失败", error=str(e))
            raise

    async def get_market_overview(self, trade_date: date | None = None) -> dict | None:
        """
        获取市场概览数据（涨跌统计）

        使用 stock_market_fund_flow 接口获取成交额信息
        """
        logger.info("获取市场概览", trade_date=str(trade_date) if trade_date else "最新")

        try:
            # 获取市场整体成交数据
            df = await self._run_sync(ak.stock_market_fund_flow)

            if df.empty:
                logger.warning("市场概览数据为空")
                return None

            result = pl.from_pandas(df)

            # 获取最新一天的数据
            latest = result.sort("日期", descending=True).head(1)

            if len(latest) == 0:
                return None

            row = latest.row(0, named=True)

            return {
                "trade_date": row.get("日期"),
                "total_amount": Decimal(str(row.get("主力净流入-净额", 0) or 0)),
            }

        except Exception as e:
            logger.error("获取市场概览失败", error=str(e))
            raise

    async def calculate_market_sentiment(
        self,
        trade_date: date,
        all_quotes: pl.DataFrame,
    ) -> dict:
        """
        计算市场情绪指标

        基于全市场行情数据计算涨跌统计、换手率分布等

        Args:
            trade_date: 交易日期
            all_quotes: 全市场行情数据（需包含 change_pct, turnover_rate 等字段）
        """
        logger.info("计算市场情绪", trade_date=str(trade_date), total=len(all_quotes))

        if len(all_quotes) == 0:
            return {
                "trade_date": trade_date,
                "rising_count": 0,
                "falling_count": 0,
                "flat_count": 0,
                "limit_up_count": 0,
                "limit_down_count": 0,
            }

        # 涨跌统计
        rising_count = all_quotes.filter(pl.col("change_pct") > 0).height
        falling_count = all_quotes.filter(pl.col("change_pct") < 0).height
        flat_count = all_quotes.filter(pl.col("change_pct") == 0).height

        # 涨跌停统计（A股涨跌停约为 ±10%，ST 约 ±5%）
        limit_up_count = all_quotes.filter(pl.col("change_pct") >= 9.9).height
        limit_down_count = all_quotes.filter(pl.col("change_pct") <= -9.9).height

        # 涨跌比
        advance_decline_ratio = None
        if falling_count > 0:
            advance_decline_ratio = Decimal(str(round(rising_count / falling_count, 4)))

        # 换手率分布
        turnover_gt_10 = all_quotes.filter(pl.col("turnover_rate") > 10).height
        turnover_5_10 = all_quotes.filter(
            (pl.col("turnover_rate") >= 5) & (pl.col("turnover_rate") <= 10)
        ).height
        turnover_lt_1 = all_quotes.filter(pl.col("turnover_rate") < 1).height

        # 平均换手率
        avg_turnover = all_quotes.select(pl.col("turnover_rate").mean()).item()
        avg_turnover_rate = Decimal(str(round(avg_turnover, 4))) if avg_turnover else None

        # 总成交量和成交额
        total_volume = all_quotes.select(pl.col("volume").sum()).item()
        total_amount_raw = all_quotes.select(pl.col("amount").sum()).item()
        # 转换为亿元
        total_amount = Decimal(str(round(total_amount_raw / 100000000, 2))) if total_amount_raw else None

        return {
            "trade_date": trade_date,
            "rising_count": rising_count,
            "falling_count": falling_count,
            "flat_count": flat_count,
            "limit_up_count": limit_up_count,
            "limit_down_count": limit_down_count,
            "advance_decline_ratio": advance_decline_ratio,
            "turnover_gt_10_count": turnover_gt_10,
            "turnover_5_10_count": turnover_5_10,
            "turnover_lt_1_count": turnover_lt_1,
            "avg_turnover_rate": avg_turnover_rate,
            "total_volume": total_volume,
            "total_amount": total_amount,
        }


# 全局单例
sentiment_adapter = SentimentAdapter()
