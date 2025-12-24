"""
Schema 验证器单元测试
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.agent.schema.validator import SchemaValidator, extract_json_from_text


class TestExtractJsonFromText:
    """JSON 提取测试"""

    def test_extract_json_block(self):
        """测试从 markdown 代码块提取 JSON"""
        text = '''
        这是一些描述文字
        ```json
        {"key": "value", "number": 42}
        ```
        这是结束文字
        '''
        result = extract_json_from_text(text)
        assert result == {"key": "value", "number": 42}

    def test_extract_plain_json(self):
        """测试提取纯 JSON"""
        text = '{"name": "test", "items": [1, 2, 3]}'
        result = extract_json_from_text(text)
        assert result == {"name": "test", "items": [1, 2, 3]}

    def test_extract_json_with_prefix(self):
        """测试带前缀文字的 JSON"""
        text = 'The result is: {"status": "ok"}'
        result = extract_json_from_text(text)
        assert result == {"status": "ok"}

    def test_invalid_json(self):
        """测试无效 JSON"""
        text = "This is not JSON at all"
        result = extract_json_from_text(text)
        assert result is None

    def test_nested_json(self):
        """测试嵌套 JSON"""
        text = '{"outer": {"inner": {"deep": true}}}'
        result = extract_json_from_text(text)
        assert result == {"outer": {"inner": {"deep": True}}}

    def test_json_with_array(self):
        """测试数组 JSON"""
        text = '[{"id": 1}, {"id": 2}]'
        result = extract_json_from_text(text)
        assert result == [{"id": 1}, {"id": 2}]


class TestSchemaValidator:
    """SchemaValidator 测试"""

    def setup_method(self):
        self.mock_llm = AsyncMock()
        self.validator = SchemaValidator(llm=self.mock_llm)

    def test_validate_valid_data(self):
        """测试验证有效数据"""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name"],
        }
        data = {"name": "test", "age": 25}

        is_valid, errors = self.validator.validate(data, schema)
        assert is_valid is True
        assert errors == []

    def test_validate_missing_required(self):
        """测试缺少必填字段"""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
            "required": ["name"],
        }
        data = {"other": "value"}

        is_valid, errors = self.validator.validate(data, schema)
        assert is_valid is False
        assert len(errors) > 0

    def test_validate_wrong_type(self):
        """测试错误类型"""
        schema = {
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
            },
        }
        data = {"count": "not a number"}

        is_valid, errors = self.validator.validate(data, schema)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_validate_and_fix(self):
        """测试验证并修复"""
        # 模拟 LLM 返回修复后的数据
        self.mock_llm.chat.return_value = MagicMock(
            content='{"name": "fixed", "count": 42}'
        )

        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer"},
            },
            "required": ["name", "count"],
        }
        invalid_data = {"name": "test"}  # 缺少 count

        result = await self.validator.validate_and_fix(invalid_data, schema)
        assert result is not None
        assert "count" in result

    @pytest.mark.asyncio
    async def test_validate_and_fix_already_valid(self):
        """测试已有效数据不调用 LLM"""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
        }
        valid_data = {"name": "test"}

        result = await self.validator.validate_and_fix(valid_data, schema)
        assert result == valid_data
        self.mock_llm.chat.assert_not_called()
