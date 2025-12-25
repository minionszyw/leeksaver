"""
OpenAI 向量服务提供商
"""

import asyncio
from typing import List

import openai

from app.config import settings
from app.core.logging import get_logger
from app.services.embedding.base import BaseEmbeddingProvider

logger = get_logger(__name__)


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """OpenAI 向量服务提供商"""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self._api_key = api_key or settings.embedding_openai_api_key
        self._model = model or settings.embedding_openai_model
        self._dimension = settings.embedding_openai_dimension

        self.client = openai.AsyncOpenAI(api_key=self._api_key)

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    async def generate_embedding(self, text: str) -> List[float]:
        """生成单个文本的向量"""
        if not text or not text.strip():
            logger.warning("文本为空，返回零向量")
            return [0.0] * self.dimension

        try:
            # 截断过长文本（OpenAI 限制：8191 tokens，约 20000 字符）
            text = text[:20000]

            response = await self.client.embeddings.create(
                input=text,
                model=self.model_name,
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
        batch_size: int = 20,  # OpenAI 推荐批次大小
    ) -> List[List[float]]:
        """批量生成向量"""
        if not texts:
            return []

        logger.info("批量生成向量（OpenAI）", count=len(texts), batch_size=batch_size)

        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            logger.debug("处理批次", batch_index=i // batch_size, batch_size=len(batch))

            try:
                # 清理和截断文本
                processed_batch = [text[:20000] if text else "" for text in batch]

                response = await self.client.embeddings.create(
                    input=processed_batch,
                    model=self.model_name,
                )

                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)

                # 批次间休息
                if i + batch_size < len(texts):
                    await asyncio.sleep(0.5)

            except Exception as e:
                logger.error("批次处理失败", batch_index=i // batch_size, error=str(e))
                # 失败时填充零向量
                all_embeddings.extend([[0.0] * self.dimension] * len(batch))

        logger.info("批量生成向量完成（OpenAI）", total=len(all_embeddings))
        return all_embeddings

    async def close(self):
        """关闭客户端"""
        await self.client.close()
