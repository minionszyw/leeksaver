"""
基本面分析工具

提供股票基本面分析能力，包括财务指标和经营状况
"""

from datetime import date
from decimal import Decimal

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.repositories.stock_repository import StockRepository
from app.repositories.market_data_repository import MarketDataRepository
from app.repositories.financial_repository import FinancialRepository
from app.agent.tools.base import ToolBase, ToolResult, ToolRegistry
from app.agent.schema.tool_schemas import (
    FundamentalInput,
    FundamentalOutput,
    FinancialMetrics,
)

logger = get_logger(__name__)


class FundamentalTool(ToolBase):
    """基本面分析工具"""

    name = "fundamental_analysis"
    description = "分析股票的基本面，包括财务指标和经营状况"
    input_schema = FundamentalInput
    output_schema = FundamentalOutput

    async def execute(self, **kwargs) -> ToolResult:
        """执行基本面分析"""
        try:
            input_data = self.validate_input(**kwargs)
            code = input_data.stock_code
            # 规范化股票代码：去掉市场后缀（如 .SH, .SZ）
            code = code.split('.')[0] if '.' in code else code

            async with get_db_session() as session:
                stock_repo = StockRepository(session)
                market_repo = MarketDataRepository(session)
                financial_repo = FinancialRepository(session)

                # 获取股票基本信息
                stock = await stock_repo.get_by_code(code)
                if not stock:
                    return ToolResult(success=False, error=f"未找到股票: {code}")

                # 获取最新行情用于计算市值等
                quote = await market_repo.get_latest_quote(code)

                # 获取财务数据
                metrics = await self._get_financial_metrics(financial_repo, code)

                # 分析亮点和风险
                highlights, risks = self._analyze_financials(metrics)

                # 生成分析总结
                summary = self._generate_summary(stock.name, metrics, highlights, risks)

                output = FundamentalOutput(
                    success=True,
                    code=code,
                    name=stock.name,
                    industry=stock.industry,
                    metrics=metrics,
                    highlights=highlights,
                    risks=risks,
                    summary=summary,
                )

                return ToolResult(success=True, data=output)

        except Exception as e:
            logger.error("基本面分析失败", error=str(e))
            return ToolResult(success=False, error=str(e))

    async def _get_financial_metrics(
        self, repo: FinancialRepository, code: str
    ) -> FinancialMetrics:
        """
        获取财务指标
        """
        statement = await repo.get_latest_statement(code)
        
        if not statement:
            return FinancialMetrics(
                revenue=None,
                revenue_yoy=None,
                net_profit=None,
                profit_yoy=None,
                roe=None,
                gross_margin=None,
                debt_ratio=None,
            )

        return FinancialMetrics(
            revenue=statement.total_revenue,
            revenue_yoy=statement.revenue_yoy,
            net_profit=statement.net_profit,
            profit_yoy=statement.net_profit_yoy,
            roe=statement.roe_weighted,
            gross_margin=statement.gross_profit_margin,
            debt_ratio=statement.debt_asset_ratio,
        )

    def _analyze_financials(
        self, metrics: FinancialMetrics
    ) -> tuple[list[str], list[str]]:
        """分析财务数据，提取亮点和风险"""
        highlights = []
        risks = []

        # ROE 分析
        if metrics.roe is not None:
            if metrics.roe > 15:
                highlights.append(f"ROE 达 {metrics.roe:.1f}%，盈利能力优秀")
            elif metrics.roe < 5:
                risks.append(f"ROE 仅 {metrics.roe:.1f}%，盈利能力偏弱")

        # 营收增长分析
        if metrics.revenue_yoy is not None:
            if metrics.revenue_yoy > 20:
                highlights.append(f"营收同比增长 {metrics.revenue_yoy:.1f}%，成长性良好")
            elif metrics.revenue_yoy < -10:
                risks.append(f"营收同比下降 {abs(metrics.revenue_yoy):.1f}%，需关注业务发展")

        # 净利润增长分析
        if metrics.profit_yoy is not None:
            if metrics.profit_yoy > 30:
                highlights.append(f"净利润同比增长 {metrics.profit_yoy:.1f}%，业绩亮眼")
            elif metrics.profit_yoy < -20:
                risks.append(f"净利润同比下降 {abs(metrics.profit_yoy):.1f}%，盈利承压")

        # 毛利率分析
        if metrics.gross_margin is not None:
            if metrics.gross_margin > 40:
                highlights.append(f"毛利率 {metrics.gross_margin:.1f}%，产品竞争力强")
            elif metrics.gross_margin < 15:
                risks.append(f"毛利率仅 {metrics.gross_margin:.1f}%，盈利空间有限")

        # 负债率分析
        if metrics.debt_ratio is not None:
            if metrics.debt_ratio > 70:
                risks.append(f"资产负债率 {metrics.debt_ratio:.1f}%，财务杠杆较高")
            elif metrics.debt_ratio < 30:
                highlights.append(f"资产负债率 {metrics.debt_ratio:.1f}%，财务结构稳健")

        # 如果数据不足
        if not highlights and not risks:
            highlights.append("暂无详细财务数据，建议关注最新财报")

        return highlights, risks

    def _generate_summary(
        self,
        name: str,
        metrics: FinancialMetrics,
        highlights: list[str],
        risks: list[str],
    ) -> str:
        """生成基本面分析总结"""
        summary_parts = [f"{name} 基本面分析："]

        # 添加关键指标
        metric_parts = []
        if metrics.roe is not None:
            metric_parts.append(f"ROE {metrics.roe:.1f}%")
        if metrics.revenue_yoy is not None:
            metric_parts.append(f"营收同比 {metrics.revenue_yoy:+.1f}%")
        if metrics.profit_yoy is not None:
            metric_parts.append(f"净利润同比 {metrics.profit_yoy:+.1f}%")

        if metric_parts:
            summary_parts.append("主要指标：" + "，".join(metric_parts) + "。")

        # 添加亮点
        if highlights:
            summary_parts.append("亮点：" + "；".join(highlights[:2]) + "。")

        # 添加风险
        if risks:
            summary_parts.append("风险提示：" + "；".join(risks[:2]) + "。")

        return " ".join(summary_parts)


# 注册工具
ToolRegistry.register(FundamentalTool())
