"""
结果解释器

将工具执行结果转换为自然语言响应
"""

import json
from typing import Any

from app.core.logging import get_logger
from app.agent.llm.base import Message
from app.agent.llm.factory import get_llm
from app.agent.intent.types import ParsedIntent, IntentCategory

logger = get_logger(__name__)

INTERPRETER_PROMPT = """你是一个投研助手，需要将数据分析结果转换为清晰、专业的自然语言回答。

## 原则

1. **准确性**：严格基于数据，不编造信息
2. **简洁性**：回答简洁明了，突出关键信息
3. **专业性**：使用恰当的金融术语
4. **透明性**：明确说明数据时间

## 格式

- 先给出核心答案
- 再补充关键细节
- 如有必要，给出数据来源时间

## 注意

- 不要给出投资建议或买卖指令
- 如果数据缺失，明确告知
- 使用中文回答"""


class ResponseInterpreter:
    """结果解释器"""

    def __init__(self):
        self.llm = get_llm()

    async def interpret(
        self,
        user_query: str,
        intent: ParsedIntent | None,
        tool_result: dict[str, Any] | None,
    ) -> str:
        """
        解释工具结果

        Args:
            user_query: 用户原始查询
            intent: 解析的意图
            tool_result: 工具执行结果

        Returns:
            自然语言响应
        """
        if not tool_result:
            return "抱歉，未能获取到相关数据。"

        # 对于简单查询，直接格式化
        if intent and intent.category == IntentCategory.FACT_QUERY:
            formatted = self._format_fact_query(tool_result)
            if formatted:
                return formatted

        # 复杂结果使用 LLM 解释
        return await self._llm_interpret(user_query, tool_result)

    def _format_fact_query(self, result: dict) -> str | None:
        """格式化数据速查结果"""
        if not result.get("success"):
            return None

        query_type = result.get("query_type")
        data = result.get("data", {})

        if query_type == "price":
            return self._format_price(data)
        elif query_type == "valuation":
            return self._format_valuation(data)
        elif query_type == "history":
            return self._format_history(data)
        elif query_type == "basic_info":
            return self._format_basic_info(data)

        return None

    def _format_price(self, data: dict) -> str:
        """格式化价格数据"""
        name = data.get("name", "")
        code = data.get("code", "")
        price = data.get("price")
        change = data.get("change")
        change_pct = data.get("change_pct")
        timestamp = data.get("timestamp", "")

        if price is None:
            return f"{name}({code}) 暂无价格数据"

        # 涨跌颜色
        if change_pct is not None:
            if change_pct > 0:
                trend = f"↑ +{change_pct:.2f}%"
            elif change_pct < 0:
                trend = f"↓ {change_pct:.2f}%"
            else:
                trend = "持平"
        else:
            trend = ""

        response = f"**{name}** ({code})\n\n"
        response += f"最新价：**{price:.2f}** 元 {trend}\n"

        if data.get("high") and data.get("low"):
            response += f"今日区间：{data['low']:.2f} - {data['high']:.2f}\n"

        if data.get("volume"):
            volume = data["volume"]
            if volume > 100000000:
                volume_str = f"{volume / 100000000:.2f} 亿股"
            elif volume > 10000:
                volume_str = f"{volume / 10000:.2f} 万股"
            else:
                volume_str = f"{volume} 股"
            response += f"成交量：{volume_str}\n"

        response += f"\n_数据时间：{timestamp}_"

        return response

    def _format_valuation(self, data: dict) -> str:
        """格式化估值数据"""
        name = data.get("name", "")
        code = data.get("code", "")

        response = f"**{name}** ({code}) 估值指标\n\n"

        if data.get("pe") is not None:
            response += f"- 市盈率(PE)：{data['pe']:.2f}\n"
        if data.get("pb") is not None:
            response += f"- 市净率(PB)：{data['pb']:.2f}\n"
        if data.get("market_cap") is not None:
            response += f"- 总市值：{data['market_cap']:.2f} 亿\n"
        if data.get("circulating_cap") is not None:
            response += f"- 流通市值：{data['circulating_cap']:.2f} 亿\n"

        if data.get("timestamp"):
            response += f"\n_数据时间：{data['timestamp']}_"

        return response

    def _format_history(self, data: dict) -> str:
        """格式化历史数据"""
        name = data.get("name", "")
        code = data.get("code", "")
        period = data.get("period", "")
        change_pct = data.get("change_pct")

        response = f"**{name}** ({code})\n\n"
        response += f"统计周期：{period}\n"

        if change_pct is not None:
            if change_pct > 0:
                response += f"区间涨幅：**+{change_pct:.2f}%** ↑\n"
            elif change_pct < 0:
                response += f"区间跌幅：**{change_pct:.2f}%** ↓\n"
            else:
                response += f"区间涨跌：持平\n"

        if data.get("high") and data.get("low"):
            response += f"区间最高：{data['high']:.2f}\n"
            response += f"区间最低：{data['low']:.2f}\n"

        response += f"数据点数：{data.get('data_points', 0)}\n"

        return response

    def _format_basic_info(self, data: dict) -> str:
        """格式化基本信息"""
        response = f"**{data.get('name', '')}** ({data.get('code', '')})\n\n"

        if data.get("market"):
            market_name = {"SH": "上海", "SZ": "深圳", "BJ": "北京"}.get(
                data["market"], data["market"]
            )
            response += f"- 上市市场：{market_name}\n"

        if data.get("asset_type"):
            type_name = {"stock": "股票", "etf": "ETF"}.get(
                data["asset_type"], data["asset_type"]
            )
            response += f"- 证券类型：{type_name}\n"

        if data.get("industry"):
            response += f"- 所属行业：{data['industry']}\n"

        if data.get("list_date"):
            response += f"- 上市日期：{data['list_date']}\n"

        return response

    async def _llm_interpret(self, query: str, result: dict) -> str:
        """使用 LLM 解释复杂结果"""
        result_str = json.dumps(result, ensure_ascii=False, indent=2)

        messages = [
            Message(role="system", content=INTERPRETER_PROMPT),
            Message(
                role="user",
                content=f"用户问题：{query}\n\n分析结果：\n```json\n{result_str}\n```\n\n请用自然语言回答用户问题：",
            ),
        ]

        response = await self.llm.chat(messages, temperature=0.3)
        return response.content
