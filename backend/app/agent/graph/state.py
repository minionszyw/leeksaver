"""
LangGraph 状态定义

定义工作流的状态结构
"""

from typing import Any, Literal
from pydantic import BaseModel, Field

from app.agent.intent.types import ParsedIntent


class AgentState(BaseModel):
    """Agent 工作流状态"""

    # 会话信息
    session_id: str = Field(..., description="会话 ID")

    # 用户输入
    user_message: str = Field(..., description="用户消息")

    # 会话历史
    conversation_history: list[dict[str, str]] = Field(
        default_factory=list, description="会话历史上下文"
    )

    # 意图解析
    intent: ParsedIntent | None = Field(None, description="解析的意图")
    needs_clarification: bool = Field(False, description="是否需要澄清")
    clarification_question: str | None = Field(None, description="澄清问题")

    # 工具执行
    tool_name: str | None = Field(None, description="待执行的工具名称")
    tool_params: dict[str, Any] | None = Field(None, description="工具参数")
    tool_result: dict[str, Any] | None = Field(None, description="工具执行结果")
    tool_error: str | None = Field(None, description="工具执行错误")

    # 数据新鲜度
    data_fresh: bool = Field(True, description="数据是否新鲜")
    sync_triggered: bool = Field(False, description="是否已触发同步")

    # 最终响应
    response: str | None = Field(None, description="最终响应")
    response_data: dict[str, Any] | None = Field(None, description="响应数据")

    # 流程控制
    current_node: str = Field(default="start", description="当前节点")
    next_node: str | None = Field(None, description="下一节点")
    retry_count: int = Field(0, description="重试次数")
    max_retries: int = Field(2, description="最大重试次数")

    # 错误处理
    error: str | None = Field(None, description="错误信息")
    is_complete: bool = Field(False, description="是否完成")

    class Config:
        arbitrary_types_allowed = True


class StreamEvent(BaseModel):
    """流式事件"""

    type: Literal["thinking", "tool_call", "tool_result", "response", "error", "done"]
    content: str | None = None
    data: dict[str, Any] | None = None
