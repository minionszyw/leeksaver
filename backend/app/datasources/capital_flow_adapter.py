"""
资金面数据源适配器

封装 AkShare 资金流向相关接口
"""

import asyncio
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

import akshare as ak
import polars as pl

from app.core.logging import get_logger
from app.datasources.rate_limiter import akshare_limiter

logger = get_logger(__name__)


class CapitalFlowAdapter:
    """
    资金流向数据源适配器

    封装北向资金、个股资金流向、龙虎榜、两融数据接口
    """

    def __init__(self):
        self._loop = asyncio.get_event_loop()

    async def _run_sync(self, func, *args, **kwargs):
        """在线程池中运行同步函数"""
        async with akshare_limiter:
            return await asyncio.to_thread(func, *args, **kwargs)

    async def get_northbound_flow(self, trade_date: date | None = None) -> dict | None:
        """
        获取北向资金数据

        使用 stock_hsgt_fund_flow_summary_em 接口
        """
        logger.info("获取北向资金数据", trade_date=str(trade_date) if trade_date else "最新")

        try:
            # 获取当日汇总数据
            df = await self._run_sync(ak.stock_hsgt_fund_flow_summary_em)

            if df.empty:
                logger.warning("北向资金数据为空")
                return None

            # 转换为 Polars
            result = pl.from_pandas(df)

            # 筛选北向资金（沪股通+深股通）
            north_data = result.filter(pl.col("资金方向") == "北向")

            if len(north_data) == 0:
                logger.warning("无北向资金数据")
                return None

            # 获取沪股通和深股通数据
            sh_row = north_data.filter(pl.col("板块") == "沪股通")
            sz_row = north_data.filter(pl.col("板块") == "深股通")

            sh_net = sh_row.select("成交净买额").item() if len(sh_row) > 0 else 0
            sz_net = sz_row.select("成交净买额").item() if len(sz_row) > 0 else 0
            total_net = sh_net + sz_net

            # 获取交易日期
            trade_date_val = north_data.select("交易日").head(1).item()
            if isinstance(trade_date_val, str):
                trade_date_val = datetime.strptime(trade_date_val, "%Y-%m-%d").date()

            logger.info("获取北向资金数据成功", trade_date=str(trade_date_val))

            return {
                "trade_date": trade_date_val,
                "sh_net_inflow": Decimal(str(sh_net)) if sh_net else None,
                "sz_net_inflow": Decimal(str(sz_net)) if sz_net else None,
                "total_net_inflow": Decimal(str(total_net)) if total_net else None,
            }

        except Exception as e:
            logger.error("获取北向资金数据失败", error=str(e))
            raise

    async def get_stock_fund_flow_rank(
        self,
        indicator: str = "今日",
        limit: int = 100,
    ) -> pl.DataFrame:
        """
        获取个股资金流向排行

        使用 stock_individual_fund_flow_rank 接口

        Args:
            indicator: 时间范围 ("今日", "3日", "5日", "10日")
            limit: 返回条数
        """
        logger.info("获取资金流向排行", indicator=indicator, limit=limit)

        try:
            df = await self._run_sync(
                ak.stock_individual_fund_flow_rank,
                indicator=indicator,
            )

            if df.empty:
                logger.warning("资金流向排行数据为空")
                return pl.DataFrame()

            # 将 '-' 替换为 None（在 pandas 层面处理）
            df = df.replace("-", None)

            result = pl.from_pandas(df)

            # 规范化列名
            # 原始列名：序号,代码,名称,最新价,今日涨跌幅,今日主力净流入-净额,今日主力净流入-净占比,
            # 今日超大单净流入-净额,今日超大单净流入-净占比,今日大单净流入-净额,今日大单净流入-净占比,
            # 今日中单净流入-净额,今日中单净流入-净占比,今日小单净流入-净额,今日小单净流入-净占比
            result = result.select(
                pl.col("代码").alias("code"),
                pl.col("名称").alias("name"),
                pl.col("今日主力净流入-净额").cast(pl.Float64, strict=False).alias("main_net_inflow"),
                pl.col("今日主力净流入-净占比").cast(pl.Float64, strict=False).alias("main_net_pct"),
                pl.col("今日超大单净流入-净额").cast(pl.Float64, strict=False).alias("super_large_net"),
                pl.col("今日大单净流入-净额").cast(pl.Float64, strict=False).alias("large_net"),
                pl.col("今日中单净流入-净额").cast(pl.Float64, strict=False).alias("medium_net"),
                pl.col("今日小单净流入-净额").cast(pl.Float64, strict=False).alias("small_net"),
            ).head(limit)

            logger.info("获取资金流向排行成功", count=len(result))
            return result

        except Exception as e:
            logger.error("获取资金流向排行失败", error=str(e))
            raise

    async def get_dragon_tiger(
        self,
        start_date: date,
        end_date: date | None = None,
    ) -> pl.DataFrame:
        """
        获取龙虎榜数据

        使用 stock_lhb_detail_em 接口
        """
        if end_date is None:
            end_date = start_date

        logger.info("获取龙虎榜数据", start_date=str(start_date), end_date=str(end_date))

        try:
            df = await self._run_sync(
                ak.stock_lhb_detail_em,
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
            )

            if df.empty:
                logger.warning("龙虎榜数据为空")
                return pl.DataFrame()

            result = pl.from_pandas(df)

            # 规范化列名
            # 原始列名：序号,代码,名称,上榜日,解读,收盘价,涨跌幅,龙虎榜净买额,龙虎榜买入额,龙虎榜卖出额,
            # 龙虎榜成交额,市场总成交额,净买额占总成交比,成交额占总成交比,换手率,流通市值,上榜原因
            result = result.select(
                pl.col("代码").alias("code"),
                pl.col("名称").alias("name"),
                pl.col("上榜日").alias("trade_date"),
                pl.col("上榜原因").alias("reason"),
                pl.col("龙虎榜买入额").alias("buy_amount"),
                pl.col("龙虎榜卖出额").alias("sell_amount"),
                pl.col("龙虎榜净买额").alias("net_amount"),
                pl.col("收盘价").alias("close"),
                pl.col("涨跌幅").alias("change_pct"),
                pl.col("换手率").alias("turnover_rate"),
            )

            # 转换日期（如果是字符串则转换，如果已经是日期则保持不变）
            if result["trade_date"].dtype == pl.Utf8:
                result = result.with_columns(
                    pl.col("trade_date").str.to_date("%Y-%m-%d")
                )
            elif result["trade_date"].dtype != pl.Date:
                # 如果是 datetime 类型，转为 date
                result = result.with_columns(
                    pl.col("trade_date").cast(pl.Date)
                )

            logger.info("获取龙虎榜数据成功", count=len(result))
            return result

        except Exception as e:
            logger.error("获取龙虎榜数据失败", error=str(e))
            raise

    async def get_margin_trade_sse(self, trade_date: date) -> pl.DataFrame:
        """
        获取沪市融资融券数据

        使用 stock_margin_detail_sse 接口
        """
        logger.info("获取沪市两融数据", trade_date=str(trade_date))

        try:
            df = await self._run_sync(
                ak.stock_margin_detail_sse,
                date=trade_date.strftime("%Y%m%d"),
            )

            if df.empty:
                logger.warning("沪市两融数据为空", trade_date=str(trade_date))
                return pl.DataFrame()

            result = pl.from_pandas(df)

            # 规范化列名
            # 原始列名：信用交易日期,标的证券代码,标的证券简称,融资余额,融资买入额,融资偿还额,融券余量,融券卖出量,融券偿还量
            result = result.select(
                pl.col("标的证券代码").alias("code"),
                pl.col("融资买入额").alias("rzmre"),
                pl.col("融资余额").alias("rzye"),
                pl.col("融券卖出量").alias("rqmcl"),
                pl.col("融券余量").alias("rqyl"),  # 沪市只有融券余量，没有融券余额
            ).with_columns(
                pl.lit(trade_date).alias("trade_date"),
            )

            logger.info("获取沪市两融数据成功", count=len(result))
            return result

        except Exception as e:
            logger.error("获取沪市两融数据失败", error=str(e))
            raise

    async def get_margin_trade_szse(self, trade_date: date) -> pl.DataFrame:
        """
        获取深市融资融券数据

        使用 stock_margin_detail_szse 接口
        """
        logger.info("获取深市两融数据", trade_date=str(trade_date))

        try:
            df = await self._run_sync(
                ak.stock_margin_detail_szse,
                date=trade_date.strftime("%Y%m%d"),
            )

            if df.empty:
                logger.warning("深市两融数据为空", trade_date=str(trade_date))
                return pl.DataFrame()

            result = pl.from_pandas(df)

            # 规范化列名
            # 深市的列名可能不同，需要根据实际情况调整
            # 通常包括：证券代码,证券简称,融资买入额,融资余额,融券卖出量,融券余量,融券余额
            col_mapping = {
                "证券代码": "code",
                "融资买入额(元)": "rzmre",
                "融资余额(元)": "rzye",
                "融券卖出量(股)": "rqmcl",
                "融券余额(元)": "rqye",
            }

            # 尝试重命名
            for old_name, new_name in col_mapping.items():
                if old_name in result.columns:
                    result = result.rename({old_name: new_name})

            result = result.with_columns(
                pl.lit(trade_date).alias("trade_date"),
            )

            logger.info("获取深市两融数据成功", count=len(result))
            return result

        except Exception as e:
            logger.error("获取深市两融数据失败", error=str(e))
            raise


# 全局单例
capital_flow_adapter = CapitalFlowAdapter()
