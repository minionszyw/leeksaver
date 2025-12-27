"""
估值数据源适配器

封装 AkShare 估值相关接口（PE、PB、市值等）
"""

import asyncio
from datetime import date
from decimal import Decimal

import akshare as ak
import polars as pl

from app.core.logging import get_logger
from app.core.cache import cached
from app.datasources.rate_limiter import akshare_limiter

logger = get_logger(__name__)


class ValuationAdapter:
    """
    估值数据源适配器

    从实时行情中提取估值数据（PE、PB、市值等）
    """

    def __init__(self):
        self._loop = asyncio.get_event_loop()

    async def _run_sync(self, func, *args, **kwargs):
        """在线程池中运行同步函数"""
        async with akshare_limiter:
            return await asyncio.to_thread(func, *args, **kwargs)

    @cached(ttl=300, key_prefix="valuation")
    async def get_all_valuations(self, trade_date: date) -> dict:
        """
        获取全市场估值数据（带缓存）

        使用 stock_zh_a_spot_em 接口获取实时行情（包含 PE、PB、市值）

        性能优化：
        - 缓存 5 分钟（避免重复调用 AkShare API）
        - 返回值转为 dict 以支持 JSON 序列化

        Returns:
            包含 DataFrame 数据的字典 {"data": list[dict], "columns": list[str]}
        """
        logger.info("获取全市场估值数据", trade_date=str(trade_date))

        try:
            df = await self._run_sync(ak.stock_zh_a_spot_em)

            if df.empty:
                logger.warning("全市场估值数据为空")
                return pl.DataFrame()

            result = pl.from_pandas(df)

            # 规范化列名
            # 原始列名包括：代码,名称,最新价,涨跌幅,涨跌额,成交量,成交额,振幅,最高,最低,
            # 今开,昨收,量比,换手率,市盈率-动态,市净率,总市值,流通市值,涨速,5分钟涨跌,60日涨跌幅,年初至今涨跌幅
            result = result.select(
                pl.col("代码").alias("code"),
                pl.col("市盈率-动态").alias("pe_ttm"),
                pl.col("市净率").alias("pb"),
                pl.col("总市值").alias("total_mv_raw"),
                pl.col("流通市值").alias("circ_mv_raw"),
            ).with_columns(
                pl.lit(trade_date).alias("trade_date"),
            )

            # 转换市值为亿元
            result = result.with_columns(
                (pl.col("total_mv_raw") / 100000000).round(2).alias("total_mv"),
                (pl.col("circ_mv_raw") / 100000000).round(2).alias("circ_mv"),
            ).drop(["total_mv_raw", "circ_mv_raw"])

            # 过滤无效数据
            result = result.filter(
                (pl.col("pe_ttm").is_not_null()) | (pl.col("pb").is_not_null())
            )

            logger.info("获取全市场估值数据成功", count=len(result))

            # 转换为可序列化的字典格式（用于缓存）
            return {
                "data": result.to_dicts(),
                "columns": result.columns,
            }

        except Exception as e:
            logger.error("获取全市场估值数据失败", error=str(e))
            raise

    async def get_stock_valuation(self, code: str, trade_date: date) -> dict | None:
        """
        获取单只股票的估值数据

        性能优化：利用缓存的全市场数据，避免重复调用 API
        """
        logger.info("获取股票估值", code=code, trade_date=str(trade_date))

        try:
            # 获取缓存的全市场数据
            all_valuations_dict = await self.get_all_valuations(trade_date)

            if not all_valuations_dict or not all_valuations_dict["data"]:
                return None

            # 从缓存的字典恢复 DataFrame
            all_valuations = pl.from_dicts(all_valuations_dict["data"])

            stock_data = all_valuations.filter(pl.col("code") == code)

            if len(stock_data) == 0:
                return None

            row = stock_data.row(0, named=True)

            return {
                "code": row["code"],
                "trade_date": row["trade_date"],
                "pe_ttm": Decimal(str(row["pe_ttm"])) if row["pe_ttm"] else None,
                "pb": Decimal(str(row["pb"])) if row["pb"] else None,
                "total_mv": Decimal(str(row["total_mv"])) if row["total_mv"] else None,
                "circ_mv": Decimal(str(row["circ_mv"])) if row["circ_mv"] else None,
            }

        except Exception as e:
            logger.error("获取股票估值失败", code=code, error=str(e))
            raise


# 全局单例
valuation_adapter = ValuationAdapter()
