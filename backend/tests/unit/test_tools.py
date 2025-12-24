"""
工具系统单元测试
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agent.tools.base import ToolBase, ToolResult, ToolRegistry


class MockTool(ToolBase):
    """测试用模拟工具"""

    name = "mock_tool"
    description = "A mock tool for testing"

    async def execute(self, param1: str, param2: int = 10) -> ToolResult:
        return ToolResult(
            success=True,
            data={"param1": param1, "param2": param2},
        )


class FailingTool(ToolBase):
    """总是失败的工具"""

    name = "failing_tool"
    description = "A tool that always fails"

    async def execute(self) -> ToolResult:
        return ToolResult(
            success=False,
            error="This tool always fails",
        )


class TestToolBase:
    """ToolBase 测试"""

    @pytest.mark.asyncio
    async def test_tool_execution(self):
        """测试工具执行"""
        tool = MockTool()
        result = await tool.execute(param1="test", param2=20)

        assert result.success is True
        assert result.data["param1"] == "test"
        assert result.data["param2"] == 20

    @pytest.mark.asyncio
    async def test_tool_with_default_params(self):
        """测试默认参数"""
        tool = MockTool()
        result = await tool.execute(param1="test")

        assert result.success is True
        assert result.data["param2"] == 10

    @pytest.mark.asyncio
    async def test_failing_tool(self):
        """测试失败的工具"""
        tool = FailingTool()
        result = await tool.execute()

        assert result.success is False
        assert result.error == "This tool always fails"


class TestToolRegistry:
    """ToolRegistry 测试"""

    def setup_method(self):
        # 清理注册表
        ToolRegistry._tools = {}

    def test_register_tool(self):
        """测试工具注册"""
        ToolRegistry.register(MockTool)
        assert "mock_tool" in ToolRegistry._tools

    def test_get_tool(self):
        """测试获取工具"""
        ToolRegistry.register(MockTool)
        tool = ToolRegistry.get("mock_tool")
        assert tool is not None
        assert isinstance(tool, MockTool)

    def test_get_nonexistent_tool(self):
        """测试获取不存在的工具"""
        tool = ToolRegistry.get("nonexistent")
        assert tool is None

    @pytest.mark.asyncio
    async def test_execute_tool(self):
        """测试通过注册表执行工具"""
        ToolRegistry.register(MockTool)
        result = await ToolRegistry.execute("mock_tool", param1="test")

        assert result.success is True
        assert result.data["param1"] == "test"

    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool(self):
        """测试执行不存在的工具"""
        result = await ToolRegistry.execute("nonexistent")

        assert result.success is False
        assert "未找到工具" in result.error

    def test_list_tools(self):
        """测试列出所有工具"""
        ToolRegistry.register(MockTool)
        ToolRegistry.register(FailingTool)

        tools = ToolRegistry.list_tools()
        assert len(tools) == 2
        assert "mock_tool" in tools
        assert "failing_tool" in tools


class TestToolResult:
    """ToolResult 测试"""

    def test_success_result(self):
        """测试成功结果"""
        result = ToolResult(success=True, data={"key": "value"})
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None

    def test_failure_result(self):
        """测试失败结果"""
        result = ToolResult(success=False, error="Something went wrong")
        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.data is None
