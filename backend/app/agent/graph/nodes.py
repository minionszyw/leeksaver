"""
LangGraph 工作流节点

定义工作流中的各个处理节点
"""

from typing import Any

from app.core.logging import get_logger
from app.agent.graph.state import AgentState
from app.agent.intent.router import IntentRouter
from app.agent.intent.types import IntentCategory, FactQueryType, DeepAnalysisType
from app.agent.tools.base import ToolRegistry
from app.agent.interpreter.response import ResponseInterpreter
from app.agent.llm.factory import get_llm

logger = get_logger(__name__)


async def intent_router_node(state: AgentState) -> AgentState:
    """
    意图路由节点

    解析用户输入，确定意图
    """
    logger.info("执行意图路由", message=state.user_message[:50])

    router = IntentRouter()
    result = await router.classify(state.user_message, state.conversation_history)

    state.intent = result.intent
    state.needs_clarification = result.needs_clarification
    state.clarification_question = result.clarification_question
    state.current_node = "intent_router"

    # 确定下一节点
    if result.needs_clarification:
        state.next_node = "clarification"
    elif result.intent.category == IntentCategory.FACT_QUERY:
        state.next_node = "fact_query"
    elif result.intent.category == IntentCategory.DEEP_ANALYSIS:
        state.next_node = "deep_analysis"
    elif result.intent.category == IntentCategory.CHITCHAT:
        state.next_node = "chitchat"
    elif result.intent.category == IntentCategory.OUT_OF_SCOPE:
        state.next_node = "out_of_scope"
    else:
        state.next_node = "clarification"

    return state


async def clarification_node(state: AgentState) -> AgentState:
    """
    澄清节点

    生成澄清问题
    """
    logger.info("执行澄清节点")

    state.current_node = "clarification"
    state.response = state.clarification_question or "请问您想查询哪只股票？"
    state.is_complete = True

    return state


async def fact_query_node(state: AgentState) -> AgentState:
    """
    数据速查节点

    执行数据查询工具
    """
    logger.info("执行数据速查", intent=state.intent.sub_type if state.intent else None)

    state.current_node = "fact_query"

    if not state.intent or not state.intent.stock_codes:
        state.next_node = "clarification"
        state.clarification_question = "请提供您要查询的股票代码或名称"
        return state

    # 确定查询类型
    query_type = "price"
    if state.intent.sub_type == FactQueryType.VALUATION:
        query_type = "valuation"
    elif state.intent.sub_type == FactQueryType.HISTORY:
        query_type = "history"
    elif state.intent.sub_type == FactQueryType.BASIC_INFO:
        query_type = "basic_info"

    # 构建工具参数
    state.tool_name = "fact_query"
    state.tool_params = {
        "stock_code": state.intent.stock_codes[0],
        "query_type": query_type,
    }

    if state.intent.time_range:
        state.tool_params["start_date"] = state.intent.time_range.get("start")
        state.tool_params["end_date"] = state.intent.time_range.get("end")

    state.next_node = "tool_executor"
    return state


async def deep_analysis_node(state: AgentState) -> AgentState:
    """
    深度分析节点

    执行技术分析或基本面分析
    """
    logger.info("执行深度分析", intent=state.intent.sub_type if state.intent else None)

    state.current_node = "deep_analysis"

    if not state.intent or not state.intent.stock_codes:
        state.next_node = "clarification"
        state.clarification_question = "请提供您要分析的股票代码或名称"
        return state

    # 确定分析类型
    if state.intent.sub_type in (DeepAnalysisType.TECHNICAL, None):
        state.tool_name = "tech_analysis"
        state.tool_params = {
            "stock_code": state.intent.stock_codes[0],
            "period": "medium",
            "indicators": ["ma", "macd"],
        }
    elif state.intent.sub_type == DeepAnalysisType.FUNDAMENTAL:
        state.tool_name = "fundamental_analysis"
        state.tool_params = {
            "stock_code": state.intent.stock_codes[0],
        }
    else:
        # 综合分析：先做技术分析
        state.tool_name = "tech_analysis"
        state.tool_params = {
            "stock_code": state.intent.stock_codes[0],
            "period": "medium",
            "indicators": ["ma", "macd", "rsi"],
        }

    state.next_node = "tool_executor"
    return state


async def tool_executor_node(state: AgentState) -> AgentState:
    """
    工具执行节点

    执行指定的工具
    """
    logger.info("执行工具", tool=state.tool_name)

    state.current_node = "tool_executor"

    if not state.tool_name:
        state.error = "未指定工具"
        state.next_node = "error_handler"
        return state

    result = await ToolRegistry.execute(state.tool_name, **(state.tool_params or {}))

    if result.success:
        state.tool_result = (
            result.data.model_dump()
            if hasattr(result.data, "model_dump")
            else result.data
        )
        state.next_node = "interpreter"
    else:
        state.tool_error = result.error
        state.retry_count += 1

        if state.retry_count < state.max_retries:
            state.next_node = "tool_executor"  # 重试
        else:
            state.next_node = "error_handler"

    return state


async def interpreter_node(state: AgentState) -> AgentState:
    """
    结果解释节点

    将工具执行结果转换为自然语言响应
    """
    logger.info("执行结果解释")

    state.current_node = "interpreter"

    interpreter = ResponseInterpreter()
    response = await interpreter.interpret(
        user_query=state.user_message,
        intent=state.intent,
        tool_result=state.tool_result,
    )

    state.response = response
    state.response_data = state.tool_result
    state.is_complete = True

    return state


async def chitchat_node(state: AgentState) -> AgentState:
    """
    闲聊节点

    处理问候等社交性对话
    """
    logger.info("执行闲聊节点")

    state.current_node = "chitchat"

    # 简单的问候回复
    greetings = {
        "你好": "您好！我是 LeekSaver 智能投研助手，有什么可以帮您的吗？",
        "您好": "您好！我是 LeekSaver 智能投研助手，有什么可以帮您的吗？",
        "早上好": "早上好！今天想了解哪只股票？",
        "下午好": "下午好！有什么可以帮您查询的吗？",
        "晚上好": "晚上好！需要查看今日收盘情况吗？",
        "谢谢": "不客气！还有其他需要帮助的吗？",
        "thanks": "You're welcome! Anything else I can help with?",
    }

    query = state.user_message.lower()
    for key, response in greetings.items():
        if key in query:
            state.response = response
            break
    else:
        state.response = "您好！我是 LeekSaver 智能投研助手，专注于 A 股市场的查询与分析。您可以问我股票价格、估值、技术分析等问题。"

    state.is_complete = True
    return state


async def out_of_scope_node(state: AgentState) -> AgentState:
    """
    超出范围节点

    处理不支持的请求
    """
    logger.info("执行超范围节点")

    state.current_node = "out_of_scope"
    state.response = (
        "抱歉，这个问题超出了我的能力范围。我专注于 A 股市场的数据查询和分析，"
        "不提供投资建议或买卖指令。您可以问我：\n"
        "- 股票价格和行情\n"
        "- 估值指标（PE、PB、市值）\n"
        "- 技术分析\n"
        "- 历史涨跌幅"
    )
    state.is_complete = True

    return state


async def error_handler_node(state: AgentState) -> AgentState:
    """
    错误处理节点
    """
    logger.error("处理错误", error=state.error or state.tool_error)

    state.current_node = "error_handler"
    state.response = f"抱歉，处理您的请求时遇到了问题：{state.error or state.tool_error or '未知错误'}。请稍后重试。"
    state.is_complete = True

    return state
