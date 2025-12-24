"""
DeepSeek LLM 适配器
"""

from typing import Any, AsyncIterator

import httpx

from app.config import settings
from app.core.logging import get_logger
from app.agent.llm.base import LLMBase, Message, LLMResponse

logger = get_logger(__name__)


class DeepSeekLLM(LLMBase):
    """DeepSeek LLM 适配器"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or settings.deepseek_api_key
        self.base_url = base_url or settings.deepseek_base_url
        self.model = model or settings.deepseek_model

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )

    @property
    def model_name(self) -> str:
        return self.model

    @property
    def provider(self) -> str:
        return "deepseek"

    async def chat(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> LLMResponse:
        """聊天补全"""
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "stream": False,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        logger.debug("DeepSeek 请求", model=self.model, messages_count=len(messages))

        response = await self._client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        usage = data.get("usage")

        return LLMResponse(
            content=choice["message"]["content"],
            model=data["model"],
            usage=usage,
            finish_reason=choice.get("finish_reason"),
        )

    async def chat_stream(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """流式聊天补全"""
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "stream": True,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        async with self._client.stream(
            "POST", "/chat/completions", json=payload
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        import json

                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except Exception:
                        continue

    async def chat_with_tools(
        self,
        messages: list[Message],
        tools: list[dict],
        temperature: float = 0.7,
        **kwargs,
    ) -> dict[str, Any]:
        """带工具调用的聊天"""
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "tools": tools,
            "tool_choice": "auto",
        }

        response = await self._client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        message = choice["message"]

        return {
            "content": message.get("content"),
            "tool_calls": message.get("tool_calls"),
            "finish_reason": choice.get("finish_reason"),
        }

    async def close(self):
        """关闭客户端"""
        await self._client.aclose()
