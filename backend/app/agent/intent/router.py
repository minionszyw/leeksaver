"""
意图路由器

将用户输入解析为意图，并路由到相应的处理流程
"""

import json
import re
from typing import Any

from app.core.logging import get_logger
from app.agent.llm.base import LLMBase, Message
from app.agent.llm.factory import get_llm
from app.agent.intent.types import (
    IntentCategory,
    FactQueryType,
    DeepAnalysisType,
    ParsedIntent,
    IntentClassificationResult,
)
from app.agent.schema.validator import extract_json_from_text

logger = get_logger(__name__)

# 股票代码正则
STOCK_CODE_PATTERN = re.compile(r"\b([036]\d{5})\b")

# 常见股票名称映射 (简化版，实际应从数据库加载)
COMMON_STOCK_NAMES = {
    "茅台": "600519",
    "贵州茅台": "600519",
    "平安": "601318",
    "中国平安": "601318",
    "招商银行": "600036",
    "招行": "600036",
    "宁德时代": "300750",
    "宁德": "300750",
    "比亚迪": "002594",
}

INTENT_ROUTER_PROMPT = """你是一个投研助手的意图分类器。分析用户的问题，提取意图和关键实体。

## 意图类型

1. **fact_query** (数据速查)
   - price: 查询价格、涨跌
   - valuation: 查询估值 (PE/PB/市值)
   - history: 查询历史涨跌幅
   - basic_info: 查询基本信息

2. **deep_analysis** (深度分析)
   - technical: 技术分析
   - fundamental: 基本面分析
   - news: 新闻背景分析
   - comprehensive: 综合分析

3. **clarification** (需要澄清)
   - 问题不清晰，需要更多信息

4. **out_of_scope** (超出范围)
   - 非股票相关问题
   - 要求给出投资建议或买卖指令

5. **chitchat** (闲聊)
   - 问候、感谢等社交性对话

## 输出格式

请输出 JSON 格式：
```json
{
  "category": "意图大类",
  "sub_type": "意图子类型（如适用）",
  "confidence": 0.0-1.0,
  "stock_codes": ["识别的股票代码"],
  "stock_names": ["识别的股票名称"],
  "metrics": ["请求的指标"],
  "time_range": {"start": "开始日期", "end": "结束日期"},
  "needs_clarification": false,
  "clarification_question": null
}
```

## 注意事项

- 如果用户提到股票名称但没有代码，在 stock_names 中记录
- 如果问题涉及多只股票，都要列出
- 如果时间范围不明确，time_range 可以为 null
- 对于"分析"类请求，判断是技术分析还是基本面分析
- 不要编造或猜测数据"""


