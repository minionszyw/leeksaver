"""
API v1 路由聚合
"""

from fastapi import APIRouter

from app.api.v1.endpoints import chat, stocks, watchlist, sync, health

api_router = APIRouter()

# 注册各模块路由
api_router.include_router(health.router, prefix="/health", tags=["健康检查"])
api_router.include_router(chat.router, prefix="/chat", tags=["对话"])
api_router.include_router(stocks.router, prefix="/stocks", tags=["股票"])
api_router.include_router(watchlist.router, prefix="/watchlist", tags=["自选股"])
api_router.include_router(sync.router, prefix="/sync", tags=["数据同步"])
