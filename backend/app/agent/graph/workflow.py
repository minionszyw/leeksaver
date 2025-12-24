"""
LangGraph 工作流编排

定义 Agent 的完整执行流程
"""

from typing import AsyncIterator

from app.core.logging import get_logger
from app.agent.graph.state import AgentState, StreamEvent
from app.agent.graph.nodes import (
    intent_router_node,
    clarification_node,
    fact_query_node,
    deep_analysis_node,
    tool_executor_node,
    interpreter_node,
    chitchat_node,
    out_of_scope_node,
    error_handler_node,
)
from app.agent.session.manager import session_manager

logger = get_logger(__name__)

# 节点映射
NODE_MAP = {
    "intent_router": intent_router_node,
    "clarification": clarification_node,
    "fact_query": fact_query_node,
    "deep_analysis": deep_analysis_node,
    "tool_executor": tool_executor_node,
    "interpreter": interpreter_node,
    "chitchat": chitchat_node,
    "out_of_scope": out_of_scope_node,
    "error_handler": error_handler_node,
}


class AgentWorkflow:
    """
    Agent 工作流

    实现从用户输入到最终响应的完整处理流程
    """

    def __init__(self, max_steps: int = 10):
        self.max_steps = max_steps

    async def run(self, session_id: str, user_message: str) -> AgentState:
        """
        运行工作流

        Args:
            session_id: 会话 ID
            user_message: 用户消息

        Returns:
            最终状态
        """
        # 获取会话上下文
        context = await session_manager.get_context(session_id, n=5)

        state = AgentState(
            session_id=session_id,
            user_message=user_message,
            conversation_history=context,
        )

        logger.info("开始工作流", session_id=session_id, message=user_message[:50])

        # 保存用户消息到会话
        await session_manager.add_message(session_id, "user", user_message)

        # 从意图路由开始
        state = await intent_router_node(state)

        # 循环执行直到完成
        steps = 0
        while not state.is_complete and steps < self.max_steps:
            steps += 1
            next_node = state.next_node

            if not next_node or next_node not in NODE_MAP:
                logger.warning("无效的下一节点", next_node=next_node)
                state.error = f"工作流错误：无效节点 {next_node}"
                state = await error_handler_node(state)
                break

            logger.debug("执行节点", node=next_node, step=steps)
            node_func = NODE_MAP[next_node]
            state = await node_func(state)

        if steps >= self.max_steps:
            logger.warning("工作流超过最大步数", steps=steps)
            state.error = "处理超时"
            state = await error_handler_node(state)

        # 保存助手回复到会话
        if state.response:
            await session_manager.add_message(
                session_id,
                "assistant",
                state.response,
                data=state.response_data,
            )

        logger.info("工作流完成", session_id=session_id, steps=steps)
        return state

    async def run_stream(
        self, session_id: str, user_message: str
    ) -> AsyncIterator[StreamEvent]:
        """
        流式运行工作流

        Args:
            session_id: 会话 ID
            user_message: 用户消息

        Yields:
            流式事件
        """
        # 获取会话上下文
        context = await session_manager.get_context(session_id, n=5)

        state = AgentState(
            session_id=session_id,
            user_message=user_message,
            conversation_history=context,
        )

        # 保存用户消息到会话
        await session_manager.add_message(session_id, "user", user_message)

        yield StreamEvent(type="thinking", content="正在理解您的问题...")

        # 意图路由
        state = await intent_router_node(state)

        if state.intent:
            yield StreamEvent(
                type="thinking",
                content=f"识别意图：{state.intent.category.value}",
                data={"intent": state.intent.category.value},
            )

        # 循环执行
        steps = 0
        while not state.is_complete and steps < self.max_steps:
            steps += 1
            next_node = state.next_node

            if not next_node or next_node not in NODE_MAP:
                state.error = f"工作流错误"
                state = await error_handler_node(state)
                break

            # 工具调用事件
            if next_node == "tool_executor" and state.tool_name:
                yield StreamEvent(
                    type="tool_call",
                    content=f"执行 {state.tool_name}...",
                    data={"tool": state.tool_name, "params": state.tool_params},
                )

            node_func = NODE_MAP[next_node]
            state = await node_func(state)

            # 工具结果事件
            if state.current_node == "tool_executor" and state.tool_result:
                yield StreamEvent(
                    type="tool_result",
                    content="数据获取完成",
                    data=state.tool_result,
                )

        # 保存助手回复到会话
        if state.response:
            await session_manager.add_message(
                session_id,
                "assistant",
                state.response,
                data=state.response_data,
            )

        # 最终响应
        if state.response:
            yield StreamEvent(
                type="response",
                content=state.response,
                data=state.response_data,
            )
        elif state.error:
            yield StreamEvent(
                type="error",
                content=state.error,
            )

        yield StreamEvent(type="done")


# 便捷函数
async def run_agent(session_id: str, user_message: str) -> AgentState:
    """运行 Agent"""
    workflow = AgentWorkflow()
    return await workflow.run(session_id, user_message)


async def run_agent_stream(
    session_id: str, user_message: str
) -> AsyncIterator[StreamEvent]:
    """流式运行 Agent"""
    workflow = AgentWorkflow()
    async for event in workflow.run_stream(session_id, user_message):
        yield event
