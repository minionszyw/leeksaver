"""
工具调用 JSON Schema 定义

定义所有工具的输入输出 Schema
"""

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field


# ==================== 数据速查工具 ====================


class FactQueryInput(BaseModel):
    """数据速查工具输入"""

    stock_code: str = Field(..., description="股票代码，如 '000001' 或 '600519'")
    query_type: Literal["price", "valuation", "history", "basic_info"] = Field(
        ..., description="查询类型"
    )
    start_date: date | None = Field(None, description="历史查询起始日期")
    end_date: date | None = Field(None, description="历史查询结束日期")
    metrics: list[str] | None = Field(None, description="请求的具体指标")


class PriceData(BaseModel):
    """价格数据"""

    code: str
    name: str
    price: float | None = Field(None, description="最新价")
    change: float | None = Field(None, description="涨跌额")
    change_pct: float | None = Field(None, description="涨跌幅 (%)")
    open: float | None = None
    high: float | None = None
    low: float | None = None
    volume: int | None = None
    amount: float | None = None
    timestamp: str = Field(..., description="数据时间戳")


class ValuationData(BaseModel):
    """估值数据"""

    code: str
    name: str
    pe: float | None = Field(None, description="市盈率")
    pb: float | None = Field(None, description="市净率")
    ps: float | None = Field(None, description="市销率")
    market_cap: float | None = Field(None, description="总市值 (亿)")
    circulating_cap: float | None = Field(None, description="流通市值 (亿)")
    timestamp: str


class HistoryData(BaseModel):
    """历史数据"""

    code: str
    name: str
    period: str = Field(..., description="时间周期")
    start_date: str
    end_date: str
    change_pct: float | None = Field(None, description="区间涨跌幅 (%)")
    high: float | None = Field(None, description="区间最高价")
    low: float | None = Field(None, description="区间最低价")
    data_points: int = Field(..., description="数据点数量")


class FactQueryOutput(BaseModel):
    """数据速查工具输出"""

    success: bool = True
    query_type: str
    data: PriceData | ValuationData | HistoryData | dict
    message: str | None = None


# ==================== 技术分析工具 ====================


class TechAnalysisInput(BaseModel):
    """技术分析工具输入"""

    stock_code: str = Field(..., description="股票代码")
    period: Literal["short", "medium", "long"] = Field(
        default="medium", description="分析周期: short(5日), medium(20日), long(60日)"
    )
    indicators: list[str] | None = Field(
        None, description="分析指标: ma, macd, kdj, rsi, boll"
    )


class TrendAnalysis(BaseModel):
    """趋势分析"""

    direction: Literal["up", "down", "sideways"] = Field(..., description="趋势方向")
    strength: Literal["strong", "moderate", "weak"] = Field(..., description="趋势强度")
    support: float | None = Field(None, description="支撑位")
    resistance: float | None = Field(None, description="压力位")


class IndicatorResult(BaseModel):
    """指标结果"""

    name: str
    value: float | dict
    signal: Literal["buy", "sell", "neutral"] | None = None
    description: str | None = None


class TechAnalysisOutput(BaseModel):
    """技术分析工具输出"""

    success: bool = True
    code: str
    name: str
    period: str
    current_price: float
    trend: TrendAnalysis
    indicators: list[IndicatorResult]
    summary: str = Field(..., description="技术分析总结")


# ==================== 基本面工具 ====================


class FundamentalInput(BaseModel):
    """基本面工具输入"""

    stock_code: str = Field(..., description="股票代码")
    aspects: list[str] | None = Field(
        None, description="分析方面: finance, growth, profit, debt"
    )


class FinancialMetrics(BaseModel):
    """财务指标"""

    revenue: float | None = Field(None, description="营业收入 (亿)")
    revenue_yoy: float | None = Field(None, description="营收同比 (%)")
    net_profit: float | None = Field(None, description="净利润 (亿)")
    profit_yoy: float | None = Field(None, description="净利润同比 (%)")
    roe: float | None = Field(None, description="ROE (%)")
    gross_margin: float | None = Field(None, description="毛利率 (%)")
    debt_ratio: float | None = Field(None, description="资产负债率 (%)")


class FundamentalOutput(BaseModel):
    """基本面工具输出"""

    success: bool = True
    code: str
    name: str
    industry: str | None
    metrics: FinancialMetrics
    highlights: list[str] = Field(default_factory=list, description="财务亮点")
    risks: list[str] = Field(default_factory=list, description="风险提示")
    summary: str


# ==================== 通用工具定义 ====================


def get_tool_definitions() -> list[dict]:
    """
    获取所有工具的 OpenAI 格式定义

    用于 LLM 的工具调用
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "fact_query",
                "description": "查询股票的基本数据，包括价格、估值、历史涨跌等",
                "parameters": FactQueryInput.model_json_schema(),
            },
        },
        {
            "type": "function",
            "function": {
                "name": "tech_analysis",
                "description": "对股票进行技术分析，包括趋势判断和技术指标",
                "parameters": TechAnalysisInput.model_json_schema(),
            },
        },
        {
            "type": "function",
            "function": {
                "name": "fundamental_analysis",
                "description": "分析股票的基本面，包括财务指标和经营状况",
                "parameters": FundamentalInput.model_json_schema(),
            },
        },
    ]
