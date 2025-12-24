"""
文本向量化服务

使用 OpenAI Embeddings API 将文本转换为向量，支持语义检索
"""

import asyncio
from typing import List

import openai
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import get_logger
from app.models.news import NewsArticle

logger = get_logger(__name__)


class EmbeddingService:
    """
    文本向量化服务

    使用 OpenAI text-embedding-3-small 模型生成 1536 维向量
    """

    def __init__(self):
        """初始化 OpenAI 客户端"""
        self.client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = "text-embedding-3-small"
        self.dimension = 1536

    async def generate_embedding(self, text: str) -> List[float]:
        """
        生成单个文本的向量

        Args:
            text: 输入文本

        Returns:
            1536 维向量
        """
        if not text or not text.strip():
            logger.warning("文本为空，返回零向量")
            return [0.0] * self.dimension

        try:
            # 截断过长文本（OpenAI 限制：8191 tokens）
            # 1 token ≈ 4 characters，保守估计取前 20000 字符
            text = text[:20000]

            # 调用 OpenAI API
            response = await self.client.embeddings.create(
                input=text,
                model=self.model,
            )

            embedding = response.data[0].embedding
            logger.debug("生成向量成功", text_length=len(text), dim=len(embedding))
            return embedding

        except Exception as e:
            logger.error("生成向量失败", error=str(e), text_length=len(text))
            raise

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 100,
    ) -> List[List[float]]:
        """
        批量生成向量

        Args:
            texts: 文本列表
            batch_size: 批次大小（OpenAI 限制：2048 个文本/批次）

        Returns:
            向量列表
        """
        if not texts:
            return []

        logger.info("批量生成向量", count=len(texts), batch_size=batch_size)

        all_embeddings = []

        # 分批处理
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            logger.debug("处理批次", batch_index=i // batch_size, batch_size=len(batch))

            try:
                # 清理空文本
                processed_batch = [text[:20000] if text else "" for text in batch]

                # 调用 OpenAI API
                response = await self.client.embeddings.create(
                    input=processed_batch,
                    model=self.model,
                )

                # 提取向量
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)

                # 批次间休息（避免超频）
                if i + batch_size < len(texts):
                    await asyncio.sleep(0.5)

            except Exception as e:
                logger.error("批次处理失败", batch_index=i // batch_size, error=str(e))
                # 失败时填充零向量
                all_embeddings.extend([[0.0] * self.dimension] * len(batch))

        logger.info("批量生成向量完成", total=len(all_embeddings))
        return all_embeddings

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
