"""
新闻数据同步器

负责同步财经新闻数据并生成向量
"""

import asyncio
from datetime import datetime, timedelta
from typing import List

import polars as pl
from sqlalchemy.dialects.postgresql import insert

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.datasources.news_adapter import news_adapter
from app.models.news import NewsArticle
from app.repositories.news_repository import NewsRepository
from app.repositories.stock_repository import StockRepository, WatchlistRepository
from app.services.embedding_service import embedding_service

logger = get_logger(__name__)


class NewsSyncer:
    """新闻数据同步器"""

    async def _upsert_articles(self, articles_df: pl.DataFrame) -> int:
        """
        批量 Upsert 新闻文章
        
        如果 URL 已存在，则更新 related_stocks（如果新数据包含代码）
        """
        if articles_df is None or len(articles_df) == 0:
            return 0

        synced_count = 0
        async with get_db_session() as session:
            for row in articles_df.iter_rows(named=True):
                # 使用 PostgreSQL 的 ON CONFLICT DO UPDATE 逻辑
                stmt = insert(NewsArticle).values(
                    title=row["title"],
                    content=row["content"],
                    source=row["source"],
                    publish_time=row["publish_time"],
                    url=row["url"],
                    related_stocks=row["related_stocks"],
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                
                # 如果 URL 冲突
                # 只有当新抓取的数据包含 related_stocks 时，才更新旧记录的字段
                update_dict = {"updated_at": datetime.now()}
                if row["related_stocks"]:
                    update_dict["related_stocks"] = row["related_stocks"]
                
                stmt = stmt.on_conflict_do_update(
                    index_elements=["url"],
                    set_=update_dict
                )
                
                await session.execute(stmt)
                synced_count += 1
            
            await session.commit()
        return synced_count

    async def sync_market_news(self, limit: int | None = None) -> dict:
        """
        同步全市场新闻

        基于时间窗口回溯 (Time-Window Backfill)：
        1. 获取上次同步时间
        2. 如果首次运行，回溯 24 小时
        3. 否则回溯 [last_sync - 5min, now]
        4. 获取足够多的新闻并按时间过滤

        Args:
            limit: 仅作为向后兼容参数，实际上会被忽略或作为安全上限

        Returns:
            同步统计信息
        """
        logger.info("开始同步全市场新闻 (基于时间窗口)")

        try:
            async with get_db_session() as session:
                repo = NewsRepository(session)
                last_sync_time = await repo.get_latest_publish_time()

            # 计算起始时间 (统一使用 UTC)
            from datetime import timezone
            now = datetime.now(timezone.utc)
            if last_sync_time:
                # 确保 last_sync_time 是带时区的
                if last_sync_time.tzinfo is None:
                    last_sync_time = last_sync_time.replace(tzinfo=timezone.utc)
                # 增量同步：回溯 5 分钟以防时间偏差
                start_time = last_sync_time - timedelta(minutes=5)
                logger.info("增量同步模式", last_sync=last_sync_time, start_time=start_time)
            else:
                # 冷启动：回溯 72 小时
                start_time = now - timedelta(hours=72)
                logger.info("冷启动模式", start_time=start_time)

            # 多源抓取新闻
            # 1. 获取东方财富全市场新闻
            news_df = await news_adapter.get_market_news(limit=2000)
            
            # 2. 获取财联社实时快讯
            flash_df = await news_adapter.get_flash_news(limit=1000)

            # 合并数据源
            dfs_to_concat = []
            if news_df is not None and len(news_df) > 0:
                dfs_to_concat.append(news_df)
            if flash_df is not None and len(flash_df) > 0:
                dfs_to_concat.append(flash_df)

            if not dfs_to_concat:
                logger.warning("所有源的新闻数据均为空")
                return {"status": "no_data", "synced": 0}

            news_df = pl.concat(dfs_to_concat)

            # 统一时区：将 news_df 中的 naive datetime 转换为 UTC
            news_df = news_df.with_columns([
                pl.col("publish_time").dt.replace_time_zone("UTC")
            ])

            # 按时间过滤
            original_count = len(news_df)
            news_df = news_df.filter(pl.col("publish_time") >= start_time)
            filtered_count = len(news_df)
            
            logger.info(
                "新闻数据多源合并与时间过滤",
                start_time=start_time,
                original=original_count,
                filtered=filtered_count
            )

            # 批量 Upsert 入库
            synced_count = await self._upsert_articles(news_df)

            logger.info(
                "全市场新闻同步完成",
                synced=synced_count,
                filtered=filtered_count,
            )

            # 触发向量生成（这里改为直接调用，确保任务执行）
            if synced_count > 0:
                await self.generate_embeddings()

            return {
                "status": "success",
                "synced": synced_count,
                "total": filtered_count,
            }

        except Exception as e:
            logger.error("全市场新闻同步失败", error=str(e))
            raise

    async def sync_watchlist_news(
        self,
        limit_per_stock: int | None = None,
    ) -> dict:
        """
        同步自选股新闻

        优先同步用户自选股的相关新闻
        如果没有自选股，降级为全市场新闻同步

        Args:
            limit_per_stock: 每只股票获取的新闻数量 (默认为 50)

        Returns:
            同步统计信息
        """
        # 默认使用较大值以确保覆盖
        limit_per_stock = limit_per_stock or 50

        logger.info("开始同步自选股新闻", limit_per_stock=limit_per_stock)

        try:
            # 获取自选股代码列表
            async with get_db_session() as session:
                watchlist_repo = WatchlistRepository(session)
                stock_codes = await watchlist_repo.get_codes()

            # 如果没有自选股，降级为全市场新闻同步
            if not stock_codes:
                logger.warning("没有自选股，降级为全市场新闻同步")
                return await self.sync_market_news()

            logger.info("获取到自选股列表", count=len(stock_codes))

            # 批量获取新闻
            news_df = await news_adapter.get_batch_stock_news(
                codes=stock_codes,
                limit_per_stock=limit_per_stock,
            )

            if news_df is None or len(news_df) == 0:
                logger.warning("自选股新闻数据为空")
                return {"status": "no_data", "synced": 0}

            # 批量 Upsert 入库
            synced_count = await self._upsert_articles(news_df)

            logger.info(
                "自选股新闻同步完成",
                synced=synced_count,
                watchlist_count=len(stock_codes),
            )

            # 触发向量生成
            if synced_count > 0:
                await self.generate_embeddings()

            return {
                "status": "success",
                "synced": synced_count,
                "watchlist_count": len(stock_codes),
            }

        except Exception as e:
            logger.error("自选股新闻同步失败", error=str(e))
            raise

    async def generate_embeddings(self, batch_size: int = 100) -> dict:
        """
        为尚未生成向量的新闻生成向量

        Args:
            batch_size: 批次大小 (默认为 100，实际由 EmbeddingService 根据 Provider 调整)

        Returns:
            生成统计信息
        """
        logger.info("开始生成新闻向量", batch_size=batch_size)

        try:
            async with get_db_session() as session:
                repo = NewsRepository(session)

                # 获取未生成向量的新闻
                articles = await repo.get_articles_without_embedding(limit=batch_size)

                if not articles:
                    logger.info("无需生成向量的新闻")
                    return {"status": "no_pending", "generated": 0}

                logger.info("找到待生成向量的新闻", count=len(articles))

                # 提取文本（标题 + 内容）
                texts = [
                    f"{article.title}\n\n{article.content}"
                    for article in articles
                ]

                # 批量生成向量
                embeddings = await embedding_service.generate_embeddings_batch(
                    texts,
                    batch_size=batch_size,
                )

                # 更新数据库
                for article, embedding in zip(articles, embeddings):
                    article.embedding = embedding

                await session.commit()

                logger.info("新闻向量生成完成", generated=len(articles))

                return {
                    "status": "success",
                    "generated": len(articles),
                }

        except Exception as e:
            logger.error("新闻向量生成失败", error=str(e))
            # 向量生成失败不抛出异常，以免导致同步任务整体失败
            return {"status": "failed", "error": str(e)}


# 全局单例
news_syncer = NewsSyncer()