"""
MCP服务器核心模块

实现符合MCP协议规范的服务器基础架构。
"""

import asyncio
import signal
import sys
import uuid
from typing import Any, Dict, List, Optional, Callable, Awaitable
from contextlib import asynccontextmanager
import json
import time

from .config import Config, get_config
from .logger import get_logger, set_log_level
from .exceptions import (
    MCPError, ServerError, ConfigurationError, 
    ToolExecutionError, ValidationError
)
from .tools.registry import ToolRegistry

class MCPServer:
    """MCP服务器实现"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.logger = get_logger("mcp_server")
        self.tool_registry = ToolRegistry()
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._request_handlers: Dict[str, Callable] = {}
        self._setup_handlers()
        
        # 设置日志级别
        set_log_level(self.config.server.log_level)
        
        self.logger.info("MCP服务器初始化完成", config=self.config.to_dict())
    
    def _setup_handlers(self) -> None:
        """设置请求处理器"""
        self._request_handlers = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_list_tools,
            "tools/call": self._handle_call_tool,
            "ping": self._handle_ping
        }
    
    async def _handle_initialize(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """处理初始化请求"""
        params = request.get("params", {})
        client_info = params.get("clientInfo", {})
        protocol_version = params.get("protocolVersion")
        
        self.logger.info(
            "客户端初始化请求",
            client_name=client_info.get("name"),
            client_version=client_info.get("version"),
            protocol_version=protocol_version
        )
        
        # 验证协议版本
        if protocol_version != "2024-11-05":
            raise ValidationError(
                f"不支持的协议版本: {protocol_version}",
                details={"supported_version": "2024-11-05"}
            )
        
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "gemini-kling-mcp-service",
                "version": "0.1.0"
            }
        }
    
    async def _handle_list_tools(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """处理工具列表请求"""
        tools = self.tool_registry.list_tools()
        self.logger.info(f"返回工具列表，共{len(tools)}个工具")
        
        return {
            "tools": [tool.to_dict() for tool in tools]
        }
    
    async def _handle_call_tool(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """处理工具调用请求"""
        params = request.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if not tool_name:
            raise ValidationError("工具名称不能为空")
        
        request_id = str(uuid.uuid4())
        self.logger.set_request_id(request_id)
        
        start_time = time.time()
        
        try:
            self.logger.info(f"开始执行工具: {tool_name}", arguments=arguments)
            
            # 执行工具
            result = await self.tool_registry.call_tool(tool_name, arguments)
            
            duration = time.time() - start_time
            self.logger.log_tool_call(
                tool_name=tool_name,
                parameters=arguments,
                status="success",
                duration=duration
            )
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2)
                    }
                ]
            }
            
        except MCPError:
            # MCP异常直接重新抛出
            duration = time.time() - start_time
            self.logger.log_tool_call(
                tool_name=tool_name,
                parameters=arguments,
                status="error",
                duration=duration
            )
            raise
            
        except Exception as e:
            # 其他异常包装为工具执行错误
            duration = time.time() - start_time
            self.logger.exception(f"工具执行异常: {tool_name}")
            self.logger.log_tool_call(
                tool_name=tool_name,
                parameters=arguments,
                status="error",
                duration=duration,
                error=str(e)
            )
            raise ToolExecutionError(
                f"工具执行失败: {str(e)}",
                tool_name=tool_name,
                details={"original_error": str(e)}
            )
        finally:
            self.logger.clear_request_id()
    
    async def _handle_ping(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """处理ping请求"""
        return {"status": "ok", "timestamp": time.time()}
    
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """处理MCP请求"""
        method = request.get("method")
        request_id = request.get("id")
        
        if not method:
            raise ValidationError("请求方法不能为空")
        
        # 查找处理器
        handler = self._request_handlers.get(method)
        if not handler:
            raise ValidationError(
                f"不支持的请求方法: {method}",
                details={"supported_methods": list(self._request_handlers.keys())}
            )
        
        try:
            # 执行处理器
            result = await handler(request)
            
            # 构造响应
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result
            }
            
            return response
            
        except MCPError as e:
            # MCP异常转换为错误响应
            self.logger.error(f"请求处理失败: {method}", error=e.to_dict())
            
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": e.to_dict()["error"]
            }
            
            return response
        
        except Exception as e:
            # 其他异常转换为服务器错误
            self.logger.exception(f"请求处理异常: {method}")
            
            server_error = ServerError(
                f"服务器内部错误: {str(e)}",
                details={"method": method, "original_error": str(e)}
            )
            
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": server_error.to_dict()["error"]
            }
            
            return response
    
    async def run_stdio(self) -> None:
        """运行stdio模式的服务器"""
        self.logger.info("启动MCP服务器 (stdio模式)")
        self._running = True
        
        # 设置信号处理器
        self._setup_signal_handlers()
        
        try:
            # 读取stdin，处理请求
            while self._running:
                try:
                    # 读取一行输入
                    line = await self._read_stdin_line()
                    if not line:
                        break
                    
                    # 解析JSON请求
                    try:
                        request = json.loads(line)
                    except json.JSONDecodeError as e:
                        self.logger.error(f"JSON解析失败: {e}")
                        continue
                    
                    # 处理请求
                    response = await self.handle_request(request)
                    
                    # 输出响应
                    response_json = json.dumps(response, ensure_ascii=False)
                    print(response_json, flush=True)
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.logger.exception("处理请求时发生异常")
                    
        except KeyboardInterrupt:
            self.logger.info("收到中断信号，开始关闭服务器")
        finally:
            await self.shutdown()
    
    async def _read_stdin_line(self) -> str:
        """异步读取stdin行"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, sys.stdin.readline)
    
    def _setup_signal_handlers(self) -> None:
        """设置信号处理器"""
        if sys.platform != "win32":
            # Unix系统信号处理
            for sig in [signal.SIGTERM, signal.SIGINT]:
                signal.signal(sig, self._signal_handler)
    
    def _signal_handler(self, signum: int, frame) -> None:
        """信号处理器"""
        self.logger.info(f"收到信号 {signum}，准备关闭服务器")
        self._running = False
        self._shutdown_event.set()
    
    async def shutdown(self) -> None:
        """优雅关闭服务器"""
        self.logger.info("开始关闭MCP服务器")
        
        # 停止运行
        self._running = False
        
        # 清理资源
        try:
            await self.tool_registry.cleanup()
            self.logger.info("工具注册器清理完成")
        except Exception as e:
            self.logger.error(f"工具注册器清理失败: {e}")
        
        # 清理文件系统资源
        try:
            await self._cleanup_resources()
            self.logger.info("系统资源清理完成")
        except Exception as e:
            self.logger.error(f"系统资源清理失败: {e}")
        
        self.logger.info("MCP服务器关闭完成")
    
    async def _cleanup_resources(self) -> None:
        """清理系统资源"""
        # 这里可以添加清理临时文件、关闭数据库连接等逻辑
        pass
    
    def register_tool(self, tool_func: Callable, name: str, description: str,
                     parameters: Dict[str, Any]) -> None:
        """注册工具"""
        self.tool_registry.register_tool(tool_func, name, description, parameters)
        self.logger.info(f"注册工具: {name}")
    
    def register_tools_from_module(self, module) -> None:
        """从模块注册工具"""
        self.tool_registry.register_from_module(module)
        self.logger.info(f"从模块注册工具: {module.__name__}")
    
    @property
    def is_running(self) -> bool:
        """服务器是否正在运行"""
        return self._running
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        from .utils.health import HealthChecker
        
        health_checker = HealthChecker(self.config)
        return await health_checker.check_health()

async def create_server(config: Optional[Config] = None) -> MCPServer:
    """创建MCP服务器实例"""
    try:
        server = MCPServer(config)
        return server
    except Exception as e:
        logger = get_logger("server_factory")
        logger.exception("创建MCP服务器失败")
        raise ConfigurationError(f"服务器创建失败: {str(e)}")

async def main() -> None:
    """主函数"""
    try:
        # 创建服务器
        server = await create_server()
        
        # 运行服务器
        await server.run_stdio()
        
    except Exception as e:
        logger = get_logger("main")
        logger.exception("服务器启动失败")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())