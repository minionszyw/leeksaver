"""
API 依赖注入
"""

from typing import Annotated, AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.repositories.stock_repository import StockRepository, WatchlistRepository
from app.repositories.market_data_repository import MarketDataRepository


# 数据库会话依赖
SessionDep = Annotated[AsyncSession, Depends(get_session)]


# Repository 依赖
async def get_stock_repository(
    session: SessionDep,
) -> AsyncGenerator[StockRepository, None]:
    yield StockRepository(session)


async def get_watchlist_repository(
    session: SessionDep,
) -> AsyncGenerator[WatchlistRepository, None]:
    yield WatchlistRepository(session)


async def get_market_data_repository(
    session: SessionDep,
) -> AsyncGenerator[MarketDataRepository, None]:
    yield MarketDataRepository(session)


StockRepoDep = Annotated[StockRepository, Depends(get_stock_repository)]
WatchlistRepoDep = Annotated[WatchlistRepository, Depends(get_watchlist_repository)]
MarketDataRepoDep = Annotated[MarketDataRepository, Depends(get_market_data_repository)]
