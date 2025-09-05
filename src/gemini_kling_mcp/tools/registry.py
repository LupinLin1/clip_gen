"""
工具注册和管理模块

提供装饰器模式的工具注册机制，简化工具开发和管理。
"""

import inspect
from typing import Dict, List, Any, Callable, Optional, Union
from dataclasses import dataclass
from functools import wraps
import asyncio

from ..logger import get_logger
from ..exceptions import ToolExecutionError, ValidationError

@dataclass
class ToolInfo:
    """工具信息"""
    name: str
    description: str
    parameters: Dict[str, Any]
    function: Callable
    is_async: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为MCP工具格式"""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                "properties": self.parameters.get("properties", {}),
                "required": self.parameters.get("required", []),
                "additionalProperties": self.parameters.get("additionalProperties", False)
            }
        }

class ToolRegistry:
    """工具注册管理器"""
    
    def __init__(self):
        self.logger = get_logger("tool_registry")
        self._tools: Dict[str, ToolInfo] = {}
        self._middleware: List[Callable] = []
    
    def register_tool(self, func: Callable, name: str, description: str,
                     parameters: Dict[str, Any]) -> None:
        """注册工具"""
        if name in self._tools:
            raise ValueError(f"工具名称已存在: {name}")
        
        # 检查函数是否为异步函数
        is_async = asyncio.iscoroutinefunction(func)
        
        # 创建工具信息
        tool_info = ToolInfo(
            name=name,
            description=description,
            parameters=parameters,
            function=func,
            is_async=is_async
        )
        
        self._tools[name] = tool_info
        self.logger.info(f"注册工具: {name}", is_async=is_async)
    
    def tool(self, name: str, description: str, 
            parameters: Optional[Dict[str, Any]] = None):
        """工具装饰器"""
        def decorator(func: Callable):
            # 自动从函数签名推导参数schema（如果没有提供）
            tool_parameters = parameters or self._extract_parameters_from_signature(func)
            
            # 注册工具
            self.register_tool(func, name, description, tool_parameters)
            
            @wraps(func)
            async def wrapper(*args, **kwargs):
                return await self.call_tool(name, kwargs)
            
            return wrapper
        return decorator
    
    def _extract_parameters_from_signature(self, func: Callable) -> Dict[str, Any]:
        """从函数签名提取参数schema"""
        sig = inspect.signature(func)
        properties = {}
        required = []
        
        for param_name, param in sig.parameters.items():
            # 跳过self参数
            if param_name == 'self':
                continue
                
            # 基础参数信息
            param_info = {"type": "string"}  # 默认为字符串类型
            
            # 根据类型注解推断参数类型
            if param.annotation != param.empty:
                if param.annotation == int:
                    param_info["type"] = "integer"
                elif param.annotation == float:
                    param_info["type"] = "number"
                elif param.annotation == bool:
                    param_info["type"] = "boolean"
                elif param.annotation == list or param.annotation == List:
                    param_info["type"] = "array"
                elif param.annotation == dict or param.annotation == Dict:
                    param_info["type"] = "object"
                elif hasattr(param.annotation, '__origin__'):
                    # 处理泛型类型
                    if param.annotation.__origin__ == list:
                        param_info["type"] = "array"
                    elif param.annotation.__origin__ == dict:
                        param_info["type"] = "object"
                    elif param.annotation.__origin__ == Union:
                        # 处理Optional类型
                        if len(param.annotation.__args__) == 2 and type(None) in param.annotation.__args__:
                            non_none_type = [arg for arg in param.annotation.__args__ if arg != type(None)][0]
                            if non_none_type == str:
                                param_info["type"] = "string"
                            elif non_none_type == int:
                                param_info["type"] = "integer"
                            elif non_none_type == float:
                                param_info["type"] = "number"
                            elif non_none_type == bool:
                                param_info["type"] = "boolean"
            
            # 检查是否有默认值
            if param.default == param.empty:
                required.append(param_name)
            else:
                param_info["default"] = param.default
            
            properties[param_name] = param_info
        
        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False
        }
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """调用工具"""
        if name not in self._tools:
            raise ToolExecutionError(f"工具不存在: {name}", tool_name=name)
        
        tool_info = self._tools[name]
        
        try:
            # 验证参数
            self._validate_arguments(tool_info, arguments)
            
            # 应用中间件
            for middleware in self._middleware:
                arguments = await self._apply_middleware(middleware, name, arguments)
            
            # 执行工具
            if tool_info.is_async:
                result = await tool_info.function(**arguments)
            else:
                # 在执行器中运行同步函数
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lambda: tool_info.function(**arguments))
            
            return result
            
        except ValidationError:
            # 参数验证错误直接重新抛出
            raise
        except ToolExecutionError:
            # 工具执行错误直接重新抛出
            raise
        except Exception as e:
            # 其他异常包装为工具执行错误
            self.logger.exception(f"工具执行异常: {name}")
            raise ToolExecutionError(
                f"工具执行失败: {str(e)}",
                tool_name=name,
                details={"arguments": arguments, "error": str(e)}
            )
    
    def _validate_arguments(self, tool_info: ToolInfo, arguments: Dict[str, Any]) -> None:
        """验证工具参数"""
        schema = tool_info.parameters
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        # 检查必需参数
        for req_param in required:
            if req_param not in arguments:
                raise ValidationError(
                    f"缺少必需参数: {req_param}",
                    details={"tool": tool_info.name, "required_params": required}
                )
        
        # 检查参数类型
        for param_name, param_value in arguments.items():
            if param_name in properties:
                param_schema = properties[param_name]
                expected_type = param_schema.get("type")
                
                if not self._validate_parameter_type(param_value, expected_type):
                    raise ValidationError(
                        f"参数类型错误: {param_name} 应为 {expected_type}",
                        details={
                            "tool": tool_info.name,
                            "parameter": param_name,
                            "expected_type": expected_type,
                            "actual_type": type(param_value).__name__
                        }
                    )
    
    def _validate_parameter_type(self, value: Any, expected_type: str) -> bool:
        """验证参数类型"""
        if expected_type == "string":
            return isinstance(value, str)
        elif expected_type == "integer":
            return isinstance(value, int)
        elif expected_type == "number":
            return isinstance(value, (int, float))
        elif expected_type == "boolean":
            return isinstance(value, bool)
        elif expected_type == "array":
            return isinstance(value, list)
        elif expected_type == "object":
            return isinstance(value, dict)
        else:
            return True  # 未知类型不做验证
    
    async def _apply_middleware(self, middleware: Callable, tool_name: str, 
                              arguments: Dict[str, Any]) -> Dict[str, Any]:
        """应用中间件"""
        if asyncio.iscoroutinefunction(middleware):
            return await middleware(tool_name, arguments)
        else:
            return middleware(tool_name, arguments)
    
    def add_middleware(self, middleware: Callable) -> None:
        """添加中间件"""
        self._middleware.append(middleware)
        self.logger.info(f"添加中间件: {middleware.__name__}")
    
    def list_tools(self) -> List[ToolInfo]:
        """获取工具列表"""
        return list(self._tools.values())
    
    def get_tool(self, name: str) -> Optional[ToolInfo]:
        """获取工具信息"""
        return self._tools.get(name)
    
    def remove_tool(self, name: str) -> bool:
        """移除工具"""
        if name in self._tools:
            del self._tools[name]
            self.logger.info(f"移除工具: {name}")
            return True
        return False
    
    def register_from_module(self, module) -> None:
        """从模块注册工具"""
        # 查找模块中的工具函数
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            
            # 检查是否为函数且有工具标记
            if (callable(attr) and 
                hasattr(attr, '_mcp_tool_info')):
                
                tool_info = attr._mcp_tool_info
                self.register_tool(
                    attr,
                    tool_info['name'],
                    tool_info['description'],
                    tool_info['parameters']
                )
    
    async def cleanup(self) -> None:
        """清理资源"""
        self.logger.info("清理工具注册器")
        # 这里可以添加资源清理逻辑
        pass
    
    @property
    def tool_count(self) -> int:
        """工具数量"""
        return len(self._tools)

# 全局工具注册实例
default_registry = ToolRegistry()

def tool(name: str, description: str, parameters: Optional[Dict[str, Any]] = None):
    """全局工具装饰器"""
    return default_registry.tool(name, description, parameters)

def register_tool(func: Callable, name: str, description: str, 
                 parameters: Dict[str, Any]) -> None:
    """全局工具注册函数"""
    default_registry.register_tool(func, name, description, parameters)

def get_registry() -> ToolRegistry:
    """获取全局工具注册器"""
    return default_registry