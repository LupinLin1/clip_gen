"""
测试工具注册管理模块
"""

import asyncio
import inspect
from typing import List, Dict, Optional
import pytest
from unittest.mock import MagicMock, AsyncMock

from src.gemini_kling_mcp.tools.registry import (
    ToolInfo, ToolRegistry, default_registry,
    tool, register_tool, get_registry
)
from src.gemini_kling_mcp.exceptions import ToolExecutionError, ValidationError

class TestToolInfo:
    """测试ToolInfo数据类"""
    
    def test_basic_creation(self):
        """测试基础创建"""
        def dummy_func():
            pass
        
        tool_info = ToolInfo(
            name="test_tool",
            description="Test tool",
            parameters={"type": "object"},
            function=dummy_func
        )
        
        assert tool_info.name == "test_tool"
        assert tool_info.description == "Test tool"
        assert tool_info.parameters == {"type": "object"}
        assert tool_info.function is dummy_func
        assert tool_info.is_async is False
    
    def test_to_dict(self):
        """测试转换为字典格式"""
        def dummy_func():
            pass
        
        parameters = {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "count": {"type": "integer"}
            },
            "required": ["text"],
            "additionalProperties": False
        }
        
        tool_info = ToolInfo(
            name="test_tool",
            description="Test tool for testing",
            parameters=parameters,
            function=dummy_func
        )
        
        result = tool_info.to_dict()
        
        expected = {
            "name": "test_tool",
            "description": "Test tool for testing",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "count": {"type": "integer"}
                },
                "required": ["text"],
                "additionalProperties": False
            }
        }
        
        assert result == expected

