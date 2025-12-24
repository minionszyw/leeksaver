"""
股票信息 API 端点
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.v1.deps import StockRepoDep, MarketDataRepoDep

router = APIRouter()


class StockInfo(BaseModel):
    """股票基本信息"""

    code: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    market: str = Field(..., description="市场 (SH/SZ)")
    asset_type: str = Field(..., description="类型 (stock/etf)")
    industry: str | None = Field(None, description="行业")

    model_config = {"from_attributes": True}


class StockQuote(BaseModel):
    """股票行情"""

    code: str
    name: str
    price: float | None = Field(None, description="最新价")
    change: float | None = Field(None, description="涨跌额")
    change_pct: float | None = Field(None, description="涨跌幅 (%)")
    volume: int | None = Field(None, description="成交量")
    amount: float | None = Field(None, description="成交额")
    timestamp: str = Field(..., description="数据时间戳")


class StockSearchResult(BaseModel):
    """股票搜索结果"""

    stocks: list[StockInfo]
    total: int


@router.get("/search", response_model=StockSearchResult)
async def search_stocks(
    repo: StockRepoDep,
    q: str = Query(..., min_length=1, max_length=20, description="搜索关键词"),
    limit: int = Query(default=10, ge=1, le=50, description="返回数量限制"),
):
    """
    搜索股票

    支持按代码或名称模糊搜索
    """
    stocks = await repo.search(q, limit)
    return StockSearchResult(
        stocks=[StockInfo.model_validate(s) for s in stocks],
        total=len(stocks),
    )


@router.get("/{code}", response_model=StockInfo)
async def get_stock(code: str, repo: StockRepoDep):
    """
    获取股票详情

    Args:
        code: 股票代码 (如 000001, 600519)
    """
    stock = await repo.get_by_code(code)
    if not stock:
        raise HTTPException(status_code=404, detail=f"股票 {code} 不存在")
    return StockInfo.model_validate(stock)


@router.get("/{code}/quote", response_model=StockQuote)
async def get_stock_quote(
    code: str,
    stock_repo: StockRepoDep,
    market_repo: MarketDataRepoDep,
):
    """
    获取股票最新行情

    Args:
        code: 股票代码
    """
    stock = await stock_repo.get_by_code(code)
    if not stock:
        raise HTTPException(status_code=404, detail=f"股票 {code} 不存在")

    quote = await market_repo.get_latest_quote(code)
    if not quote:
        raise HTTPException(status_code=404, detail=f"股票 {code} 暂无行情数据")

    return StockQuote(
        code=code,
        name=stock.name,
        price=float(quote.close) if quote.close else None,
        change=float(quote.change) if quote.change else None,
        change_pct=float(quote.change_pct) if quote.change_pct else None,
        volume=quote.volume,
        amount=float(quote.amount) if quote.amount else None,
        timestamp=quote.trade_date.isoformat(),
    )
