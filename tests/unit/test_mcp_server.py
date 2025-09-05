"""
测试MCP服务器核心模块
"""

import json
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import pytest

from src.gemini_kling_mcp.mcp_server import MCPServer, create_server, main
from src.gemini_kling_mcp.config import Config
from src.gemini_kling_mcp.exceptions import ValidationError, MCPError, ServerError

class TestMCPServer:
    """测试MCPServer类"""
    
    @pytest.fixture
    def mock_config(self):
        """创建模拟配置"""
        config = MagicMock()
        config.server = MagicMock()
        config.server.log_level = "INFO"
        config.server.debug = False
        config.to_dict.return_value = {"test": "config"}
        return config
    
    def test_initialization(self, mock_config):
        """测试服务器初始化"""
        with patch('src.gemini_kling_mcp.mcp_server.get_config', return_value=mock_config):
            server = MCPServer(mock_config)
        
        assert server.config is mock_config
        assert server._running is False
        assert len(server._request_handlers) == 4  # initialize, tools/list, tools/call, ping
        assert "initialize" in server._request_handlers
        assert "tools/list" in server._request_handlers
        assert "tools/call" in server._request_handlers
        assert "ping" in server._request_handlers
    
    @pytest.mark.asyncio
    async def test_handle_initialize_success(self, mock_config):
        """测试处理初始化请求成功"""
        with patch('src.gemini_kling_mcp.mcp_server.get_config', return_value=mock_config):
            server = MCPServer(mock_config)
        
        request = {
            "method": "initialize",
            "params": {
                "clientInfo": {"name": "test-client", "version": "1.0"},
                "protocolVersion": "2024-11-05"
            }
        }
        
        result = await server._handle_initialize(request)
        
        assert result["protocolVersion"] == "2024-11-05"
        assert "capabilities" in result
        assert "serverInfo" in result
        assert result["serverInfo"]["name"] == "gemini-kling-mcp-service"
    
    @pytest.mark.asyncio
    async def test_handle_initialize_unsupported_version(self, mock_config):
        """测试处理初始化请求不支持的版本"""
        with patch('src.gemini_kling_mcp.mcp_server.get_config', return_value=mock_config):
            server = MCPServer(mock_config)
        
        request = {
            "method": "initialize",
            "params": {
                "protocolVersion": "unsupported-version"
            }
        }
        
        with pytest.raises(ValidationError, match="不支持的协议版本"):
            await server._handle_initialize(request)
    
    @pytest.mark.asyncio
    async def test_handle_list_tools(self, mock_config):
        """测试处理工具列表请求"""
        with patch('src.gemini_kling_mcp.mcp_server.get_config', return_value=mock_config):
            server = MCPServer(mock_config)
        
        # Mock工具注册器
        mock_tool = MagicMock()
        mock_tool.to_dict.return_value = {"name": "test_tool", "description": "Test tool"}
        server.tool_registry.list_tools = MagicMock(return_value=[mock_tool])
        
        request = {"method": "tools/list"}
        result = await server._handle_list_tools(request)
        
        assert "tools" in result
        assert len(result["tools"]) == 1
        assert result["tools"][0]["name"] == "test_tool"
    
    @pytest.mark.asyncio
    async def test_handle_call_tool_success(self, mock_config):
        """测试处理工具调用请求成功"""
        with patch('src.gemini_kling_mcp.mcp_server.get_config', return_value=mock_config):
            server = MCPServer(mock_config)
        
        # Mock工具注册器
        server.tool_registry.call_tool = AsyncMock(return_value={"result": "success"})
        
        request = {
            "method": "tools/call",
            "params": {
                "name": "test_tool",
                "arguments": {"param1": "value1"}
            }
        }
        
        result = await server._handle_call_tool(request)
        
        assert "content" in result
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"
        
        # 解析JSON内容
        content_json = json.loads(result["content"][0]["text"])
        assert content_json["result"] == "success"
    
    @pytest.mark.asyncio
    async def test_handle_call_tool_missing_name(self, mock_config):
        """测试处理工具调用请求缺少工具名"""
        with patch('src.gemini_kling_mcp.mcp_server.get_config', return_value=mock_config):
            server = MCPServer(mock_config)
        
        request = {
            "method": "tools/call",
            "params": {
                "arguments": {"param1": "value1"}
            }
        }
        
        with pytest.raises(ValidationError, match="工具名称不能为空"):
            await server._handle_call_tool(request)
    
    @pytest.mark.asyncio
    async def test_handle_call_tool_exception(self, mock_config):
        """测试处理工具调用请求异常"""
        with patch('src.gemini_kling_mcp.mcp_server.get_config', return_value=mock_config):
            server = MCPServer(mock_config)
        
        # Mock工具注册器抛出异常
        server.tool_registry.call_tool = AsyncMock(side_effect=RuntimeError("Tool failed"))
        
        request = {
            "method": "tools/call",
            "params": {
                "name": "failing_tool",
                "arguments": {}
            }
        }
        
        with pytest.raises(Exception):  # 会包装为ToolExecutionError
            await server._handle_call_tool(request)
    
    @pytest.mark.asyncio
    async def test_handle_ping(self, mock_config):
        """测试处理ping请求"""
        with patch('src.gemini_kling_mcp.mcp_server.get_config', return_value=mock_config):
            server = MCPServer(mock_config)
        
        request = {"method": "ping"}
        result = await server._handle_ping(request)
        
        assert result["status"] == "ok"
        assert "timestamp" in result
        assert isinstance(result["timestamp"], float)
    
    @pytest.mark.asyncio
    async def test_handle_request_success(self, mock_config):
        """测试处理请求成功"""
        with patch('src.gemini_kling_mcp.mcp_server.get_config', return_value=mock_config):
            server = MCPServer(mock_config)
        
        request = {
            "jsonrpc": "2.0",
            "id": "test-123",
            "method": "ping",
            "params": {}
        }
        
        response = await server.handle_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "test-123"
        assert "result" in response
        assert response["result"]["status"] == "ok"
    
    @pytest.mark.asyncio
    async def test_handle_request_missing_method(self, mock_config):
        """测试处理请求缺少方法"""
        with patch('src.gemini_kling_mcp.mcp_server.get_config', return_value=mock_config):
            server = MCPServer(mock_config)
        
        request = {
            "jsonrpc": "2.0",
            "id": "test-123",
            "params": {}
        }
        
        response = await server.handle_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "test-123"
        assert "error" in response
        assert "请求方法不能为空" in response["error"]["message"]
    
    @pytest.mark.asyncio
    async def test_handle_request_unsupported_method(self, mock_config):
        """测试处理请求不支持的方法"""
        with patch('src.gemini_kling_mcp.mcp_server.get_config', return_value=mock_config):
            server = MCPServer(mock_config)
        
        request = {
            "jsonrpc": "2.0",
            "id": "test-123",
            "method": "unsupported_method",
            "params": {}
        }
        
        response = await server.handle_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "test-123"
        assert "error" in response
        assert "不支持的请求方法" in response["error"]["message"]
    
    @pytest.mark.asyncio
    async def test_handle_request_mcp_error(self, mock_config):
        """测试处理请求MCP异常"""
        with patch('src.gemini_kling_mcp.mcp_server.get_config', return_value=mock_config):
            server = MCPServer(mock_config)
        
        # Mock ping方法抛出MCP异常
        original_ping = server._handle_ping
        async def mock_ping(request):
            raise ValidationError("Test MCP error")
        server._handle_ping = mock_ping
        
        request = {
            "jsonrpc": "2.0",
            "id": "test-123",
            "method": "ping"
        }
        
        response = await server.handle_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "test-123"
        assert "error" in response
        assert response["error"]["message"] == "Test MCP error"
    
    @pytest.mark.asyncio
    async def test_handle_request_generic_exception(self, mock_config):
        """测试处理请求通用异常"""
        with patch('src.gemini_kling_mcp.mcp_server.get_config', return_value=mock_config):
            server = MCPServer(mock_config)
        
        # Mock ping方法抛出通用异常
        async def mock_ping(request):
            raise RuntimeError("Generic error")
        server._handle_ping = mock_ping
        
        request = {
            "jsonrpc": "2.0",
            "id": "test-123",
            "method": "ping"
        }
        
        response = await server.handle_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "test-123"
        assert "error" in response
        assert "服务器内部错误" in response["error"]["message"]
    
    @pytest.mark.asyncio
    async def test_shutdown(self, mock_config):
        """测试服务器关闭"""
        with patch('src.gemini_kling_mcp.mcp_server.get_config', return_value=mock_config):
            server = MCPServer(mock_config)
        
        server._running = True
        server.tool_registry.cleanup = AsyncMock()
        
        await server.shutdown()
        
        assert server._running is False
        server.tool_registry.cleanup.assert_called_once()
    
    def test_register_tool(self, mock_config):
        """测试注册工具"""
        with patch('src.gemini_kling_mcp.mcp_server.get_config', return_value=mock_config):
            server = MCPServer(mock_config)
        
        def test_tool():
            return "test"
        
        server.tool_registry.register_tool = MagicMock()
        
        server.register_tool(
            test_tool,
            "test_tool",
            "Test tool",
            {"type": "object"}
        )
        
        server.tool_registry.register_tool.assert_called_once_with(
            test_tool,
            "test_tool",
            "Test tool",
            {"type": "object"}
        )
    
    def test_register_tools_from_module(self, mock_config):
        """测试从模块注册工具"""
        with patch('src.gemini_kling_mcp.mcp_server.get_config', return_value=mock_config):
            server = MCPServer(mock_config)
        
        mock_module = MagicMock()
        server.tool_registry.register_from_module = MagicMock()
        
        server.register_tools_from_module(mock_module)
        
        server.tool_registry.register_from_module.assert_called_once_with(mock_module)
    
    def test_is_running_property(self, mock_config):
        """测试运行状态属性"""
        with patch('src.gemini_kling_mcp.mcp_server.get_config', return_value=mock_config):
            server = MCPServer(mock_config)
        
        assert server.is_running is False
        
        server._running = True
        assert server.is_running is True
    
    @pytest.mark.asyncio
    async def test_health_check(self, mock_config):
        """测试健康检查"""
        with patch('src.gemini_kling_mcp.mcp_server.get_config', return_value=mock_config):
            server = MCPServer(mock_config)
        
        mock_health_data = {"status": "healthy", "components": {}}
        
        with patch('src.gemini_kling_mcp.utils.health.HealthChecker') as MockHealthChecker:
            mock_checker = MockHealthChecker.return_value
            mock_checker.check_health = AsyncMock(return_value=mock_health_data)
            
            result = await server.health_check()
            
            assert result == mock_health_data
            MockHealthChecker.assert_called_once_with(mock_config)