class IntentRouter:
    """意图路由器"""

    def __init__(self, llm: LLMBase | None = None):
        self.llm = llm or get_llm()

    async def classify(
        self, query: str, history: list[dict[str, str]] | None = None
    ) -> IntentClassificationResult:
        """
        分类用户意图

        Args:
            query: 用户输入
            history: 会话历史（可选）

        Returns:
            意图分类结果
        """
        logger.info("开始意图分类", query=query[:50])

        # 快速规则匹配
        quick_result = self._quick_match(query)
        if quick_result:
            return quick_result

        # 构建消息列表
        messages = [Message(role="system", content=INTENT_ROUTER_PROMPT)]

        # 添加会话历史（最近几轮）
        if history:
            context_parts = []
            for msg in history[-6:]:  # 最近 3 轮对话
                role = "用户" if msg["role"] == "user" else "助手"
                context_parts.append(f"{role}：{msg['content'][:100]}")

            if context_parts:
                context_text = "\n".join(context_parts)
                messages.append(
                    Message(
                        role="user",
                        content=f"以下是之前的对话历史（供上下文参考）：\n{context_text}\n\n现在用户问：{query}",
                    )
                )
            else:
                messages.append(Message(role="user", content=f"用户问题：{query}"))
        else:
            messages.append(Message(role="user", content=f"用户问题：{query}"))

        response = await self.llm.chat(messages, temperature=0.1)

        # 解析响应
        parsed = await self._parse_response(response.content, query)

        logger.info(
            "意图分类完成",
            category=parsed.intent.category,
            sub_type=parsed.intent.sub_type,
            stocks=parsed.intent.stock_codes or parsed.intent.stock_names,
        )

        return parsed

    def _quick_match(self, query: str) -> IntentClassificationResult | None:
        """
        快速规则匹配

        对于简单明确的查询，直接返回结果，避免调用 LLM
        """
        query_lower = query.lower()

        # 提取股票代码
        codes = STOCK_CODE_PATTERN.findall(query)

        # 提取股票名称
        names = []
        for name, code in COMMON_STOCK_NAMES.items():
            if name in query:
                names.append(name)
                if code not in codes:
                    codes.append(code)

        # 问候语
        greetings = ["你好", "您好", "hi", "hello", "早上好", "下午好", "晚上好"]
        if any(g in query_lower for g in greetings) and len(query) < 20:
            return IntentClassificationResult(
                intent=ParsedIntent(
                    category=IntentCategory.CHITCHAT,
                    original_query=query,
                    confidence=0.95,
                )
            )

        # 价格查询
        price_keywords = ["价格", "股价", "多少钱", "现价", "最新价", "涨了", "跌了"]
        if any(k in query for k in price_keywords) and (codes or names):
            return IntentClassificationResult(
                intent=ParsedIntent(
                    category=IntentCategory.FACT_QUERY,
                    sub_type=FactQueryType.PRICE,
                    stock_codes=codes,
                    stock_names=names,
                    original_query=query,
                    confidence=0.9,
                )
            )

        # 市盈率/估值查询
        valuation_keywords = ["市盈率", "pe", "pb", "市值", "估值", "市净率"]
        if any(k in query_lower for k in valuation_keywords) and (codes or names):
            return IntentClassificationResult(
                intent=ParsedIntent(
                    category=IntentCategory.FACT_QUERY,
                    sub_type=FactQueryType.VALUATION,
                    stock_codes=codes,
                    stock_names=names,
                    original_query=query,
                    confidence=0.9,
                )
            )

        return None

    async def _parse_response(self, content: str, query: str) -> IntentClassificationResult:
        """解析 LLM 响应"""
        data = extract_json_from_text(content)

        if not data:
            logger.warning("无法解析意图分类响应", content=content[:100])
            return IntentClassificationResult(
                intent=ParsedIntent(
                    category=IntentCategory.CLARIFICATION,
                    original_query=query,
                    confidence=0.5,
                ),
                needs_clarification=True,
                clarification_question="抱歉，我没有完全理解您的问题，能否请您再说明一下？",
            )

        # 解析意图类别
        category_str = data.get("category", "clarification")
        try:
            category = IntentCategory(category_str)
        except ValueError:
            category = IntentCategory.CLARIFICATION

        intent = ParsedIntent(
            category=category,
            sub_type=data.get("sub_type"),
            confidence=data.get("confidence", 0.8),
            stock_codes=data.get("stock_codes", []),
            stock_names=data.get("stock_names", []),
            time_range=data.get("time_range"),
            metrics=data.get("metrics", []),
            original_query=query,
        )

        # 补充股票代码映射
        for name in intent.stock_names:
            if name in COMMON_STOCK_NAMES:
                code = COMMON_STOCK_NAMES[name]
                if code not in intent.stock_codes:
                    intent.stock_codes.append(code)

        # 如果有股票名称但没有代码，尝试从数据库搜索
        if intent.stock_names and not intent.stock_codes:
            await self._resolve_stock_names(intent)

        needs_clarification = data.get("needs_clarification", False)

        # 如果需要股票但没有识别到，设置为需要澄清
        if intent.requires_stock() and not intent.has_stock():
            needs_clarification = True

        return IntentClassificationResult(
            intent=intent,
            needs_clarification=needs_clarification,
            clarification_question=data.get("clarification_question"),
        )

    async def _resolve_stock_names(self, intent: ParsedIntent) -> None:
        """
        从数据库解析股票名称为代码

        Args:
            intent: 意图对象，会直接修改其 stock_codes
        """
        from app.core.database import get_db_session
        from app.repositories.stock_repository import StockRepository

        try:
            async with get_db_session() as session:
                repo = StockRepository(session)
                for name in intent.stock_names:
                    # 搜索股票
                    stocks = await repo.search(name, limit=1)
                    if stocks:
                        code = stocks[0].code
                        if code not in intent.stock_codes:
                            intent.stock_codes.append(code)
                            logger.info("解析股票名称", name=name, code=code)
        except Exception as e:
            logger.warning("解析股票名称失败", error=str(e))

    async def resolve_stock_names(
        self, names: list[str], search_func
    ) -> dict[str, str]:
        """
        解析股票名称为代码

        Args:
            names: 股票名称列表
            search_func: 股票搜索函数

        Returns:
            名称到代码的映射
        """
        result = {}

        for name in names:
            # 先查本地映射
            if name in COMMON_STOCK_NAMES:
                result[name] = COMMON_STOCK_NAMES[name]
                continue

            # 调用搜索
            stocks = await search_func(name, limit=1)
            if stocks:
                result[name] = stocks[0].code

        return result
