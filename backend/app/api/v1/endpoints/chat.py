"""
对话 API 端点

支持 SSE 流式响应
"""

import json
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.agent.graph.workflow import run_agent, run_agent_stream

logger = get_logger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    """对话请求"""

    session_id: str = Field(..., description="会话 ID")
    message: str = Field(..., min_length=1, max_length=2000, description="用户消息")


class ChatResponse(BaseModel):
    """对话响应"""

    session_id: str
    message: str
    intent: str | None = None
    data: dict | None = None


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    对话端点 (非流式)

    用于简单的问答场景
    """
    logger.info("收到对话请求", session_id=request.session_id, message=request.message[:50])

    try:
        # 调用 Agent 工作流
        state = await run_agent(request.session_id, request.message)

        return ChatResponse(
            session_id=request.session_id,
            message=state.response or "抱歉，处理失败",
            intent=state.intent.category.value if state.intent else None,
            data=state.response_data,
        )
    except Exception as e:
        logger.error("对话处理失败", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


async def generate_sse_response(
    session_id: str, message: str
) -> AsyncGenerator[str, None]:
    """生成 SSE 流式响应"""
    try:
        async for event in run_agent_stream(session_id, message):
            data = {
                "type": event.type,
                "content": event.content,
                "data": event.data,
            }
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    except Exception as e:
        logger.error("流式响应错误", error=str(e))
        error_data = {"type": "error", "content": str(e)}
        yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"

    yield "data: [DONE]\n\n"


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """
    对话端点 (SSE 流式)

    用于需要实时反馈的场景
    """
    logger.info("收到流式对话请求", session_id=request.session_id)

    return StreamingResponse(
        generate_sse_response(request.session_id, request.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
