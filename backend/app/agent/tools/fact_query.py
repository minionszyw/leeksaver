"""
数据速查工具

提供股票价格、估值、历史数据等快速查询能力
"""

from datetime import date, timedelta
from decimal import Decimal

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.repositories.stock_repository import StockRepository
from app.repositories.market_data_repository import MarketDataRepository
from app.agent.tools.base import ToolBase, ToolResult, ToolRegistry
from app.agent.schema.tool_schemas import (
    FactQueryInput,
    FactQueryOutput,
    PriceData,
    ValuationData,
    HistoryData,
)

logger = get_logger(__name__)


class FactQueryTool(ToolBase):
    """数据速查工具"""

    name = "fact_query"
    description = "查询股票的基本数据，包括价格、估值、历史涨跌等"
    input_schema = FactQueryInput
    output_schema = FactQueryOutput

    async def execute(self, **kwargs) -> ToolResult:
        """执行数据查询"""
        try:
            input_data = self.validate_input(**kwargs)
            code = input_data.stock_code
            # 规范化股票代码：去掉市场后缀（如 .SH, .SZ）
            code = code.split('.')[0] if '.' in code else code
            query_type = input_data.query_type

            async with get_db_session() as session:
                stock_repo = StockRepository(session)
                market_repo = MarketDataRepository(session)

                # 获取股票基本信息
                stock = await stock_repo.get_by_code(code)
                if not stock:
                    return ToolResult(
                        success=False,
                        error=f"未找到股票: {code}",
                    )

                # 根据查询类型执行不同逻辑
                if query_type == "price":
                    data = await self._query_price(code, stock.name, market_repo)
                elif query_type == "valuation":
                    data = await self._query_valuation(code, stock.name, market_repo)
                elif query_type == "history":
                    data = await self._query_history(
                        code,
                        stock.name,
                        market_repo,
                        input_data.start_date,
                        input_data.end_date,
                    )
                elif query_type == "basic_info":
                    data = {
                        "code": code,
                        "name": stock.name,
                        "market": stock.market,
                        "asset_type": stock.asset_type,
                        "industry": stock.industry,
                        "list_date": stock.list_date.isoformat() if stock.list_date else None,
                    }
                else:
                    return ToolResult(
                        success=False,
                        error=f"不支持的查询类型: {query_type}",
                    )

                output = FactQueryOutput(
                    success=True,
                    query_type=query_type,
                    data=data,
                )

                return ToolResult(success=True, data=output)

        except Exception as e:
            logger.error("数据查询失败", error=str(e))
            return ToolResult(success=False, error=str(e))

    async def _query_price(
        self, code: str, name: str, repo: MarketDataRepository
    ) -> PriceData:
        """查询价格"""
        quote = await repo.get_latest_quote(code)

        if not quote:
            return PriceData(
                code=code,
                name=name,
                timestamp=date.today().isoformat(),
            )

        return PriceData(
            code=code,
            name=name,
            price=self._to_float(quote.close),
            change=self._to_float(quote.change),
            change_pct=self._to_float(quote.change_pct),
            open=self._to_float(quote.open),
            high=self._to_float(quote.high),
            low=self._to_float(quote.low),
            volume=quote.volume,
            amount=self._to_float(quote.amount),
            timestamp=quote.trade_date.isoformat(),
        )

    async def _query_valuation(
        self, code: str, name: str, repo: MarketDataRepository
    ) -> ValuationData:
        """查询估值"""
        # 注意：实际估值数据需要从专门的数据源获取
        # 这里暂时返回占位数据
        quote = await repo.get_latest_quote(code)
        timestamp = quote.trade_date.isoformat() if quote else date.today().isoformat()

        return ValuationData(
            code=code,
            name=name,
            pe=None,  # 需要从专门接口获取
            pb=None,
            ps=None,
            market_cap=None,
            circulating_cap=None,
            timestamp=timestamp,
        )

    async def _query_history(
        self,
        code: str,
        name: str,
        repo: MarketDataRepository,
        start_date: date | None,
        end_date: date | None,
    ) -> HistoryData:
        """查询历史数据"""
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()

        quotes = await repo.get_daily_quotes(code, start_date, end_date)

        if not quotes:
            return HistoryData(
                code=code,
                name=name,
                period=f"{start_date} 至 {end_date}",
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                data_points=0,
            )

        # 计算区间涨跌幅
        first_close = self._to_float(quotes[-1].close) if quotes[-1].close else None
        last_close = self._to_float(quotes[0].close) if quotes[0].close else None

        change_pct = None
        if first_close and last_close and first_close > 0:
            change_pct = round((last_close - first_close) / first_close * 100, 2)

        # 区间最高最低
        highs = [self._to_float(q.high) for q in quotes if q.high]
        lows = [self._to_float(q.low) for q in quotes if q.low]

        return HistoryData(
            code=code,
            name=name,
            period=f"{start_date} 至 {end_date}",
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            change_pct=change_pct,
            high=max(highs) if highs else None,
            low=min(lows) if lows else None,
            data_points=len(quotes),
        )

    @staticmethod
    def _to_float(value: Decimal | None) -> float | None:
        """Decimal 转 float"""
        return float(value) if value is not None else None


# 注册工具
ToolRegistry.register(FactQueryTool())
