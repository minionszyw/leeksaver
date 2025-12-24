"""
Ollama 本地模型适配器
"""

from typing import Any, AsyncIterator

import httpx

from app.config import settings
from app.core.logging import get_logger
from app.agent.llm.base import LLMBase, Message, LLMResponse

logger = get_logger(__name__)


class OllamaLLM(LLMBase):
    """Ollama 本地模型适配器"""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self.base_url = base_url or settings.ollama_base_url
        self.model = model or settings.ollama_model

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=120.0,  # 本地模型可能需要更长时间
        )

    @property
    def model_name(self) -> str:
        return self.model

    @property
    def provider(self) -> str:
        return "ollama"

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
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        logger.debug("Ollama 请求", model=self.model, messages_count=len(messages))

        response = await self._client.post("/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()

        return LLMResponse(
            content=data["message"]["content"],
            model=data["model"],
            usage={
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": data.get("prompt_eval_count", 0)
                + data.get("eval_count", 0),
            },
            finish_reason="stop" if data.get("done") else None,
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
            "stream": True,
            "options": {
                "temperature": temperature,
            },
        }

        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        async with self._client.stream("POST", "/api/chat", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line:
                    try:
                        import json

                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        if content:
                            yield content
                        if data.get("done"):
                            break
                    except Exception:
                        continue

    async def close(self):
        """关闭客户端"""
        await self._client.aclose()
