"""
工具基类

定义工具的通用接口和注册机制
"""

from abc import ABC, abstractmethod
from typing import Any, Type

from pydantic import BaseModel

from app.core.logging import get_logger

logger = get_logger(__name__)


class ToolResult(BaseModel):
    """工具执行结果"""

    success: bool = True
    data: Any = None
    error: str | None = None
    message: str | None = None

    def to_context(self) -> str:
        """转换为上下文字符串（用于 LLM）"""
        if not self.success:
            return f"[错误] {self.error or '执行失败'}"

        if isinstance(self.data, BaseModel):
            return self.data.model_dump_json(indent=2)
        elif isinstance(self.data, dict):
            import json
            return json.dumps(self.data, ensure_ascii=False, indent=2)
        else:
            return str(self.data)


class ToolBase(ABC):
    """工具基类"""

    # 子类需要定义
    name: str = ""
    description: str = ""
    input_schema: Type[BaseModel] | None = None
    output_schema: Type[BaseModel] | None = None

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """
        执行工具

        Args:
            **kwargs: 工具参数

        Returns:
            工具执行结果
        """
        pass

    def validate_input(self, **kwargs) -> BaseModel | None:
        """验证输入参数"""
        if self.input_schema:
            return self.input_schema.model_validate(kwargs)
        return None

    def get_definition(self) -> dict:
        """获取工具定义（OpenAI 格式）"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": (
                    self.input_schema.model_json_schema()
                    if self.input_schema
                    else {"type": "object", "properties": {}}
                ),
            },
        }


class ToolRegistry:
    """工具注册表"""

    _tools: dict[str, ToolBase] = {}

    @classmethod
    def register(cls, tool: ToolBase):
        """注册工具"""
        cls._tools[tool.name] = tool
        logger.info("注册工具", name=tool.name)

    @classmethod
    def get(cls, name: str) -> ToolBase | None:
        """获取工具"""
        return cls._tools.get(name)

    @classmethod
    def get_all(cls) -> dict[str, ToolBase]:
        """获取所有工具"""
        return cls._tools.copy()

    @classmethod
    def get_definitions(cls) -> list[dict]:
        """获取所有工具定义"""
        return [tool.get_definition() for tool in cls._tools.values()]

    @classmethod
    async def execute(cls, name: str, **kwargs) -> ToolResult:
        """执行工具"""
        tool = cls.get(name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"未找到工具: {name}",
            )

        try:
            logger.info("执行工具", name=name, params=kwargs)
            result = await tool.execute(**kwargs)
            logger.info("工具执行完成", name=name, success=result.success)
            return result
        except Exception as e:
            logger.error("工具执行失败", name=name, error=str(e))
            return ToolResult(
                success=False,
                error=str(e),
            )
