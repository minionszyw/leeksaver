"""
Agent 工作流集成测试
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agent.graph.state import AgentState, StreamEvent
from app.agent.graph.workflow import AgentWorkflow
from app.agent.intent.types import IntentCategory, FactQueryType, ParsedIntent


@pytest.mark.integration
class TestAgentWorkflow:
    """Agent 工作流测试"""

    @pytest.fixture
    def mock_session_manager(self):
        """模拟会话管理器"""
        mock = AsyncMock()
        mock.get_context.return_value = []
        mock.add_message.return_value = None
        return mock

    @pytest.fixture
    def mock_intent_router(self):
        """模拟意图路由器"""
        mock = AsyncMock()
        mock.classify.return_value = MagicMock(
            intent=ParsedIntent(
                category=IntentCategory.CHITCHAT,
                original_query="你好",
                confidence=0.95,
            ),
            needs_clarification=False,
        )
        return mock

    @pytest.mark.asyncio
    async def test_workflow_chitchat(self, mock_session_manager):
        """测试闲聊工作流"""
        with patch("app.agent.graph.workflow.session_manager", mock_session_manager):
            workflow = AgentWorkflow()
            state = await workflow.run("test-session", "你好")

            assert state.is_complete is True
            assert state.response is not None
            assert "您好" in state.response or "投研助手" in state.response

    @pytest.mark.asyncio
    async def test_workflow_stream_events(self, mock_session_manager):
        """测试流式事件"""
        with patch("app.agent.graph.workflow.session_manager", mock_session_manager):
            workflow = AgentWorkflow()
            events = []

            async for event in workflow.run_stream("test-session", "你好"):
                events.append(event)

            # 应该至少有 thinking 和 done 事件
            event_types = [e.type for e in events]
            assert "thinking" in event_types
            assert "done" in event_types

    @pytest.mark.asyncio
    async def test_workflow_max_steps(self, mock_session_manager):
        """测试最大步数限制"""
        with patch("app.agent.graph.workflow.session_manager", mock_session_manager):
            workflow = AgentWorkflow(max_steps=1)

            # 创建一个会无限循环的状态
            with patch("app.agent.graph.nodes.intent_router_node") as mock_node:
                mock_node.return_value = AgentState(
                    session_id="test",
                    user_message="test",
                    next_node="intent_router",  # 循环回自己
                    is_complete=False,
                )

                state = await workflow.run("test-session", "测试")

                # 应该因为超过最大步数而停止
                assert state.is_complete is True
                assert "超时" in (state.error or state.response or "")


@pytest.mark.integration
class TestStreamEvent:
    """流式事件测试"""

    def test_thinking_event(self):
        """测试思考事件"""
        event = StreamEvent(type="thinking", content="正在分析...")
        assert event.type == "thinking"
        assert event.content == "正在分析..."

    def test_tool_call_event(self):
        """测试工具调用事件"""
        event = StreamEvent(
            type="tool_call",
            content="执行查询...",
            data={"tool": "fact_query", "params": {"code": "600519"}},
        )
        assert event.type == "tool_call"
        assert event.data["tool"] == "fact_query"

    def test_response_event(self):
        """测试响应事件"""
        event = StreamEvent(
            type="response",
            content="茅台今日上涨 1.5%",
            data={"price": 1800, "change_pct": 1.5},
        )
        assert event.type == "response"
        assert event.data["price"] == 1800

    def test_error_event(self):
        """测试错误事件"""
        event = StreamEvent(type="error", content="查询失败")
        assert event.type == "error"

    def test_done_event(self):
        """测试完成事件"""
        event = StreamEvent(type="done")
        assert event.type == "done"
        assert event.content is None
