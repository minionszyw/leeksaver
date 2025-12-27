"""
文本向量化服务（统一入口）

内部使用工厂模式，根据配置动态选择向量提供商（OpenAI/SiliconFlow/Ollama）
保持向后兼容性，支持语义检索
"""

from typing import List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.news import NewsArticle
from app.services.embedding.factory import get_embedding_provider

logger = get_logger(__name__)


PROVIDER_CONFIGS = {
    "openai": {"batch_size": 100, "concurrency": 10},
    "ollama": {"batch_size": 5, "concurrency": 2},
    "siliconflow": {"batch_size": 50, "concurrency": 5},
}


class EmbeddingService:
    """
    文本向量化服务（统一入口）

    内部使用工厂模式，根据配置动态选择提供商
    """

    def __init__(self):
        """初始化（延迟创建提供商）"""
        self._provider = None

    @property
    def provider(self):
        """获取当前提供商（懒加载）"""
        if self._provider is None:
            self._provider = get_embedding_provider()
        return self._provider

    @property
    def model(self) -> str:
        """当前模型名称"""
        return self.provider.model_name

    @property
    def dimension(self) -> int:
        """当前向量维度"""
        return self.provider.dimension

    async def generate_embedding(self, text: str) -> List[float]:
        """
        生成单个文本的向量

        Args:
            text: 输入文本

        Returns:
            向量
        """
        return await self.provider.generate_embedding(text)

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int | None = None,
    ) -> List[List[float]]:
        """
        批量生成向量

        Args:
            texts: 文本列表
            batch_size: 批次大小（保留参数以兼容，但优先使用 Provider 配置）

        Returns:
            向量列表
        """
        from app.config import settings

        # 根据 Provider 获取配置
        provider_type = settings.embedding_provider
        config = PROVIDER_CONFIGS.get(provider_type, {})
        
        # 优先使用配置中的 batch_size，如果未配置则使用传入值或默认值 100
        final_batch_size = config.get("batch_size", batch_size or 100)
        
        logger.debug(
            "批量生成向量", 
            provider=provider_type, 
            text_count=len(texts), 
            batch_size=final_batch_size
        )
        
        return await self.provider.generate_embeddings_batch(texts, batch_size=final_batch_size)

    async def search_similar_news(
        self,
        session: AsyncSession,
        query_text: str,
        limit: int = 10,
        similarity_threshold: float = 0.5,
        days: int = 7,
    ) -> List[NewsArticle]:
        """
        搜索相似新闻

        Args:
            session: 数据库会话
            query_text: 查询文本
            limit: 返回结果数量
            similarity_threshold: 相似度阈值 (0-1)
            days: 搜索最近 N 天的新闻

        Returns:
            新闻列表（按相似度降序）
        """
        logger.debug(
            "搜索相似新闻",
            query_length=len(query_text),
            limit=limit,
            threshold=similarity_threshold,
            days=days,
        )

        try:
            # 生成查询向量
            query_embedding = await self.generate_embedding(query_text)

            # 使用 pgvector 余弦相似度搜索
            # 1 - cosine_distance = cosine_similarity
            query = text(
                """
                SELECT *,
                       1 - (embedding <=> :query_embedding) AS similarity
                FROM news_articles
                WHERE publish_time >= NOW() - INTERVAL ':days days'
                  AND embedding IS NOT NULL
                  AND (1 - (embedding <=> :query_embedding)) >= :threshold
                ORDER BY similarity DESC
                LIMIT :limit
                """
            )

            result = await session.execute(
                query,
                {
                    "query_embedding": str(query_embedding),
                    "days": days,
                    "threshold": similarity_threshold,
                    "limit": limit,
                },
            )

            articles = result.fetchall()

            logger.info(
                "搜索相似新闻完成",
                query_length=len(query_text),
                found_count=len(articles),
            )

            # 转换为 NewsArticle 对象
            # 注：这里简化处理，实际应使用 ORM
            return [
                NewsArticle(
                    id=row[0],
                    title=row[1],
                    content=row[2],
                    summary=row[3],
                    source=row[4],
                    publish_time=row[5],
                    url=row[6],
                    related_stocks=row[7],
                    embedding=row[8],
                    created_at=row[9],
                    updated_at=row[10],
                )
                for row in articles
            ]

        except Exception as e:
            logger.error("搜索相似新闻失败", error=str(e))
            raise

    async def search_by_stock(
        self,
        session: AsyncSession,
        stock_code: str,
        limit: int = 10,
        days: int = 7,
    ) -> List[NewsArticle]:
        """
        按股票代码搜索新闻

        Args:
            session: 数据库会话
            stock_code: 股票代码
            limit: 返回结果数量
            days: 搜索最近 N 天的新闻

        Returns:
            新闻列表（按发布时间降序）
        """
        logger.debug(
            "按股票搜索新闻",
            stock_code=stock_code,
            limit=limit,
            days=days,
        )

        try:
            # 查询包含该股票代码的新闻
            # related_stocks 是 JSON 数组字符串，如 '["600519", "000001"]'
            query = text(
                """
                SELECT *
                FROM news_articles
                WHERE publish_time >= NOW() - INTERVAL ':days days'
                  AND related_stocks LIKE :stock_pattern
                ORDER BY publish_time DESC
                LIMIT :limit
                """
            )

            result = await session.execute(
                query,
                {
                    "days": days,
                    "stock_pattern": f'%"{stock_code}"%',
                    "limit": limit,
                },
            )

            articles = result.fetchall()

            logger.info(
                "按股票搜索新闻完成",
                stock_code=stock_code,
                found_count=len(articles),
            )

            # 转换为 NewsArticle 对象
            return [
                NewsArticle(
                    id=row[0],
                    title=row[1],
                    content=row[2],
                    summary=row[3],
                    source=row[4],
                    publish_time=row[5],
                    url=row[6],
                    related_stocks=row[7],
                    embedding=row[8],
                    created_at=row[9],
                    updated_at=row[10],
                )
                for row in articles
            ]

        except Exception as e:
            logger.error("按股票搜索新闻失败", stock_code=stock_code, error=str(e))
            raise


# 全局单例
embedding_service = EmbeddingService()
