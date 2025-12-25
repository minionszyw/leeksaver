"""
Ollama 向量服务提供商（本地）
"""

import asyncio
from typing import List

import httpx

from app.config import settings
from app.core.logging import get_logger
from app.services.embedding.base import BaseEmbeddingProvider

logger = get_logger(__name__)


class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    """Ollama 向量服务提供商（本地）"""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self._base_url = base_url or settings.embedding_ollama_base_url
        self._model = model or settings.embedding_ollama_model
        self._dimension = settings.embedding_ollama_dimension

        self.client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=120.0,
        )

    @property
    def provider_name(self) -> str:
        return "ollama"

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
            # Ollama 通常支持较长文本
            text = text[:50000]

            payload = {
                "model": self.model_name,
                "prompt": text,
            }

            response = await self.client.post("/api/embeddings", json=payload)
            response.raise_for_status()
            data = response.json()

            embedding = data["embedding"]
            logger.debug("生成向量成功（Ollama）", text_length=len(text), dim=len(embedding))
            return embedding

        except Exception as e:
            logger.error("生成向量失败（Ollama）", error=str(e), text_length=len(text))
            raise

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 1,  # Ollama 逐个处理
    ) -> List[List[float]]:
        """批量生成向量（Ollama 逐个调用 API）"""
        if not texts:
            return []

        logger.info("批量生成向量（Ollama）", count=len(texts))

        all_embeddings = []

        for i, text in enumerate(texts):
            try:
                embedding = await self.generate_embedding(text)
                all_embeddings.append(embedding)

                # 本地调用也适度休息
                if i < len(texts) - 1:
                    await asyncio.sleep(0.1)

            except Exception as e:
                logger.error("生成向量失败（Ollama）", index=i, error=str(e))
                all_embeddings.append([0.0] * self.dimension)

        logger.info("批量生成向量完成（Ollama）", total=len(all_embeddings))
        return all_embeddings

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()