class TestToolRegistry:
    """测试ToolRegistry类"""
    
    def test_initialization(self):
        """测试初始化"""
        registry = ToolRegistry()
        assert len(registry._tools) == 0
        assert len(registry._middleware) == 0
    
    def test_register_sync_tool(self):
        """测试注册同步工具"""
        registry = ToolRegistry()
        
        def test_tool(text: str) -> str:
            return f"Hello {text}"
        
        parameters = {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"]
        }
        
        registry.register_tool(test_tool, "greet", "Greet someone", parameters)
        
        assert "greet" in registry._tools
        tool_info = registry._tools["greet"]
        assert tool_info.name == "greet"
        assert tool_info.description == "Greet someone"
        assert tool_info.function is test_tool
        assert tool_info.is_async is False
    
    def test_register_async_tool(self):
        """测试注册异步工具"""
        registry = ToolRegistry()
        
        async def async_tool(text: str) -> str:
            await asyncio.sleep(0.1)
            return f"Async hello {text}"
        
        parameters = {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"]
        }
        
        registry.register_tool(async_tool, "async_greet", "Async greet", parameters)
        
        tool_info = registry._tools["async_greet"]
        assert tool_info.is_async is True
    
    def test_register_duplicate_tool_raises_error(self):
        """测试注册重复工具抛出错误"""
        registry = ToolRegistry()
        
        def tool1():
            pass
        
        def tool2():
            pass
        
        parameters = {"type": "object"}
        
        registry.register_tool(tool1, "duplicate", "First tool", parameters)
        
        with pytest.raises(ValueError, match="工具名称已存在: duplicate"):
            registry.register_tool(tool2, "duplicate", "Second tool", parameters)
    
    def test_tool_decorator_basic(self):
        """测试工具装饰器基础使用"""
        registry = ToolRegistry()
        
        @registry.tool("decorated_tool", "A decorated tool")
        def decorated_func(text: str) -> str:
            return f"Decorated: {text}"
        
        assert "decorated_tool" in registry._tools
        tool_info = registry._tools["decorated_tool"]
        assert tool_info.name == "decorated_tool"
        assert tool_info.description == "A decorated tool"
    
    def test_extract_parameters_from_signature(self):
        """测试从函数签名提取参数"""
        registry = ToolRegistry()
        
        def test_func(
            text: str,
            count: int = 5,
            enabled: bool = True,
            items: List[str] = None,
            config: Dict = None,
            optional_text: Optional[str] = None
        ):
            pass
        
        params = registry._extract_parameters_from_signature(test_func)
        
        assert params["type"] == "object"
        assert "text" in params["properties"]
        assert "count" in params["properties"]
        assert "enabled" in params["properties"]
        assert "items" in params["properties"]
        assert "config" in params["properties"]
        assert "optional_text" in params["properties"]
        
        # 验证类型推断
        assert params["properties"]["text"]["type"] == "string"
        assert params["properties"]["count"]["type"] == "integer"
        assert params["properties"]["enabled"]["type"] == "boolean"
        assert params["properties"]["items"]["type"] == "array"
        assert params["properties"]["config"]["type"] == "object"
        
        # 验证必需参数
        assert "text" in params["required"]
        assert "count" not in params["required"]  # 有默认值
        assert "optional_text" not in params["required"]  # Optional类型
        
        # 验证默认值
        assert params["properties"]["count"]["default"] == 5
        assert params["properties"]["enabled"]["default"] is True
    
    @pytest.mark.asyncio
    async def test_call_sync_tool(self):
        """测试调用同步工具"""
        registry = ToolRegistry()
        
        def test_tool(text: str, count: int = 1) -> str:
            return text * count
        
        parameters = {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "count": {"type": "integer", "default": 1}
            },
            "required": ["text"]
        }
        
        registry.register_tool(test_tool, "repeat", "Repeat text", parameters)
        
        result = await registry.call_tool("repeat", {"text": "hi", "count": 3})
        assert result == "hihihi"
    
    @pytest.mark.asyncio
    async def test_call_async_tool(self):
        """测试调用异步工具"""
        registry = ToolRegistry()
        
        async def async_tool(text: str) -> str:
            await asyncio.sleep(0.01)
            return f"async_{text}"
        
        parameters = {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"]
        }
        
        registry.register_tool(async_tool, "async_repeat", "Async repeat", parameters)
        
        result = await registry.call_tool("async_repeat", {"text": "test"})
        assert result == "async_test"
    
    @pytest.mark.asyncio
    async def test_call_nonexistent_tool(self):
        """测试调用不存在的工具"""
        registry = ToolRegistry()
        
        with pytest.raises(ToolExecutionError, match="工具不存在: nonexistent"):
            await registry.call_tool("nonexistent", {})
    
    @pytest.mark.asyncio
    async def test_parameter_validation_missing_required(self):
        """测试参数验证 - 缺少必需参数"""
        registry = ToolRegistry()
        
        def test_tool(text: str, count: int) -> str:
            return text * count
        
        parameters = {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "count": {"type": "integer"}
            },
            "required": ["text", "count"]
        }
        
        registry.register_tool(test_tool, "test", "Test tool", parameters)
        
        with pytest.raises(ValidationError, match="缺少必需参数: count"):
            await registry.call_tool("test", {"text": "hello"})
    
    @pytest.mark.asyncio
    async def test_parameter_validation_wrong_type(self):
        """测试参数验证 - 错误类型"""
        registry = ToolRegistry()
        
        def test_tool(count: int) -> str:
            return str(count)
        
        parameters = {
            "type": "object",
            "properties": {"count": {"type": "integer"}},
            "required": ["count"]
        }
        
        registry.register_tool(test_tool, "test", "Test tool", parameters)
        
        with pytest.raises(ValidationError, match="参数类型错误: count 应为 integer"):
            await registry.call_tool("test", {"count": "not_a_number"})
    
    def test_validate_parameter_type(self):
        """测试参数类型验证"""
        registry = ToolRegistry()
        
        # 测试各种类型验证
        assert registry._validate_parameter_type("hello", "string") is True
        assert registry._validate_parameter_type(123, "integer") is True
        assert registry._validate_parameter_type(123.5, "number") is True
        assert registry._validate_parameter_type(123, "number") is True  # int也是number
        assert registry._validate_parameter_type(True, "boolean") is True
        assert registry._validate_parameter_type([1, 2, 3], "array") is True
        assert registry._validate_parameter_type({"key": "value"}, "object") is True
        
        # 测试错误类型
        assert registry._validate_parameter_type(123, "string") is False
        assert registry._validate_parameter_type("hello", "integer") is False
        assert registry._validate_parameter_type(True, "string") is False
        
        # 测试未知类型（应该总是返回True）
        assert registry._validate_parameter_type("anything", "unknown") is True
    
    @pytest.mark.asyncio
    async def test_middleware_execution(self):
        """测试中间件执行"""
        registry = ToolRegistry()
        
        # 创建中间件
        executed_middleware = []
        
        def middleware1(tool_name: str, arguments: dict) -> dict:
            executed_middleware.append("middleware1")
            arguments["middleware1"] = True
            return arguments
        
        async def middleware2(tool_name: str, arguments: dict) -> dict:
            executed_middleware.append("middleware2")
            arguments["middleware2"] = True
            return arguments
        
        # 添加中间件
        registry.add_middleware(middleware1)
        registry.add_middleware(middleware2)
        
        # 注册工具
        def test_tool(**kwargs) -> dict:
            return kwargs
        
        parameters = {"type": "object", "properties": {}, "required": []}
        registry.register_tool(test_tool, "test", "Test tool", parameters)
        
        # 调用工具
        result = await registry.call_tool("test", {"original": True})
        
        # 验证中间件执行和参数修改
        assert "middleware1" in executed_middleware
        assert "middleware2" in executed_middleware
        assert result["middleware1"] is True
        assert result["middleware2"] is True
        assert result["original"] is True
    
    @pytest.mark.asyncio
    async def test_tool_execution_exception(self):
        """测试工具执行异常处理"""
        registry = ToolRegistry()
        
        def failing_tool(text: str) -> str:
            raise RuntimeError("Tool failed")
        
        parameters = {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"]
        }
        
        registry.register_tool(failing_tool, "fail", "Failing tool", parameters)
        
        with pytest.raises(ToolExecutionError, match="工具执行失败"):
            await registry.call_tool("fail", {"text": "test"})
    
    def test_list_tools(self):
        """测试获取工具列表"""
        registry = ToolRegistry()
        
        def tool1():
            pass
        
        def tool2():
            pass
        
        params = {"type": "object"}
        registry.register_tool(tool1, "tool1", "First tool", params)
        registry.register_tool(tool2, "tool2", "Second tool", params)
        
        tools = registry.list_tools()
        assert len(tools) == 2
        assert all(isinstance(tool, ToolInfo) for tool in tools)
        
        tool_names = [tool.name for tool in tools]
        assert "tool1" in tool_names
        assert "tool2" in tool_names
    
    def test_get_tool(self):
        """测试获取工具信息"""
        registry = ToolRegistry()
        
        def test_tool():
            pass
        
        params = {"type": "object"}
        registry.register_tool(test_tool, "test", "Test tool", params)
        
        # 获取存在的工具
        tool_info = registry.get_tool("test")
        assert tool_info is not None
        assert tool_info.name == "test"
        
        # 获取不存在的工具
        assert registry.get_tool("nonexistent") is None
    
    def test_remove_tool(self):
        """测试移除工具"""
        registry = ToolRegistry()
        
        def test_tool():
            pass
        
        params = {"type": "object"}
        registry.register_tool(test_tool, "test", "Test tool", params)
        
        # 移除存在的工具
        assert registry.remove_tool("test") is True
        assert "test" not in registry._tools
        
        # 移除不存在的工具
        assert registry.remove_tool("nonexistent") is False
    
    def test_register_from_module(self):
        """测试从模块注册工具"""
        registry = ToolRegistry()
        
        # 创建带有工具信息的函数
        def tool_func():
            return "result"
        
        tool_func._mcp_tool_info = {
            "name": "module_tool",
            "description": "Tool from module",
            "parameters": {"type": "object"}
        }
        
        # 创建不带工具信息的普通函数
        def regular_func():
            return "regular"
        
        # 创建一个真实的类来模拟模块
        class MockModule:
            pass
        
        mock_module = MockModule()
        mock_module.tool_func = tool_func
        mock_module.regular_func = regular_func
        mock_module.OTHER_VAR = "not a function"
        
        # 注册工具
        registry.register_from_module(mock_module)
        
        # 验证工具被注册
        assert "module_tool" in registry._tools
        tool_info = registry._tools["module_tool"]
        assert tool_info.name == "module_tool"
        assert tool_info.description == "Tool from module"
    
    @pytest.mark.asyncio
    async def test_cleanup(self):
        """测试清理资源"""
        registry = ToolRegistry()
        
        # cleanup是个空操作，只要不抛异常即可
        await registry.cleanup()
    
    def test_tool_count(self):
        """测试工具计数属性"""
        registry = ToolRegistry()
        
        assert registry.tool_count == 0
        
        def tool1():
            pass
        
        def tool2():
            pass
        
        params = {"type": "object"}
        registry.register_tool(tool1, "tool1", "Tool 1", params)
        assert registry.tool_count == 1
        
        registry.register_tool(tool2, "tool2", "Tool 2", params)
        assert registry.tool_count == 2

def test_global_tool_decorator():
    """测试全局工具装饰器"""
    # 清理默认注册器以避免测试间干扰
    default_registry._tools.clear()
    
    @tool("global_tool", "Global tool", {"type": "object"})
    def global_tool_func(text: str) -> str:
        return f"global: {text}"
    
    assert "global_tool" in default_registry._tools
    tool_info = default_registry._tools["global_tool"]
    assert tool_info.name == "global_tool"

def test_global_register_tool():
    """测试全局工具注册函数"""
    # 清理默认注册器
    default_registry._tools.clear()
    
    def test_func():
        return "test"
    
    register_tool(test_func, "global_registered", "Global registered", {"type": "object"})
    
    assert "global_registered" in default_registry._tools

def test_get_registry():
    """测试获取全局注册器"""
    registry = get_registry()
    assert registry is default_registry