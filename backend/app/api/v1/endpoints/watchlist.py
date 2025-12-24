"""
自选股 API 端点
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.deps import WatchlistRepoDep, StockRepoDep, MarketDataRepoDep

router = APIRouter()


class WatchlistItem(BaseModel):
    """自选股项"""

    code: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    price: float | None = Field(None, description="最新价")
    change_pct: float | None = Field(None, description="涨跌幅 (%)")
    added_at: str = Field(..., description="添加时间")


class WatchlistResponse(BaseModel):
    """自选股列表响应"""

    items: list[WatchlistItem]
    total: int


@router.get("", response_model=WatchlistResponse)
async def get_watchlist(
    watchlist_repo: WatchlistRepoDep,
    stock_repo: StockRepoDep,
    market_repo: MarketDataRepoDep,
):
    """
    获取自选股列表
    """
    watchlist = await watchlist_repo.get_all()
    items = []

    for w in watchlist:
        stock = await stock_repo.get_by_code(w.code)
        quote = await market_repo.get_latest_quote(w.code)

        items.append(
            WatchlistItem(
                code=w.code,
                name=stock.name if stock else w.code,
                price=float(quote.close) if quote and quote.close else None,
                change_pct=float(quote.change_pct) if quote and quote.change_pct else None,
                added_at=w.created_at.isoformat(),
            )
        )

    return WatchlistResponse(items=items, total=len(items))


@router.post("/{code}")
async def add_to_watchlist(
    code: str,
    watchlist_repo: WatchlistRepoDep,
    stock_repo: StockRepoDep,
):
    """
    添加股票到自选

    Args:
        code: 股票代码
    """
    # 检查股票是否存在
    stock = await stock_repo.get_by_code(code)
    if not stock:
        raise HTTPException(status_code=404, detail=f"股票 {code} 不存在")

    # 检查是否已在自选
    if await watchlist_repo.exists(code):
        raise HTTPException(status_code=400, detail=f"股票 {code} 已在自选中")

    await watchlist_repo.add(code)
    return {"message": f"已添加 {code} 到自选", "code": code}


@router.delete("/{code}")
async def remove_from_watchlist(code: str, watchlist_repo: WatchlistRepoDep):
    """
    从自选中移除股票

    Args:
        code: 股票代码
    """
    removed = await watchlist_repo.remove(code)
    if not removed:
        raise HTTPException(status_code=404, detail=f"股票 {code} 不在自选中")

    return {"message": f"已从自选移除 {code}", "code": code}
