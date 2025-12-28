"""
宏观经济数据源适配器

封装 AkShare 宏观经济数据接口
"""

import asyncio
import re
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

    def _parse_cn_date(self, date_str: str) -> str:
        """
        解析中文日期字符串
        支持:
        - "2025年11月份" -> "2025-11-01"
        - "2025.11" -> "2025-11-01"
        - "202501" -> "2025-01-01"
        """
        try:
            date_str = str(date_str).strip()
            # 匹配 YYYY年MM月份
            match = re.search(r"(\d{4})年(\d{1,2})月份", date_str)
            if match:
                year, month = match.groups()
                return f"{year}-{month.zfill(2)}-01"
            
            # 匹配 YYYY.MM
            match = re.search(r"(\d{4})\.(\d{1,2})", date_str)
            if match:
                year, month = match.groups()
                return f"{year}-{month.zfill(2)}-01"

            # 匹配 YYYYMM
            match = re.search(r"(\d{4})(\d{2})", date_str)
            if match:
                year, month = match.groups()
                return f"{year}-{month}-01"

            return "2000-01-01"
        except Exception:
            return "2000-01-01"

    async def get_gdp_data(self) -> pl.DataFrame:
        """获取 GDP 数据（季度）"""
        logger.info("获取 GDP 数据")
        try:
            df = await self._run_sync(ak.macro_china_gdp)
            if df is None or df.empty:
                return pl.DataFrame()

            # 解析季度字符串
            def parse_quarter(quarter_str: str) -> str:
                try:
                    if "第1-3季度" in quarter_str or "第1-2季度" in quarter_str:
                        year = quarter_str[:4]
                        return f"{year}-09-30" if "1-3" in quarter_str else f"{year}-06-30"
                    
                    year = quarter_str[:4]
                    if "第1季度" in quarter_str: return f"{year}-03-31"
                    elif "第2季度" in quarter_str: return f"{year}-06-30"
                    elif "第3季度" in quarter_str: return f"{year}-09-30"
                    elif "第4季度" in quarter_str: return f"{year}-12-31"
                    return f"{year}-12-31"
                except:
                    return "2000-01-01"

            df["period"] = df["季度"].apply(parse_quarter)
            result = pl.from_pandas(df)

            records = []
            for row in result.iter_rows(named=True):
                records.append({
                    "indicator_name": "GDP",
                    "indicator_category": "国民经济",
                    "period": row["period"],
                    "period_type": "季度",
                    "value": float(row["国内生产总值-绝对值"]) if row["国内生产总值-绝对值"] else None,
                    "yoy_rate": float(row["国内生产总值-同比增长"]) if row["国内生产总值-同比增长"] else None,
                    "unit": "亿元",
                })

            result_df = pl.DataFrame(records).with_columns([
                pl.col("period").str.to_date("%Y-%m-%d")
            ])
            logger.info("获取 GDP 数据成功", count=len(result_df))
            return result_df
        except Exception as e:
            logger.error("获取 GDP 数据失败", error=str(e))
            raise

    async def get_pmi_data(self) -> pl.DataFrame:
        """获取 PMI 数据（月度）"""
        logger.info("获取 PMI 数据")
        try:
            df = await self._run_sync(ak.macro_china_pmi)
            if df is None or df.empty:
                return pl.DataFrame()

            df["period"] = df["月份"].apply(self._parse_cn_date)
            result = pl.from_pandas(df)

            records = []
            for row in result.iter_rows(named=True):
                records.append({
                    "indicator_name": "PMI_制造业",
                    "indicator_category": "景气指数",
                    "period": row["period"],
                    "period_type": "月度",
                    "value": float(row["制造业-指数"]) if row["制造业-指数"] else None,
                    "yoy_rate": float(row["制造业-同比增长"]) if row["制造业-同比增长"] else None,
                    "unit": "点",
                })
                records.append({
                    "indicator_name": "PMI_非制造业",
                    "indicator_category": "景气指数",
                    "period": row["period"],
                    "period_type": "月度",
                    "value": float(row["非制造业-指数"]) if row["非制造业-指数"] else None,
                    "yoy_rate": float(row["非制造业-同比增长"]) if row["非制造业-同比增长"] else None,
                    "unit": "点",
                })

            result_df = pl.DataFrame(records).with_columns([
                pl.col("period").str.to_date("%Y-%m-%d")
            ])
            logger.info("获取 PMI 数据成功", count=len(result_df))
            return result_df
        except Exception as e:
            logger.error("获取 PMI 数据失败", error=str(e))
            raise

    async def get_cpi_data(self) -> pl.DataFrame:
        """获取 CPI 数据（月度）"""
        logger.info("获取 CPI 数据")
        try:
            df = await self._run_sync(ak.macro_china_cpi)
            if df is None or df.empty:
                return pl.DataFrame()

            df["period"] = df["月份"].apply(self._parse_cn_date)
            result = pl.from_pandas(df)

            records = []
            for row in result.iter_rows(named=True):
                records.append({
                    "indicator_name": "CPI",
                    "indicator_category": "价格指数",
                    "period": row["period"],
                    "period_type": "月度",
                    "value": float(row["全国-当月"]) if row["全国-当月"] else None,
                    "yoy_rate": float(row["全国-同比增长"]) if row["全国-同比增长"] else None,
                    "unit": "点",
                })

            result_df = pl.DataFrame(records).with_columns([
                pl.col("period").str.to_date("%Y-%m-%d")
            ])
            logger.info("获取 CPI 数据成功", count=len(result_df))
            return result_df
        except Exception as e:
            logger.error("获取 CPI 数据失败", error=str(e))
            raise

    async def get_ppi_data(self) -> pl.DataFrame:
        """获取 PPI 数据（月度）"""
        logger.info("获取 PPI 数据")
        try:
            df = await self._run_sync(ak.macro_china_ppi)
            if df is None or df.empty:
                return pl.DataFrame()

            df["period"] = df["月份"].apply(self._parse_cn_date)
            result = pl.from_pandas(df)

            records = []
            for row in result.iter_rows(named=True):
                # 修正字段名: '同比增长' -> '当月同比增长'
                records.append({
                    "indicator_name": "PPI",
                    "indicator_category": "价格指数",
                    "period": row["period"],
                    "period_type": "月度",
                    "value": float(row["当月"]) if row["当月"] else None,
                    "yoy_rate": float(row["当月同比增长"]) if row["当月同比增长"] else None,
                    "unit": "点",
                })

            result_df = pl.DataFrame(records).with_columns([
                pl.col("period").str.to_date("%Y-%m-%d")
            ])
            logger.info("获取 PPI 数据成功", count=len(result_df))
            return result_df
        except Exception as e:
            logger.error("获取 PPI 数据失败", error=str(e))
            raise

    async def get_social_financing_data(self) -> pl.DataFrame:
        """获取社融规模数据（月度）"""
        logger.info("获取社融规模数据")
        try:
            df = await self._run_sync(ak.macro_china_shrzgm)
            if df is None or df.empty:
                return pl.DataFrame()

            df["period"] = df["月份"].apply(self._parse_cn_date)
            result = pl.from_pandas(df)

            records = []
            for row in result.iter_rows(named=True):
                # 修正字段名: 只有 '社会融资规模增量'
                records.append({
                    "indicator_name": "社融规模",
                    "indicator_category": "金融数据",
                    "period": row["period"],
                    "period_type": "月度",
                    "value": float(row["社会融资规模增量"]) if row["社会融资规模增量"] else None,
                    "yoy_rate": None, # 接口未提供同比数据
                    "unit": "亿元",
                })

            result_df = pl.DataFrame(records).with_columns([
                pl.col("period").str.to_date("%Y-%m-%d")
            ])
            logger.info("获取社融规模数据成功", count=len(result_df))
            return result_df
        except Exception as e:
            logger.error("获取社融规模数据失败", error=str(e))
            raise

    async def get_money_supply_data(self) -> pl.DataFrame:
        """获取货币供应量数据（月度）"""
        logger.info("获取货币供应量数据")
        try:
            df = await self._run_sync(ak.macro_china_money_supply)
            if df is None or df.empty:
                return pl.DataFrame()

            df["period"] = df["月份"].apply(self._parse_cn_date)
            result = pl.from_pandas(df)

            records = []
            for row in result.iter_rows(named=True):
                for m_type in ["M0", "M1", "M2"]:
                    key_val = f"货币(M1)-数量(亿元)" if m_type == "M1" else (
                        f"流通中的现金(M0)-数量(亿元)" if m_type == "M0" else f"货币和准货币(M2)-数量(亿元)"
                    )
                    key_yoy = f"货币(M1)-同比增长" if m_type == "M1" else (
                        f"流通中的现金(M0)-同比增长" if m_type == "M0" else f"货币和准货币(M2)-同比增长"
                    )
                    
                    records.append({
                        "indicator_name": m_type,
                        "indicator_category": "金融数据",
                        "period": row["period"],
                        "period_type": "月度",
                        "value": float(row[key_val]) if row.get(key_val) else None,
                        "yoy_rate": float(row[key_yoy]) if row.get(key_yoy) else None,
                        "unit": "亿元",
                    })

            result_df = pl.DataFrame(records).with_columns([
                pl.col("period").str.to_date("%Y-%m-%d")
            ])
            logger.info("获取货币供应量数据成功", count=len(result_df))
            return result_df
        except Exception as e:
            logger.error("获取货币供应量数据失败", error=str(e))
            raise

    async def get_shibor_data(self) -> pl.DataFrame:
        """获取 SHIBOR 利率数据"""
        logger.info("获取 SHIBOR 数据")
        try:
            # 替换为 macro_china_shibor_all
            df = await self._run_sync(ak.macro_china_shibor_all)
            if df is None or df.empty:
                return pl.DataFrame()

            # 转换为 Date 对象
            df["日期"] = df["日期"].apply(lambda x: str(x))
            result = pl.from_pandas(df)

            records = []
            # 只取最近 1000 条，避免全量历史太大
            for row in result.tail(1000).iter_rows(named=True):
                period_date = str(row["日期"])
                # 隔夜
                records.append({
                    "indicator_name": "SHIBOR_隔夜",
                    "indicator_category": "利率",
                    "period": period_date,
                    "period_type": "日度",
                    "value": float(row["ON"]) if row.get("ON") else None,
                    "yoy_rate": None,
                    "unit": "%",
                })
                # 1月
                records.append({
                    "indicator_name": "SHIBOR_1月",
                    "indicator_category": "利率",
                    "period": period_date,
                    "period_type": "日度",
                    "value": float(row["1M"]) if row.get("1M") else None,
                    "yoy_rate": None,
                    "unit": "%",
                })

            result_df = pl.DataFrame(records).with_columns([
                pl.col("period").str.to_date("%Y-%m-%d")
            ])
            logger.info("获取 SHIBOR 数据成功", count=len(result_df))
            return result_df
        except Exception as e:
            logger.error("获取 SHIBOR 数据失败", error=str(e))
            raise

    async def get_treasury_yield_data(self) -> pl.DataFrame:
        """获取国债收益率数据"""
        logger.info("获取国债收益率数据")
        try:
            df = await self._run_sync(ak.bond_zh_us_rate)
            if df is None or df.empty:
                return pl.DataFrame()

            # 显式转换类型，解决 Polars schema 推断错误
            for col in df.columns:
                if "收益率" in col:
                    df[col] = df[col].astype(float)
            
            df["日期"] = df["日期"].astype(str)
            result = pl.from_pandas(df)

            records = []
            # 只取最近 1000 条
            for row in result.tail(1000).iter_rows(named=True):
                records.append({
                    "indicator_name": "国债收益率_10年",
                    "indicator_category": "利率",
                    "period": str(row["日期"]),
                    "period_type": "日度",
                    "value": float(row["中国国债收益率10年"]) if row.get("中国国债收益率10年") else None,
                    "yoy_rate": None,
                    "unit": "%",
                })

            result_df = pl.DataFrame(records).with_columns([
                pl.col("period").str.to_date("%Y-%m-%d")
            ])
            logger.info("获取国债收益率数据成功", count=len(result_df))
            return result_df
        except Exception as e:
            logger.error("获取国债收益率数据失败", error=str(e))
            raise

    async def get_exchange_rate_data(self) -> pl.DataFrame:
        """获取汇率数据"""
        logger.info("获取人民币汇率数据")
        try:
            # fx_spot_quote 无参数
            df = await self._run_sync(ak.fx_spot_quote)
            if df is None or df.empty:
                return pl.DataFrame()

            result = pl.from_pandas(df)
            
            # 筛选 USD/CNY
            usd_cny = result.filter(pl.col("货币对") == "USD/CNY")
            
            if len(usd_cny) == 0:
                logger.warning("未找到 USD/CNY 汇率")
                return pl.DataFrame()

            row = usd_cny.row(0, named=True)
            # 使用买报价作为参考
            price = float(row["买报价"]) if row["买报价"] else None
            
            from datetime import date
            today = str(date.today())

            records = [{
                "indicator_name": "美元兑人民币",
                "indicator_category": "汇率",
                "period": today,
                "period_type": "日度",
                "value": price,
                "yoy_rate": None,
                "unit": "CNY/USD",
            }]

            result_df = pl.DataFrame(records).with_columns([
                pl.col("period").str.to_date("%Y-%m-%d")
            ])
            logger.info("获取汇率数据成功", count=1)
            return result_df
        except Exception as e:
            logger.error("获取汇率数据失败", error=str(e))
            raise


# 全局单例
macro_adapter = MacroAdapter()