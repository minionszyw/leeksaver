"""
新闻数据源适配器

封装 AkShare 新闻接口，提供统一的新闻数据获取能力
"""

import asyncio
from datetime import datetime
from typing import Optional

import akshare as ak
import polars as pl

from app.core.logging import get_logger
from app.datasources.rate_limiter import akshare_limiter

logger = get_logger(__name__)


class NewsAdapter:
    """
    新闻数据源适配器

    使用 AkShare stock_news_em 接口获取东方财富新闻
    """

    def __init__(self):
        self._loop = asyncio.get_event_loop()

    async def _run_sync(self, func, *args, **kwargs):
        """在线程池中运行同步函数"""
        async with akshare_limiter:
            return await asyncio.to_thread(func, *args, **kwargs)

    async def get_market_news(self, limit: int = 100) -> pl.DataFrame:
        """
        获取全市场新闻

        Args:
            limit: 获取数量（AkShare 默认返回最新 10 条，可能无法指定）

        Returns:
            新闻数据 DataFrame
        """
        logger.info("获取全市场新闻", limit=limit)

        try:
            # 获取全部市场新闻
            df = await self._run_sync(ak.stock_news_em, symbol="全部")

            if df is None or df.empty:
                logger.warning("全市场新闻数据为空")
                return pl.DataFrame()

            # 转换为 Polars DataFrame
            result = pl.from_pandas(df)

            # 规范化列名
            result = result.rename({
                "新闻标题": "title",
                "新闻内容": "content",
                "发布时间": "publish_time",
                "文章来源": "source",
                "新闻链接": "url",
                "关键词": "keyword",
            })

            # 数据清洗和转换
            result = result.with_columns([
                # 转换发布时间为 datetime
                pl.col("publish_time").str.to_datetime("%Y-%m-%d %H:%M:%S"),
                # 关联股票设为空（全市场新闻无特定关联）
                pl.lit(None).alias("related_stocks"),
            ])

            # 只保留需要的列
            result = result.select([
                "title",
                "content",
                "source",
                "publish_time",
                "url",
                "related_stocks",
            ])

            # 按时间降序排序，取最新的 N 条
            result = result.sort("publish_time", descending=True).head(limit)

            logger.info("获取全市场新闻成功", count=len(result))
            return result

        except Exception as e:
            logger.error("获取全市场新闻失败", error=str(e))
            raise

    async def get_flash_news(self, limit: int = 100) -> pl.DataFrame:
        """
        获取实时快讯新闻（财联社等）

        Args:
            limit: 获取数量

        Returns:
            新闻数据 DataFrame
        """
        logger.info("获取实时快讯新闻", limit=limit)

        try:
            # 获取财联社快讯
            df = await self._run_sync(ak.stock_info_global_cls)

            if df is None or df.empty:
                logger.warning("实时快讯数据为空")
                return pl.DataFrame()

            # 转换为 Polars DataFrame
            result = pl.from_pandas(df)

            # 规范化列名
            # stock_info_global_cls 返回列：标题, 内容, 发布日期, 发布时间
            result = result.rename({
                "标题": "title",
                "内容": "content",
                "发布日期": "publish_date",
                "发布时间": "publish_clock",
            })

            # 合并日期和时间为 publish_time
            # 注意：Polars 中处理 Python date/time 对象需要转换
            result = result.with_columns([
                (pl.col("publish_date").cast(pl.Utf8) + " " + pl.col("publish_clock").cast(pl.Utf8))
                .str.to_datetime("%Y-%m-%d %H:%M:%S")
                .alias("publish_time"),
                pl.lit("财联社").alias("source"),
                pl.lit(None).alias("related_stocks"),
            ])

            # 为快讯生成唯一 URL 防止重复 (publish_time + title hash)
            result = result.with_columns([
                ("https://www.cls.cn/flash/" + pl.col("publish_time").cast(pl.Utf8) + pl.col("title")).alias("url")
            ])

            # 只保留需要的列
            result = result.select([
                "title",
                "content",
                "source",
                "publish_time",
                "url",
                "related_stocks",
            ])

            # 按时间降序排序，取最新的 N 条
            result = result.sort("publish_time", descending=True).head(limit)

            logger.info("获取实时快讯成功", count=len(result))
            return result

        except Exception as e:
            logger.error("获取实时快讯失败", error=str(e))
            raise

    async def get_stock_news(
        self,
        code: str,
        limit: int = 20,
    ) -> pl.DataFrame:
        """
        获取个股新闻

        Args:
            code: 股票代码
            limit: 获取数量

        Returns:
            新闻数据 DataFrame
        """
        logger.debug("获取个股新闻", code=code, limit=limit)

        try:
            # 获取个股新闻
            df = await self._run_sync(ak.stock_news_em, symbol=code)

            if df is None or df.empty:
                logger.warning("个股新闻数据为空", code=code)
                return pl.DataFrame()

            # 转换为 Polars DataFrame
            result = pl.from_pandas(df)

            # 规范化列名
            result = result.rename({
                "新闻标题": "title",
                "新闻内容": "content",
                "发布时间": "publish_time",
                "文章来源": "source",
                "新闻链接": "url",
                "关键词": "keyword",
            })

            # 数据清洗和转换
            result = result.with_columns([
                # 转换发布时间为 datetime
                pl.col("publish_time").str.to_datetime("%Y-%m-%d %H:%M:%S"),
                # 关联股票：将股票代码转换为 JSON 数组格式
                pl.lit(f'["{code}"]').alias("related_stocks"),
            ])

            # 只保留需要的列
            result = result.select([
                "title",
                "content",
                "source",
                "publish_time",
                "url",
                "related_stocks",
            ])

            # 按时间降序排序，取最新的 N 条
            result = result.sort("publish_time", descending=True).head(limit)

            logger.debug("获取个股新闻成功", code=code, count=len(result))
            return result

        except Exception as e:
            logger.error("获取个股新闻失败", code=code, error=str(e))
            raise

    async def get_batch_stock_news(
        self,
        codes: list[str],
        limit_per_stock: int = 10,
    ) -> pl.DataFrame:
        """
        批量获取多只股票的新闻

        Args:
            codes: 股票代码列表
            limit_per_stock: 每只股票获取的新闻数量

        Returns:
            合并后的新闻数据 DataFrame
        """
        logger.info("批量获取股票新闻", stock_count=len(codes), limit_per_stock=limit_per_stock)

        all_news = []

        for code in codes:
            try:
                news_df = await self.get_stock_news(code, limit=limit_per_stock)
                if news_df is not None and len(news_df) > 0:
                    all_news.append(news_df)

                # 批次间休息，避免超频
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.warning("获取股票新闻失败", code=code, error=str(e))
                continue

        if not all_news:
            logger.warning("批量获取股票新闻无数据")
            return pl.DataFrame()

        # 合并所有新闻
        result = pl.concat(all_news)

        # 去重（按 URL）
        original_count = len(result)
        result = result.unique(subset=["url"])
        dedup_count = original_count - len(result)

        if dedup_count > 0:
            logger.info(
                "去重新闻",
                original=original_count,
                after_dedup=len(result),
                removed=dedup_count,
            )

        # 按时间降序排序
        result = result.sort("publish_time", descending=True)

        logger.info("批量获取股票新闻成功", total_count=len(result))
        return result


# 全局单例
news_adapter = NewsAdapter()
