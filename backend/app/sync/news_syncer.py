import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Type

import polars as pl
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select, desc

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.datasources.news_adapter import news_adapter
from app.models.news import NewsArticle, StockNewsArticle
from app.repositories.stock_repository import StockRepository
from app.services.embedding_service import embedding_service
from app.sync.status_manager import sync_status_manager

logger = get_logger(__name__)


class NewsSyncer:
    """新闻数据同步器"""

    async def _upsert_market_articles(self, articles: List[dict]) -> int:
        """批量 Upsert 全市新闻 (财联社)"""
        if not articles:
            return 0

        synced_count = 0
        async with get_db_session() as session:
            for item in articles:
                pub_time = item["publish_time"]
                if pub_time.tzinfo is None:
                    pub_time = pub_time.replace(tzinfo=timezone.utc)

                stmt = insert(NewsArticle).values(
                    title=item["title"],
                    content=item["content"],
                    source=item["source"],
                    publish_time=pub_time,
                    url=item["url"],
                    cls_id=item.get("cls_id"),
                    importance_level=item.get("importance_level", 1),
                    related_stocks=item.get("related_stocks"),
                    keywords=item.get("keywords"),
                    raw_data=item.get("raw_data"),
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                
                stmt = stmt.on_conflict_do_update(
                    index_elements=["url"],
                    set_={
                        "content": stmt.excluded.content,
                        "updated_at": datetime.now(timezone.utc)
                    }
                )
                res = await session.execute(stmt)
                if res.rowcount > 0:
                    synced_count += 1
            
            await session.commit()
        return synced_count

    async def _upsert_stock_articles(self, articles_df: pl.DataFrame) -> int:
        """批量 Upsert 个股新闻 (东方财富)"""
        if articles_df is None or len(articles_df) == 0:
            return 0

        synced_count = 0
        async with get_db_session() as session:
            for row in articles_df.iter_rows(named=True):
                pub_time = row["publish_time"]
                if pub_time and pub_time.tzinfo is None:
                    pub_time = pub_time.replace(tzinfo=timezone.utc)

                stmt = insert(StockNewsArticle).values(
                    stock_code=row["stock_code"],
                    title=row["title"],
                    content=row["content"],
                    source=row["source"],
                    publish_time=pub_time,
                    url=row["url"],
                    keywords=row.get("keywords"),
                    raw_data={"source": "eastmoney_em"},
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                stmt = stmt.on_conflict_do_nothing(index_elements=["url"])
                res = await session.execute(stmt)
                if res.rowcount > 0:
                    synced_count += 1
            await session.commit()
        return synced_count

    async def sync_market_news(self) -> dict:
        """同步全市新闻 (财联社)"""
        logger.info("开始同步全市新闻 (财联社)")
        try:
            # 每次同步都尝试抓取最新的全量(约20条)数据，由 _upsert_market_articles 处理冲突
            articles = await news_adapter.get_market_news(limit=100)
            logger.info(f"适配器返回新闻数量: {len(articles)}")
            
            if not articles:
                return {"status": "no_data", "synced": 0}

            synced_count = await self._upsert_market_articles(articles)
            logger.info(f"实际新入库/更新数量: {synced_count}")
            
            if synced_count > 0:
                await self.generate_embeddings(NewsArticle)

            return {"status": "success", "synced": synced_count}
        except Exception as e:
            logger.error("全市新闻同步失败", error=str(e))
            raise

    async def sync_stock_news_batch(self, batch_size: int = 50) -> dict:
        """轮询同步全市场个股新闻"""
        logger.info("开始轮询同步个股新闻", batch_size=batch_size)
        try:
            cursor = await sync_status_manager.get_cursor("stock_news_rotation")
            
            async with get_db_session() as session:
                stock_repo = StockRepository(session)
                stocks = await stock_repo.get_all_codes()
            
            if not stocks:
                return {"status": "no_stocks", "synced": 0}

            start_idx = cursor % len(stocks)
            end_idx = start_idx + batch_size
            batch_codes = stocks[start_idx:end_idx]
            
            if end_idx > len(stocks):
                batch_codes += stocks[:(end_idx % len(stocks))]

            logger.info(f"本批次同步个股数量: {len(batch_codes)}")

            news_df = await news_adapter.get_batch_stock_news(batch_codes, limit_per_stock=10)
            
            synced_count = 0
            if news_df is not None and len(news_df) > 0:
                synced_count = await self._upsert_stock_articles(news_df)

            await sync_status_manager.set_cursor("stock_news_rotation", end_idx % len(stocks))

            if synced_count > 0:
                await self.generate_embeddings(StockNewsArticle)

            return {
                "status": "success", 
                "synced": synced_count, 
                "stocks_processed": len(batch_codes),
                "next_cursor": end_idx % len(stocks)
            }
        except Exception as e:
            logger.error("个股新闻轮询失败", error=str(e))
            raise

    async def generate_embeddings(self, model_class: Type, batch_size: int = 50) -> dict:
        """生成新闻向量"""
        logger.info(f"为 {model_class.__tablename__} 生成向量")
        try:
            async with get_db_session() as session:
                stmt = select(model_class).where(model_class.embedding.is_(None)).order_by(desc(model_class.publish_time)).limit(batch_size)
                result = await session.execute(stmt)
                articles = result.scalars().all()

                if not articles:
                    return {"generated": 0}

                texts = [f"{a.title}\n\n{a.content}" for a in articles]
                embeddings = await embedding_service.generate_embeddings_batch(texts, batch_size=batch_size)

                for article, emb in zip(articles, embeddings):
                    article.embedding = emb
                
                await session.commit()
                return {"generated": len(articles)}
        except Exception as e:
            logger.error("生成向量失败", error=str(e))
            return {"generated": 0}

# 全局单例
news_syncer = NewsSyncer()