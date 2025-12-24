"""
OpenAI LLM 适配器
"""

from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from app.config import settings
from app.core.logging import get_logger
from app.agent.llm.base import LLMBase, Message, LLMResponse

logger = get_logger(__name__)


class OpenAILLM(LLMBase):
    """OpenAI LLM 适配器"""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.openai_model

        self._client = AsyncOpenAI(api_key=self.api_key)

    @property
    def model_name(self) -> str:
        return self.model

    @property
    def provider(self) -> str:
        return "openai"

    async def chat(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> LLMResponse:
        """聊天补全"""
        logger.debug("OpenAI 请求", model=self.model, messages_count=len(messages))

        response = await self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        choice = response.choices[0]
        usage = (
            {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
            if response.usage
            else None
        )

        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            usage=usage,
            finish_reason=choice.finish_reason,
        )

    async def chat_stream(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """流式聊天补全"""
        stream = await self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def chat_with_tools(
        self,
        messages: list[Message],
        tools: list[dict],
        temperature: float = 0.7,
        **kwargs,
    ) -> dict[str, Any]:
        """带工具调用的聊天"""
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
            tools=tools,
            tool_choice="auto",
        )

        choice = response.choices[0]
        message = choice.message

        tool_calls = None
        if message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]

        return {
            "content": message.content,
            "tool_calls": tool_calls,
            "finish_reason": choice.finish_reason,
        }

    async def close(self):
        """关闭客户端"""
        await self._client.close()
