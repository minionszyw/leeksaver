"""
Agent 意图分类体系

定义系统支持的意图类型和相关数据结构
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class IntentCategory(str, Enum):
    """意图大类"""

    FACT_QUERY = "fact_query"  # 数据速查
    DEEP_ANALYSIS = "deep_analysis"  # 深度分析
    CLARIFICATION = "clarification"  # 需要澄清
    OUT_OF_SCOPE = "out_of_scope"  # 超出范围
    CHITCHAT = "chitchat"  # 闲聊


class FactQueryType(str, Enum):
    """数据速查子类型"""

    PRICE = "price"  # 查询价格
    VALUATION = "valuation"  # 查询估值 (PE/PB/市值)
    HISTORY = "history"  # 历史涨跌幅
    BASIC_INFO = "basic_info"  # 基本信息 (行业/上市日期等)
    COMPARE = "compare"  # 多股比较


class DeepAnalysisType(str, Enum):
    """深度分析子类型"""

    TECHNICAL = "technical"  # 技术分析
    FUNDAMENTAL = "fundamental"  # 基本面分析
    NEWS = "news"  # 新闻背景分析
    COMPREHENSIVE = "comprehensive"  # 综合分析


class ParsedIntent(BaseModel):
    """解析后的意图"""

    category: IntentCategory = Field(..., description="意图大类")
    sub_type: str | None = Field(None, description="意图子类型")
    confidence: float = Field(default=1.0, ge=0, le=1, description="置信度")

    # 提取的实体
    stock_codes: list[str] = Field(default_factory=list, description="识别的股票代码")
    stock_names: list[str] = Field(default_factory=list, description="识别的股票名称")
    time_range: dict[str, str] | None = Field(None, description="时间范围")
    metrics: list[str] = Field(default_factory=list, description="请求的指标")

    # 原始查询
    original_query: str = Field(..., description="原始用户查询")
    rewritten_query: str | None = Field(None, description="改写后的查询")

    # 额外参数
    params: dict[str, Any] = Field(default_factory=dict, description="额外参数")

    def is_actionable(self) -> bool:
        """是否可执行（非澄清/闲聊/超范围）"""
        return self.category in (IntentCategory.FACT_QUERY, IntentCategory.DEEP_ANALYSIS)

    def requires_stock(self) -> bool:
        """是否需要股票代码"""
        return self.is_actionable()

    def has_stock(self) -> bool:
        """是否已识别股票"""
        return bool(self.stock_codes or self.stock_names)


class IntentClassificationResult(BaseModel):
    """意图分类结果"""

    intent: ParsedIntent
    needs_clarification: bool = Field(default=False, description="是否需要澄清")
    clarification_question: str | None = Field(None, description="澄清问题")
    suggested_stocks: list[dict] | None = Field(None, description="建议的股票列表")
