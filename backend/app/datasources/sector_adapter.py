"""
板块数据源适配器

封装 AkShare 板块数据接口
"""

import asyncio
from datetime import date, datetime
from typing import Literal

import akshare as ak
import polars as pl

from app.core.logging import get_logger
from app.datasources.rate_limiter import akshare_limiter

logger = get_logger(__name__)


class SectorAdapter:
    """
    板块数据源适配器

    使用 AkShare 板块数据接口获取行业和概念板块数据
    """

    def __init__(self):
        self._loop = asyncio.get_event_loop()

    async def _run_sync(self, func, *args, **kwargs):
        """在线程池中运行同步函数"""
        async with akshare_limiter:
            return await asyncio.to_thread(func, *args, **kwargs)

    async def get_industry_sectors(self) -> pl.DataFrame:
        """
        获取行业板块列表及行情

        Returns:
            包含板块基本信息和行情的 DataFrame
        """
        logger.info("获取行业板块列表")

        try:
            df = await self._run_sync(ak.stock_board_industry_name_em)

            if df is None or df.empty:
                logger.warning("行业板块数据为空")
                return pl.DataFrame()

            # 转换为 Polars
            result = pl.from_pandas(df)

            # 规范化列名
            result = result.rename({
                "板块代码": "code",
                "板块名称": "name",
                "最新价": "index_value",
                "涨跌额": "change_amount",
                "涨跌幅": "change_pct",
                "总市值": "total_amount",  # 注：这里是总市值，不是成交额
                "换手率": "turnover_rate",
                "上涨家数": "rising_count",
                "下跌家数": "falling_count",
                "领涨股票": "leading_stock",
                "领涨股票-涨跌幅": "leading_stock_pct",
            })

            # 添加板块类型和交易日期
            result = result.with_columns([
                pl.lit("industry").alias("sector_type"),
                pl.lit(date.today()).alias("trade_date"),
            ])

            # 选择需要的列
            result = result.select([
                "code",
                "name",
                "sector_type",
                "trade_date",
                "index_value",
                "change_pct",
                "change_amount",
                "total_amount",
                "rising_count",
                "falling_count",
                "leading_stock",
                "leading_stock_pct",
            ])

            logger.info("获取行业板块列表成功", count=len(result))
            return result

        except Exception as e:
            logger.error("获取行业板块列表失败", error=str(e))
            raise

    async def get_concept_sectors(self) -> pl.DataFrame:
        """
        获取概念板块列表及行情

        Returns:
            包含板块基本信息和行情的 DataFrame
        """
        logger.info("获取概念板块列表")

        try:
            df = await self._run_sync(ak.stock_board_concept_name_em)

            if df is None or df.empty:
                logger.warning("概念板块数据为空")
                return pl.DataFrame()

            # 转换为 Polars
            result = pl.from_pandas(df)

            # 规范化列名
            result = result.rename({
                "板块代码": "code",
                "板块名称": "name",
                "最新价": "index_value",
                "涨跌额": "change_amount",
                "涨跌幅": "change_pct",
                "总市值": "total_amount",
                "换手率": "turnover_rate",
                "上涨家数": "rising_count",
                "下跌家数": "falling_count",
                "领涨股票": "leading_stock",
                "领涨股票-涨跌幅": "leading_stock_pct",
            })

            # 添加板块类型和交易日期
            result = result.with_columns([
                pl.lit("concept").alias("sector_type"),
                pl.lit(date.today()).alias("trade_date"),
            ])

            # 选择需要的列
            result = result.select([
                "code",
                "name",
                "sector_type",
                "trade_date",
                "index_value",
                "change_pct",
                "change_amount",
                "total_amount",
                "rising_count",
                "falling_count",
                "leading_stock",
                "leading_stock_pct",
            ])

            logger.info("获取概念板块列表成功", count=len(result))
            return result

        except Exception as e:
            logger.error("获取概念板块列表失败", error=str(e))
            raise

    async def get_all_sectors(self) -> pl.DataFrame:
        """
        获取所有板块（行业 + 概念）

        Returns:
            合并后的板块数据 DataFrame
        """
        logger.info("获取所有板块数据")

        try:
            # 并行获取行业和概念板块
            industry_df = await self.get_industry_sectors()
            concept_df = await self.get_concept_sectors()

            # 合并
            all_sectors = pl.concat([industry_df, concept_df])

            logger.info("获取所有板块数据成功", total_count=len(all_sectors))
            return all_sectors

        except Exception as e:
            logger.error("获取所有板块数据失败", error=str(e))
            raise


# 全局单例
sector_adapter = SectorAdapter()
