"""
测试配置和共享 fixtures
"""

import asyncio
import os
from datetime import datetime
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# 设置测试环境
os.environ["APP_ENV"] = "testing"
os.environ["DEBUG"] = "true"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost:5432/leeksaver_test"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def app():
    """创建测试应用"""
    from app.main import create_app

    app = create_app()
    yield app


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """创建测试客户端"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_llm():
    """模拟 LLM 客户端"""
    mock = AsyncMock()
    mock.chat.return_value = MagicMock(
        content='{"category": "fact_query", "sub_type": "price", "confidence": 0.9, "stock_codes": ["600519"], "stock_names": ["贵州茅台"]}'
    )
    return mock


@pytest.fixture
def mock_akshare():
    """模拟 AkShare 数据源"""
    import pandas as pd

    mock = MagicMock()

    # 模拟股票列表
    mock.stock_zh_a_spot_em.return_value = pd.DataFrame({
        "代码": ["600519", "000001", "300750"],
        "名称": ["贵州茅台", "平安银行", "宁德时代"],
        "最新价": [1800.0, 12.5, 200.0],
        "涨跌幅": [1.5, -0.5, 2.0],
        "成交量": [10000, 50000, 30000],
        "成交额": [18000000, 625000, 6000000],
    })

    # 模拟历史数据
    mock.stock_zh_a_hist.return_value = pd.DataFrame({
        "日期": pd.date_range("2024-01-01", periods=5),
        "开盘": [1750, 1760, 1780, 1790, 1800],
        "收盘": [1760, 1780, 1790, 1800, 1810],
        "最高": [1765, 1785, 1795, 1805, 1815],
        "最低": [1745, 1755, 1775, 1785, 1795],
        "成交量": [10000, 12000, 11000, 13000, 14000],
        "成交额": [17600000, 21360000, 19690000, 23400000, 25340000],
    })

    return mock


@pytest.fixture
def sample_stock():
    """示例股票数据"""
    return {
        "code": "600519",
        "name": "贵州茅台",
        "market": "sh",
        "asset_type": "stock",
        "industry": "白酒",
    }


@pytest.fixture
def sample_quote():
    """示例行情数据"""
    return {
        "code": "600519",
        "name": "贵州茅台",
        "price": 1800.0,
        "open": 1790.0,
        "high": 1810.0,
        "low": 1785.0,
        "close": 1800.0,
        "change": 10.0,
        "change_percent": 0.56,
        "volume": 10000,
        "amount": 18000000,
        "timestamp": datetime.now(),
    }


@pytest.fixture
def sample_intent():
    """示例意图"""
    from app.agent.intent.types import ParsedIntent, IntentCategory, FactQueryType

    return ParsedIntent(
        category=IntentCategory.FACT_QUERY,
        sub_type=FactQueryType.PRICE,
        confidence=0.9,
        stock_codes=["600519"],
        stock_names=["贵州茅台"],
        original_query="茅台今天涨了多少？",
    )


@pytest.fixture
def sample_agent_state(sample_intent):
    """示例 Agent 状态"""
    from app.agent.graph.state import AgentState

    return AgentState(
        session_id="test-session-001",
        user_message="茅台今天涨了多少？",
        intent=sample_intent,
    )
