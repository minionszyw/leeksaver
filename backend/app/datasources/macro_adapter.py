"""
宏观经济数据源适配器

封装 AkShare 宏观经济数据接口
"""

import asyncio
from datetime import datetime
from typing import Literal

import akshare as ak
import polars as pl

from app.core.logging import get_logger
from app.datasources.rate_limiter import akshare_limiter

logger = get_logger(__name__)


class MacroAdapter:
    """
    宏观经济数据源适配器

    使用 AkShare 宏观数据接口获取中国宏观经济指标
    """

    def __init__(self):
        self._loop = asyncio.get_event_loop()

    async def _run_sync(self, func, *args, **kwargs):
        """在线程池中运行同步函数"""
        async with akshare_limiter:
            return await asyncio.to_thread(func, *args, **kwargs)

    async def get_gdp_data(self) -> pl.DataFrame:
        """
        获取 GDP 数据（季度）

        Returns:
            包含 GDP 绝对值和同比增长的 DataFrame
        """
        logger.info("获取 GDP 数据")

        try:
            df = await self._run_sync(ak.macro_china_gdp)

            if df is None or df.empty:
                logger.warning("GDP 数据为空")
                return pl.DataFrame()

            # 转换为 Polars
            result = pl.from_pandas(df)

            # 解析季度字符串为日期（如 "2025年第3季度" → 2025-09-30）
            def parse_quarter(quarter_str: str) -> str:
                """解析季度字符串"""
                try:
                    if "第1-3季度" in quarter_str or "第1-2季度" in quarter_str:
                        # 特殊情况：累计季度
                        year = quarter_str[:4]
                        if "1-3" in quarter_str:
                            return f"{year}-09-30"
                        else:
                            return f"{year}-06-30"

                    year = quarter_str[:4]
                    if "第1季度" in quarter_str:
                        return f"{year}-03-31"
                    elif "第2季度" in quarter_str:
                        return f"{year}-06-30"
                    elif "第3季度" in quarter_str:
                        return f"{year}-09-30"
                    elif "第4季度" in quarter_str:
                        return f"{year}-12-31"
                    else:
                        return f"{year}-12-31"
                except:
                    return "2000-01-01"

            # 在 Pandas 中预处理日期
            df["period"] = df["季度"].apply(parse_quarter)

            # 重新转换为 Polars
            result = pl.from_pandas(df)

            # 构建多条记录：GDP、第一产业、第二产业、第三产业
            records = []

            for row in result.iter_rows(named=True):
                period_date = row["period"]

                # GDP
                records.append({
                    "indicator_name": "GDP",
                    "indicator_category": "国民经济",
                    "period": period_date,
                    "period_type": "季度",
                    "value": float(row["国内生产总值-绝对值"]) if row["国内生产总值-绝对值"] else None,
                    "yoy_rate": float(row["国内生产总值-同比增长"]) if row["国内生产总值-同比增长"] else None,
                    "unit": "亿元",
                })

            result_df = pl.DataFrame(records)
            result_df = result_df.with_columns([
                pl.col("period").str.to_date("%Y-%m-%d")
            ])

            logger.info("获取 GDP 数据成功", count=len(result_df))
            return result_df

        except Exception as e:
            logger.error("获取 GDP 数据失败", error=str(e))
            raise

    async def get_pmi_data(self) -> pl.DataFrame:
        """
        获取 PMI 数据（月度）

        Returns:
            包含制造业 PMI 和非制造业 PMI 的 DataFrame
        """
        logger.info("获取 PMI 数据")

        try:
            df = await self._run_sync(ak.macro_china_pmi)

            if df is None or df.empty:
                logger.warning("PMI 数据为空")
                return pl.DataFrame()

            # 转换为 Polars
            result = pl.from_pandas(df)

            # 解析月份字符串（如 "2025年11月份" → 2025-11-01）
            def parse_month(month_str: str) -> str:
                try:
                    year = month_str[:4]
                    month = month_str[5:7]
                    return f"{year}-{month}-01"
                except:
                    return "2000-01-01"

            # 在 Pandas 中预处理
            df["period"] = df["月份"].apply(parse_month)

            # 重新转换
            result = pl.from_pandas(df)

            # 构建记录
            records = []
            for row in result.iter_rows(named=True):
                # 制造业 PMI
                records.append({
                    "indicator_name": "PMI_制造业",
                    "indicator_category": "景气指数",
                    "period": row["period"],
                    "period_type": "月度",
                    "value": float(row["制造业-指数"]) if row["制造业-指数"] else None,
                    "yoy_rate": float(row["制造业-同比增长"]) if row["制造业-同比增长"] else None,
                    "unit": "点",
                })

                # 非制造业 PMI
                records.append({
                    "indicator_name": "PMI_非制造业",
                    "indicator_category": "景气指数",
                    "period": row["period"],
                    "period_type": "月度",
                    "value": float(row["非制造业-指数"]) if row["非制造业-指数"] else None,
                    "yoy_rate": float(row["非制造业-同比增长"]) if row["非制造业-同比增长"] else None,
                    "unit": "点",
                })

            result_df = pl.DataFrame(records)
            result_df = result_df.with_columns([
                pl.col("period").str.to_date("%Y-%m-%d")
            ])

            logger.info("获取 PMI 数据成功", count=len(result_df))
            return result_df

        except Exception as e:
            logger.error("获取 PMI 数据失败", error=str(e))
            raise


# 全局单例
macro_adapter = MacroAdapter()
