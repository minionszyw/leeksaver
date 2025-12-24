"""
新闻数据同步器

负责同步财经新闻数据并生成向量
"""

import asyncio
from datetime import datetime
from typing import List

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.datasources.news_adapter import news_adapter
from app.models.news import NewsArticle
from app.repositories.news_repository import NewsRepository
from app.repositories.stock_repository import StockRepository
from app.services.embedding_service import embedding_service

logger = get_logger(__name__)


class NewsSyncer:
    """新闻数据同步器"""

    async def sync_market_news(self, limit: int = 50) -> dict:
        """
        同步全市场新闻

        Args:
            limit: 获取数量

        Returns:
            同步统计信息
        """
        logger.info("开始同步全市场新闻", limit=limit)

        try:
            # 获取新闻数据
            news_df = await news_adapter.get_market_news(limit=limit)

            if news_df is None or len(news_df) == 0:
                logger.warning("全市场新闻数据为空")
                return {"status": "no_data", "synced": 0}

            # 转换为新闻对象并入库
            synced_count = 0
            skipped_count = 0
            new_articles = []

            async with get_db_session() as session:
                repo = NewsRepository(session)

                for row in news_df.iter_rows(named=True):
                    # 检查是否已存在（按 URL 去重）
                    existing = await repo.get_by_url(row["url"])
                    if existing:
                        skipped_count += 1
                        continue

                    # 创建新闻对象
                    article = NewsArticle(
                        title=row["title"],
                        content=row["content"],
                        summary=None,  # 可后续从 content 提取
                        source=row["source"],
                        publish_time=row["publish_time"],
                        url=row["url"],
                        related_stocks=row["related_stocks"],
                        embedding=None,  # 后续生成
                    )

                    new_articles.append(article)

                # 批量插入
                if new_articles:
                    synced_count = await repo.bulk_create(new_articles)
                    await session.commit()

            logger.info(
                "全市场新闻同步完成",
                synced=synced_count,
                skipped=skipped_count,
                total=len(news_df),
            )

            # 异步生成向量（不阻塞）
            if synced_count > 0:
                asyncio.create_task(self._generate_embeddings_async())

            return {
                "status": "success",
                "synced": synced_count,
                "skipped": skipped_count,
                "total": len(news_df),
            }

        except Exception as e:
            logger.error("全市场新闻同步失败", error=str(e))
            raise

    async def sync_hot_stocks_news(
        self,
        top_n: int = 50,
        limit_per_stock: int = 5,
    ) -> dict:
        """
        同步热门股票新闻

        Args:
            top_n: 选择前 N 只活跃股票
            limit_per_stock: 每只股票获取的新闻数量

        Returns:
            同步统计信息
        """
        logger.info(
            "开始同步热门股票新闻",
            top_n=top_n,
            limit_per_stock=limit_per_stock,
        )

        try:
            # 获取活跃股票列表（排除 ETF）
            async with get_db_session() as session:
                stock_repo = StockRepository(session)
                all_stocks = await stock_repo.get_all(active_only=True)
                # 只选择股票（排除 ETF）
                stocks = [s for s in all_stocks if s.asset_type == "stock"]

            if not stocks:
                logger.warning("无活跃股票")
                return {"status": "no_stocks", "synced": 0}

            # 选择前 N 只股票（简化：按代码排序，实际可按市值或成交量排序）
            hot_stocks = stocks[:top_n]
            stock_codes = [stock.code for stock in hot_stocks]

            logger.info("选择热门股票", count=len(stock_codes))

            # 批量获取新闻
            news_df = await news_adapter.get_batch_stock_news(
                codes=stock_codes,
                limit_per_stock=limit_per_stock,
            )

            if news_df is None or len(news_df) == 0:
                logger.warning("热门股票新闻数据为空")
                return {"status": "no_data", "synced": 0}

            # 转换为新闻对象并入库
            synced_count = 0
            skipped_count = 0
            new_articles = []

            async with get_db_session() as session:
                repo = NewsRepository(session)

                for row in news_df.iter_rows(named=True):
                    # 检查是否已存在
                    existing = await repo.get_by_url(row["url"])
                    if existing:
                        skipped_count += 1
                        continue

                    # 创建新闻对象
                    article = NewsArticle(
                        title=row["title"],
                        content=row["content"],
                        summary=None,
                        source=row["source"],
                        publish_time=row["publish_time"],
                        url=row["url"],
                        related_stocks=row["related_stocks"],
                        embedding=None,
                    )

                    new_articles.append(article)

                # 批量插入
                if new_articles:
                    synced_count = await repo.bulk_create(new_articles)
                    await session.commit()

            logger.info(
                "热门股票新闻同步完成",
                synced=synced_count,
                skipped=skipped_count,
                total=len(news_df),
            )

            # 异步生成向量
            if synced_count > 0:
                asyncio.create_task(self._generate_embeddings_async())

            return {
                "status": "success",
                "synced": synced_count,
                "skipped": skipped_count,
                "total": len(news_df),
            }

        except Exception as e:
            logger.error("热门股票新闻同步失败", error=str(e))
            raise

    async def generate_embeddings(self, batch_size: int = 50) -> dict:
        """
        为尚未生成向量的新闻生成向量

        Args:
            batch_size: 批次大小

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
                    batch_size=20,  # OpenAI 批次限制
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
            raise

    async def _generate_embeddings_async(self):
        """异步生成向量（后台任务）"""
        try:
            await asyncio.sleep(5)  # 延迟 5 秒启动
            await self.generate_embeddings(batch_size=100)
        except Exception as e:
            logger.error("异步生成向量失败", error=str(e))


# 全局单例
news_syncer = NewsSyncer()