@pytest.mark.asyncio
async def test_create_server_success():
    """测试创建服务器成功"""
    mock_config = MagicMock()
    mock_config.server.log_level = "INFO"
    
    with patch('src.gemini_kling_mcp.mcp_server.get_config', return_value=mock_config):
        server = await create_server(mock_config)
    
    assert isinstance(server, MCPServer)
    assert server.config is mock_config

@pytest.mark.asyncio
async def test_create_server_failure():
    """测试创建服务器失败"""
    with patch('src.gemini_kling_mcp.mcp_server.MCPServer', side_effect=RuntimeError("Init failed")):
        with pytest.raises(Exception):  # 应该包装为ConfigurationError
            await create_server()

@pytest.mark.asyncio
async def test_main_success():
    """测试main函数成功"""
    mock_server = AsyncMock()
    mock_server.run_stdio = AsyncMock()
    
    with patch('src.gemini_kling_mcp.mcp_server.create_server', return_value=mock_server):
        await main()
    
    mock_server.run_stdio.assert_called_once()

@pytest.mark.asyncio
async def test_main_failure():
    """测试main函数失败"""
    with patch('src.gemini_kling_mcp.mcp_server.create_server', side_effect=RuntimeError("Create failed")):
        with patch('sys.exit') as mock_exit:
            await main()
            mock_exit.assert_called_once_with(1)