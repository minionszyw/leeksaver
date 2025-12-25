"""
向量服务抽象基类
"""

from abc import ABC, abstractmethod
from typing import List


class BaseEmbeddingProvider(ABC):
    """向量服务提供商抽象基类"""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """提供商名称"""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """模型名称"""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """向量维度"""
        pass

    @abstractmethod
    async def generate_embedding(self, text: str) -> List[float]:
        """
        生成单个文本的向量

        Args:
            text: 输入文本

        Returns:
            向量（浮点数列表）
        """
        pass

    @abstractmethod
    async def generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 100,
    ) -> List[List[float]]:
        """
        批量生成向量

        Args:
            texts: 文本列表
            batch_size: 内部批次大小（提供商限制）

        Returns:
            向量列表
        """
        pass

    async def close(self):
        """关闭客户端（可选实现）"""
        pass
