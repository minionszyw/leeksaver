"""
Schema 校验器与自愈机制

实现契约优先原则：所有 LLM 输出必须通过 Schema 校验
"""

import json
from typing import Any, Type, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.logging import get_logger
from app.agent.llm.base import LLMBase, Message

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class SchemaValidationError(Exception):
    """Schema 校验错误"""

    def __init__(self, message: str, errors: list[dict] | None = None):
        super().__init__(message)
        self.errors = errors or []


class SchemaValidator:
    """
    Schema 校验器

    支持自愈重试机制
    """

    def __init__(self, llm: LLMBase, max_retries: int = 2):
        self.llm = llm
        self.max_retries = max_retries

    def validate(self, data: dict | str, schema: Type[T]) -> T:
        """
        验证数据是否符合 Schema

        Args:
            data: 待验证的数据（字典或 JSON 字符串）
            schema: Pydantic 模型类

        Returns:
            验证后的模型实例

        Raises:
            SchemaValidationError: 校验失败
        """
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as e:
                raise SchemaValidationError(f"JSON 解析失败: {e}")

        try:
            return schema.model_validate(data)
        except ValidationError as e:
            errors = e.errors()
            raise SchemaValidationError(
                f"Schema 校验失败: {len(errors)} 个错误",
                errors=[
                    {"loc": err["loc"], "msg": err["msg"], "type": err["type"]}
                    for err in errors
                ],
            )

    async def validate_with_retry(
        self,
        data: dict | str,
        schema: Type[T],
        context: str = "",
    ) -> T:
        """
        验证数据，失败时触发 LLM 自愈重试

        Args:
            data: 待验证的数据
            schema: Pydantic 模型类
            context: 上下文信息（用于重试时提供给 LLM）

        Returns:
            验证后的模型实例

        Raises:
            SchemaValidationError: 重试后仍然失败
        """
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                return self.validate(data, schema)
            except SchemaValidationError as e:
                last_error = e
                logger.warning(
                    "Schema 校验失败",
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                    errors=e.errors,
                )

                if attempt < self.max_retries:
                    # 尝试让 LLM 修正
                    data = await self._attempt_fix(data, schema, e, context)
                else:
                    break

        # 所有重试都失败
        raise last_error

    async def _attempt_fix(
        self,
        data: dict | str,
        schema: Type[T],
        error: SchemaValidationError,
        context: str,
    ) -> dict:
        """
        尝试让 LLM 修正数据

        Args:
            data: 原始数据
            schema: 目标 Schema
            error: 校验错误
            context: 上下文

        Returns:
            修正后的数据
        """
        # 构建修正提示
        prompt = self._build_fix_prompt(data, schema, error, context)

        logger.info("触发自愈机制", schema=schema.__name__)

        messages = [
            Message(role="system", content="你是一个数据修正助手，请根据错误信息修正 JSON 数据。只输出修正后的 JSON，不要有其他内容。"),
            Message(role="user", content=prompt),
        ]

        response = await self.llm.chat(messages, temperature=0.1)

        # 尝试解析修正后的数据
        try:
            fixed_data = json.loads(response.content)
            return fixed_data
        except json.JSONDecodeError:
            # 提取可能的 JSON 块
            content = response.content
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                if end > start:
                    content = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                if end > start:
                    content = content[start:end].strip()

            return json.loads(content)

    def _build_fix_prompt(
        self,
        data: dict | str,
        schema: Type[T],
        error: SchemaValidationError,
        context: str,
    ) -> str:
        """构建修正提示"""
        data_str = json.dumps(data, ensure_ascii=False, indent=2) if isinstance(data, dict) else data
        schema_str = json.dumps(schema.model_json_schema(), ensure_ascii=False, indent=2)
        errors_str = json.dumps(error.errors, ensure_ascii=False, indent=2)

        return f"""请修正以下 JSON 数据，使其符合目标 Schema。

## 原始数据
```json
{data_str}
```

## 目标 Schema
```json
{schema_str}
```

## 校验错误
```json
{errors_str}
```

{f"## 上下文信息{chr(10)}{context}" if context else ""}

请输出修正后的 JSON（只输出 JSON，不要有其他内容）："""


def extract_json_from_text(text: str) -> dict | None:
    """
    从文本中提取 JSON

    尝试多种方式提取 JSON 对象
    """
    # 直接尝试解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试从代码块提取
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end > start:
            try:
                return json.loads(text[start:end].strip())
            except json.JSONDecodeError:
                pass

    if "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        if end > start:
            try:
                return json.loads(text[start:end].strip())
            except json.JSONDecodeError:
                pass

    # 尝试找到 JSON 对象边界
    start = text.find("{")
    if start >= 0:
        depth = 0
        for i, c in enumerate(text[start:], start):
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break

    return None
