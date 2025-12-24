"""
意图路由器单元测试
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agent.intent.router import IntentRouter, COMMON_STOCK_NAMES
from app.agent.intent.types import IntentCategory, FactQueryType


class TestIntentRouterQuickMatch:
    """快速规则匹配测试"""

    def setup_method(self):
        self.router = IntentRouter(llm=AsyncMock())

    def test_greeting_detection(self):
        """测试问候语识别"""
        result = self.router._quick_match("你好")
        assert result is not None
        assert result.intent.category == IntentCategory.CHITCHAT

    def test_price_query_with_name(self):
        """测试带股票名称的价格查询"""
        result = self.router._quick_match("茅台今天涨了多少？")
        assert result is not None
        assert result.intent.category == IntentCategory.FACT_QUERY
        assert result.intent.sub_type == FactQueryType.PRICE
        assert "600519" in result.intent.stock_codes

    def test_price_query_with_code(self):
        """测试带股票代码的价格查询"""
        result = self.router._quick_match("600519 的价格是多少？")
        assert result is not None
        assert result.intent.category == IntentCategory.FACT_QUERY
        assert "600519" in result.intent.stock_codes

    def test_valuation_query(self):
        """测试估值查询"""
        result = self.router._quick_match("茅台的市盈率是多少？")
        assert result is not None
        assert result.intent.category == IntentCategory.FACT_QUERY
        assert result.intent.sub_type == FactQueryType.VALUATION

    def test_no_match(self):
        """测试无法快速匹配的情况"""
        result = self.router._quick_match("分析一下市场走势")
        assert result is None


class TestIntentRouterClassify:
    """LLM 分类测试"""

    @pytest.mark.asyncio
    async def test_classify_with_quick_match(self):
        """测试快速匹配走快速路径"""
        router = IntentRouter(llm=AsyncMock())
        result = await router.classify("你好")

        assert result.intent.category == IntentCategory.CHITCHAT
        # LLM 不应该被调用
        router.llm.chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_classify_with_llm(self, mock_llm):
        """测试 LLM 分类"""
        router = IntentRouter(llm=mock_llm)
        result = await router.classify("帮我分析一下最近的市场趋势")

        # LLM 应该被调用
        mock_llm.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_classify_with_history(self, mock_llm):
        """测试带历史上下文的分类"""
        router = IntentRouter(llm=mock_llm)
        history = [
            {"role": "user", "content": "茅台怎么样？"},
            {"role": "assistant", "content": "茅台目前价格 1800 元..."},
        ]

        await router.classify("那宁德时代呢？", history=history)

        # 检查 LLM 调用包含历史
        call_args = mock_llm.chat.call_args
        messages = call_args[0][0]
        assert any("对话历史" in str(m.content) for m in messages)


class TestStockCodeExtraction:
    """股票代码提取测试"""

    def test_common_stock_names(self):
        """测试常见股票名称映射"""
        assert "茅台" in COMMON_STOCK_NAMES
        assert COMMON_STOCK_NAMES["茅台"] == "600519"
        assert COMMON_STOCK_NAMES["宁德时代"] == "300750"

    def test_stock_code_pattern(self):
        """测试股票代码正则"""
        from app.agent.intent.router import STOCK_CODE_PATTERN

        text = "看看 600519 和 000001 的走势"
        codes = STOCK_CODE_PATTERN.findall(text)
        assert "600519" in codes
        assert "000001" in codes

    def test_invalid_code_not_matched(self):
        """测试无效代码不匹配"""
        from app.agent.intent.router import STOCK_CODE_PATTERN

        text = "123456 不是有效代码"
        codes = STOCK_CODE_PATTERN.findall(text)
        assert "123456" not in codes
