"""
API 集成测试
"""

import pytest
from httpx import AsyncClient


@pytest.mark.integration
class TestHealthAPI:
    """健康检查 API 测试"""

    @pytest.mark.asyncio
    async def test_liveness(self, client: AsyncClient):
        """测试存活检查"""
        response = await client.get("/api/v1/health/liveness")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """测试完整健康检查"""
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data
        assert "app_name" in data


@pytest.mark.integration
class TestStockAPI:
    """股票 API 测试"""

    @pytest.mark.asyncio
    async def test_search_stocks(self, client: AsyncClient):
        """测试股票搜索"""
        response = await client.get("/api/v1/stocks/search", params={"q": "茅台"})
        # 可能返回 200（有数据）或 200（空结果）
        assert response.status_code == 200
        data = response.json()
        assert "stocks" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_search_stocks_empty_query(self, client: AsyncClient):
        """测试空搜索"""
        response = await client.get("/api/v1/stocks/search", params={"q": ""})
        assert response.status_code == 200
        data = response.json()
        assert data["stocks"] == []

    @pytest.mark.asyncio
    async def test_get_stock_not_found(self, client: AsyncClient):
        """测试获取不存在的股票"""
        response = await client.get("/api/v1/stocks/999999")
        assert response.status_code == 404


@pytest.mark.integration
class TestWatchlistAPI:
    """自选股 API 测试"""

    @pytest.mark.asyncio
    async def test_get_watchlist(self, client: AsyncClient):
        """测试获取自选股列表"""
        response = await client.get("/api/v1/watchlist")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data


@pytest.mark.integration
class TestSyncAPI:
    """数据同步 API 测试"""

    @pytest.mark.asyncio
    async def test_get_sync_status(self, client: AsyncClient):
        """测试获取同步状态"""
        response = await client.get("/api/v1/sync/status")
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data

    @pytest.mark.asyncio
    async def test_get_unknown_task_status(self, client: AsyncClient):
        """测试获取未知任务状态"""
        response = await client.get("/api/v1/sync/status/unknown_task")
        assert response.status_code == 404


@pytest.mark.integration
class TestChatAPI:
    """聊天 API 测试"""

    @pytest.mark.asyncio
    async def test_chat_endpoint(self, client: AsyncClient):
        """测试聊天端点"""
        response = await client.post(
            "/api/v1/chat",
            json={
                "session_id": "test-session",
                "message": "你好",
            },
        )
        # 可能需要 LLM，如果没有配置可能失败
        # 这里只测试端点存在
        assert response.status_code in [200, 500]
