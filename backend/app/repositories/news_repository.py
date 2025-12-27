"""
新闻数据仓储

处理新闻数据的数据库操作
"""

from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.news import NewsArticle
from app.repositories.base import BaseRepository

logger = get_logger(__name__)


class NewsRepository(BaseRepository[NewsArticle]):
    """新闻数据仓储"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, NewsArticle)

    async def get_by_url(self, url: str) -> Optional[NewsArticle]:
        """
        根据 URL 查询新闻（检查是否已存在）

        Args:
            url: 新闻链接

        Returns:
            新闻对象，不存在则返回 None
        """
        stmt = select(NewsArticle).where(NewsArticle.url == url)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, article: NewsArticle) -> NewsArticle:
        """
        创建新闻记录

        Args:
            article: 新闻对象

        Returns:
            创建后的新闻对象
        """
        self.session.add(article)
        await self.session.flush()
        return article

    async def bulk_create(self, articles: List[NewsArticle]) -> int:
        """
        批量创建新闻记录

        Args:
            articles: 新闻对象列表

        Returns:
            创建的记录数
        """
        if not articles:
            return 0

        self.session.add_all(articles)
        await self.session.flush()
        return len(articles)

    async def update_embedding(
        self,
        article_id: int,
        embedding: List[float],
    ) -> None:
        """
        更新新闻的向量

        Args:
            article_id: 新闻 ID
            embedding: 向量数据
        """
        stmt = select(NewsArticle).where(NewsArticle.id == article_id)
        result = await self.session.execute(stmt)
        article = result.scalar_one_or_none()

        if article:
            article.embedding = embedding
            await self.session.flush()

    async def get_articles_without_embedding(
        self,
        limit: int = 100,
    ) -> List[NewsArticle]:
        """
        获取尚未生成向量的新闻

        Args:
            limit: 获取数量

        Returns:
            新闻列表
        """
        stmt = (
            select(NewsArticle)
            .where(NewsArticle.embedding.is_(None))
            .order_by(desc(NewsArticle.publish_time))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_recent_articles(
        self,
        days: int = 7,
        limit: int = 100,
    ) -> List[NewsArticle]:
        """
        获取最近的新闻

        Args:
            days: 最近 N 天
            limit: 获取数量

        Returns:
            新闻列表
        """
        cutoff_time = datetime.now() - timedelta(days=days)

        stmt = (
            select(NewsArticle)
            .where(NewsArticle.publish_time >= cutoff_time)
            .order_by(desc(NewsArticle.publish_time))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_articles_by_stock(
        self,
        stock_code: str,
        days: int = 7,
        limit: int = 20,
    ) -> List[NewsArticle]:
        """
        获取某只股票的相关新闻

        Args:
            stock_code: 股票代码
            days: 最近 N 天
            limit: 获取数量

        Returns:
            新闻列表
        """
        cutoff_time = datetime.now() - timedelta(days=days)

        # related_stocks 是 JSON 数组字符串，如 '["600519"]'
        # 使用 LIKE 模糊匹配
        stmt = (
            select(NewsArticle)
            .where(
                and_(
                    NewsArticle.publish_time >= cutoff_time,
                    NewsArticle.related_stocks.like(f'%"{stock_code}"%'),
                )
            )
            .order_by(desc(NewsArticle.publish_time))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_total(self) -> int:
        """
        统计新闻总数

        Returns:
            新闻总数
        """
        stmt = select(NewsArticle)
        result = await self.session.execute(stmt)
        return len(list(result.scalars().all()))

    async def count_with_embedding(self) -> int:
        """
        统计已生成向量的新闻数

        Returns:
            新闻数
        """
        stmt = select(NewsArticle).where(NewsArticle.embedding.is_not(None))
        result = await self.session.execute(stmt)
        return len(list(result.scalars().all()))
