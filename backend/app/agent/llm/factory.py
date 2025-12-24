"""
LLM 工厂

根据配置创建对应的 LLM 实例
"""

from typing import Literal

from app.config import settings
from app.core.logging import get_logger
from app.agent.llm.base import LLMBase
from app.agent.llm.providers.deepseek import DeepSeekLLM
from app.agent.llm.providers.openai import OpenAILLM
from app.agent.llm.providers.ollama import OllamaLLM

logger = get_logger(__name__)

LLMProvider = Literal["deepseek", "openai", "ollama"]


class LLMFactory:
    """LLM 工厂"""

    _instances: dict[str, LLMBase] = {}

    @classmethod
    def create(
        cls,
        provider: LLMProvider | None = None,
        **kwargs,
    ) -> LLMBase:
        """
        创建 LLM 实例

        Args:
            provider: 服务商名称，默认从配置读取
            **kwargs: 传递给具体 LLM 的参数

        Returns:
            LLM 实例
        """
        provider = provider or settings.llm_provider

        logger.info("创建 LLM 实例", provider=provider)

        if provider == "deepseek":
            return DeepSeekLLM(**kwargs)
        elif provider == "openai":
            return OpenAILLM(**kwargs)
        elif provider == "ollama":
            return OllamaLLM(**kwargs)
        else:
            raise ValueError(f"不支持的 LLM 服务商: {provider}")

    @classmethod
    def get_default(cls) -> LLMBase:
        """
        获取默认 LLM 实例（单例）

        Returns:
            默认 LLM 实例
        """
        provider = settings.llm_provider

        if provider not in cls._instances:
            cls._instances[provider] = cls.create(provider)

        return cls._instances[provider]

    @classmethod
    async def close_all(cls):
        """关闭所有 LLM 实例"""
        for instance in cls._instances.values():
            await instance.close()
        cls._instances.clear()


# 便捷函数
def get_llm(provider: LLMProvider | None = None) -> LLMBase:
    """获取 LLM 实例"""
    if provider:
        return LLMFactory.create(provider)
    return LLMFactory.get_default()
