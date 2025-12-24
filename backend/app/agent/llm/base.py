"""
LLM 抽象基类

提供统一的 LLM 调用接口，支持多服务商切换
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from pydantic import BaseModel, Field


class Message(BaseModel):
    """消息"""

    role: str = Field(..., description="角色: system/user/assistant")
    content: str = Field(..., description="内容")


class LLMResponse(BaseModel):
    """LLM 响应"""

    content: str = Field(..., description="响应内容")
    model: str = Field(..., description="使用的模型")
    usage: dict[str, Any] | None = Field(None, description="Token 使用情况")
    finish_reason: str | None = Field(None, description="结束原因")


class LLMBase(ABC):
    """LLM 抽象基类"""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """模型名称"""
        pass

    @property
    @abstractmethod
    def provider(self) -> str:
        """服务商名称"""
        pass

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> LLMResponse:
        """
        聊天补全

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            **kwargs: 其他参数

        Returns:
            LLM 响应
        """
        pass

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        流式聊天补全

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            **kwargs: 其他参数

        Yields:
            响应文本片段
        """
        pass

    async def chat_with_tools(
        self,
        messages: list[Message],
        tools: list[dict],
        temperature: float = 0.7,
        **kwargs,
    ) -> dict[str, Any]:
        """
        带工具调用的聊天

        Args:
            messages: 消息列表
            tools: 工具定义列表
            temperature: 温度参数
            **kwargs: 其他参数

        Returns:
            包含工具调用的响应
        """
        raise NotImplementedError("该 LLM 不支持工具调用")

    def format_system_prompt(self, prompt: str) -> Message:
        """格式化系统提示"""
        return Message(role="system", content=prompt)

    def format_user_message(self, content: str) -> Message:
        """格式化用户消息"""
        return Message(role="user", content=content)

    def format_assistant_message(self, content: str) -> Message:
        """格式化助手消息"""
        return Message(role="assistant", content=content)
