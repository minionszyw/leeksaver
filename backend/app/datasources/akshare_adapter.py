"""
AkShare 数据源适配器

封装 AkShare 接口，提供统一的数据获取能力
"""

import asyncio
from datetime import date, datetime, timedelta
from typing import Any

import akshare as ak
import polars as pl

from app.core.logging import get_logger
from app.datasources.base import DataSourceBase
from app.datasources.rate_limiter import akshare_limiter

logger = get_logger(__name__)


class AkShareAdapter(DataSourceBase):
    """
    AkShare 数据源适配器

    注意：AkShare 是同步库，需要在线程池中执行
    """

    def __init__(self):
        self._loop = asyncio.get_event_loop()

    async def _run_sync(self, func, *args, **kwargs):
        """在线程池中运行同步函数"""
        async with akshare_limiter:
            return await asyncio.to_thread(func, *args, **kwargs)

    async def get_stock_list(self) -> pl.DataFrame:
        """
        获取 A 股股票列表

        使用 stock_info_a_code_name 接口
        """
        logger.info("获取 A 股股票列表")

        try:
            # 获取沪深股票列表
            df = await self._run_sync(ak.stock_info_a_code_name)

            # 转换为 Polars DataFrame
            result = pl.from_pandas(df)

            # 规范化列名
            result = result.rename({"code": "code", "name": "name"})

            # 添加市场标识
            result = result.with_columns(
                pl.when(pl.col("code").str.starts_with("6"))
                .then(pl.lit("SH"))
                .when(pl.col("code").str.starts_with("0"))
                .then(pl.lit("SZ"))
                .when(pl.col("code").str.starts_with("3"))
                .then(pl.lit("SZ"))
                .otherwise(pl.lit("BJ"))
                .alias("market"),
                pl.lit("stock").alias("asset_type"),
            )

            logger.info("获取 A 股股票列表成功", count=len(result))
            return result

        except Exception as e:
            logger.error("获取 A 股股票列表失败", error=str(e))
            raise

    async def get_etf_list(self) -> pl.DataFrame:
        """
        获取场内 ETF 列表

        使用 fund_etf_spot_em 接口
        """
        logger.info("获取 ETF 列表")

        try:
            # 获取 ETF 实时行情 (包含 ETF 列表)
            df = await self._run_sync(ak.fund_etf_spot_em)

            # 转换为 Polars DataFrame
            result = pl.from_pandas(df)

            # 选择需要的列并重命名
            result = result.select(
                pl.col("代码").alias("code"),
                pl.col("名称").alias("name"),
            ).with_columns(
                pl.when(pl.col("code").str.starts_with("5"))
                .then(pl.lit("SH"))
                .when(pl.col("code").str.starts_with("1"))
                .then(pl.lit("SZ"))
                .otherwise(pl.lit("SZ"))
                .alias("market"),
                pl.lit("etf").alias("asset_type"),
            )

            logger.info("获取 ETF 列表成功", count=len(result))
            return result

        except Exception as e:
            logger.error("获取 ETF 列表失败", error=str(e))
            raise

    async def get_daily_quotes(
        self,
        code: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pl.DataFrame:
        """
        获取股票日线行情

        使用 stock_zh_a_hist 接口
        """
        # 默认获取最近 2 年数据
        if start_date is None:
            start_date = date.today() - timedelta(days=730)
        if end_date is None:
            end_date = date.today()

        logger.debug(
            "获取日线行情",
            code=code,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

        try:
            # 调用 AkShare 接口
            df = await self._run_sync(
                ak.stock_zh_a_hist,
                symbol=code,
                period="daily",
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                adjust="qfq",  # 前复权
            )

            if df is None or df.empty:
                logger.warning("日线行情数据为空", code=code)
                return pl.DataFrame()

            # 转换为 Polars DataFrame
            result = pl.from_pandas(df)

            # 规范化列名
            # 处理日期列：如果是 date 类型直接使用，如果是字符串则转换
            date_col = result["日期"]
            if date_col.dtype == pl.Date:
                trade_date_expr = pl.col("日期").alias("trade_date")
            else:
                trade_date_expr = pl.col("日期").str.to_date("%Y-%m-%d").alias("trade_date")

            result = result.select(
                pl.lit(code).alias("code"),
                trade_date_expr,
                pl.col("开盘").cast(pl.Decimal(10, 2)).alias("open"),
                pl.col("最高").cast(pl.Decimal(10, 2)).alias("high"),
                pl.col("最低").cast(pl.Decimal(10, 2)).alias("low"),
                pl.col("收盘").cast(pl.Decimal(10, 2)).alias("close"),
                pl.col("成交量").cast(pl.Int64).alias("volume"),
                pl.col("成交额").cast(pl.Decimal(18, 2)).alias("amount"),
                pl.col("涨跌额").cast(pl.Decimal(10, 2)).alias("change"),
                pl.col("涨跌幅").cast(pl.Decimal(8, 4)).alias("change_pct"),
                pl.col("换手率").cast(pl.Decimal(8, 4)).alias("turnover_rate"),
            )

            logger.debug("获取日线行情成功", code=code, count=len(result))
            return result

        except Exception as e:
            logger.error("获取日线行情失败", code=code, error=str(e))
            raise

    async def get_realtime_quote(self, code: str) -> dict[str, Any]:
        """
        获取实时行情

        使用 stock_zh_a_spot_em 接口
        """
        logger.debug("获取实时行情", code=code)

        try:
            # 获取全市场实时行情
            df = await self._run_sync(ak.stock_zh_a_spot_em)

            # 筛选指定股票
            result = pl.from_pandas(df).filter(pl.col("代码") == code)

            if len(result) == 0:
                logger.warning("未找到股票实时行情", code=code)
                return {}

            row = result.row(0, named=True)

            return {
                "code": code,
                "name": row.get("名称"),
                "price": row.get("最新价"),
                "change": row.get("涨跌额"),
                "change_pct": row.get("涨跌幅"),
                "volume": row.get("成交量"),
                "amount": row.get("成交额"),
                "open": row.get("今开"),
                "high": row.get("最高"),
                "low": row.get("最低"),
                "pre_close": row.get("昨收"),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error("获取实时行情失败", code=code, error=str(e))
            raise


# 全局单例
akshare_adapter = AkShareAdapter()
