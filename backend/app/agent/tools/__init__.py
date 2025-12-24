"""
工具模块

导入所有工具以触发自动注册
"""

from app.agent.tools.base import ToolBase, ToolResult, ToolRegistry

# 导入工具以触发注册
from app.agent.tools.fact_query import FactQueryTool
from app.agent.tools.tech_analysis import TechAnalysisTool
from app.agent.tools.fundamental import FundamentalTool

__all__ = [
    "ToolBase",
    "ToolResult",
    "ToolRegistry",
    "FactQueryTool",
    "TechAnalysisTool",
    "FundamentalTool",
]
