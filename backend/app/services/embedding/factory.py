"""
向量服务工厂
"""

from typing import Literal

from app.config import settings
from app.core.logging import get_logger
from app.services.embedding.base import BaseEmbeddingProvider
from app.services.embedding.providers.ollama import OllamaEmbeddingProvider
from app.services.embedding.providers.openai import OpenAIEmbeddingProvider
from app.services.embedding.providers.siliconflow import SiliconFlowEmbeddingProvider

logger = get_logger(__name__)

EmbeddingProviderType = Literal["openai", "siliconflow", "ollama"]


class EmbeddingFactory:
    """向量服务工厂"""

    _instances: dict[str, BaseEmbeddingProvider] = {}

    @classmethod
    def create(
        cls,
        provider: EmbeddingProviderType | None = None,
        **kwargs,
    ) -> BaseEmbeddingProvider:
        """
        创建向量服务实例

        Args:
            provider: 提供商名称，默认从配置读取
            **kwargs: 传递给具体提供商的参数

        Returns:
            向量服务实例
        """
        provider = provider or settings.embedding_provider

        logger.info("创建向量服务实例", provider=provider)

        if provider == "openai":
            return OpenAIEmbeddingProvider(**kwargs)
        elif provider == "siliconflow":
            return SiliconFlowEmbeddingProvider(**kwargs)
        elif provider == "ollama":
            return OllamaEmbeddingProvider(**kwargs)
        else:
            raise ValueError(f"不支持的向量服务提供商: {provider}")

    @classmethod
    def get_default(cls) -> BaseEmbeddingProvider:
        """
        获取默认向量服务实例（单例）

        Returns:
            默认向量服务实例
        """
        provider = settings.embedding_provider

        if provider not in cls._instances:
            cls._instances[provider] = cls.create(provider)

        return cls._instances[provider]

    @classmethod
    async def close_all(cls):
        """关闭所有向量服务实例"""
        for instance in cls._instances.values():
            await instance.close()
        cls._instances.clear()


# 便捷函数
def get_embedding_provider(
    provider: EmbeddingProviderType | None = None,
) -> BaseEmbeddingProvider:
    """获取向量服务实例"""
    if provider:
        return EmbeddingFactory.create(provider)
    return EmbeddingFactory.get_default()
