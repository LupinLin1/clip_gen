"""
测试 Gemini HTTP 客户端
"""

import pytest
import json
from unittest.mock import AsyncMock, Mock, patch
import aiohttp
from aiohttp import ClientResponse, ClientError
import asyncio

from src.gemini_kling_mcp.config import GeminiConfig
from src.gemini_kling_mcp.services.gemini.client import GeminiClient, GeminiHTTPError
from src.gemini_kling_mcp.services.gemini.models import GeminiModel


@pytest.fixture
def gemini_config():
    """创建测试配置"""
    return GeminiConfig(
        api_key="test-api-key",
        base_url="https://test.googleapis.com",
        timeout=30,
        max_retries=2
    )


@pytest.fixture
def gemini_client(gemini_config):
    """创建测试客户端"""
    return GeminiClient(gemini_config)


class MockResponse:
    """模拟HTTP响应"""
    
    def __init__(self, status=200, json_data=None, text_data=""):
        self.status = status
        self._json_data = json_data or {}
        self._text_data = text_data or json.dumps(json_data or {})
    
    async def text(self):
        return self._text_data
    
    async def json(self):
        return self._json_data


class AsyncContextManagerMock:
    """模拟异步上下文管理器"""
    
    def __init__(self, return_value):
        self.return_value = return_value
    
    async def __aenter__(self):
        return self.return_value
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


class TestGeminiClientInit:
    """测试客户端初始化"""
    
    def test_client_init(self, gemini_config):
        """测试客户端初始化"""
        client = GeminiClient(gemini_config)
        
        assert client.config == gemini_config
        assert client.base_url == "https://test.googleapis.com"
        assert client.session is None
    
    def test_endpoints_configuration(self, gemini_client):
        """测试端点配置"""
        expected_endpoints = {
            "generate": "/v1beta/models/{model}:generateContent",
            "chat": "/v1beta/models/{model}:generateContent",
            "analyze": "/v1beta/models/{model}:generateContent"
        }
        
        assert gemini_client.endpoints == expected_endpoints


class TestGeminiClientSession:
    """测试客户端会话管理"""
    
    @pytest.mark.asyncio
    async def test_ensure_session_creation(self, gemini_client):
        """测试会话创建"""
        with patch('src.gemini_kling_mcp.services.gemini.client.ClientSession') as mock_session_class, \
             patch('src.gemini_kling_mcp.services.gemini.client.ClientTimeout') as mock_timeout_class, \
             patch('aiohttp.TCPConnector') as mock_connector_class:
            
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session
            mock_timeout_class.return_value = Mock()
            mock_connector_class.return_value = Mock()
            
            await gemini_client._ensure_session()
            
            assert gemini_client.session == mock_session
            mock_session_class.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close_session(self, gemini_client):
        """测试会话关闭"""
        mock_session = AsyncMock()
        mock_session.closed = False
        gemini_client.session = mock_session
        
        await gemini_client.close()
        
        mock_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close_no_session(self, gemini_client):
        """测试没有会话时的关闭"""
        await gemini_client.close()
        # 不应抛出异常
    
    @pytest.mark.asyncio
    async def test_context_manager(self, gemini_config):
        """测试上下文管理器"""
        with patch('src.gemini_kling_mcp.services.gemini.client.ClientSession') as mock_session_class, \
             patch('src.gemini_kling_mcp.services.gemini.client.ClientTimeout') as mock_timeout_class, \
             patch('aiohttp.TCPConnector') as mock_connector_class:
            
            mock_session = AsyncMock()
            mock_session.closed = False  # 添加 closed 属性
            mock_session_class.return_value = mock_session
            mock_timeout_class.return_value = Mock()
            mock_connector_class.return_value = Mock()
            
            async with GeminiClient(gemini_config) as client:
                assert client.session == mock_session
            
            mock_session.close.assert_called_once()


class TestGeminiClientRequests:
    """测试客户端请求功能"""
    
    @pytest.mark.asyncio
    async def test_successful_request(self, gemini_client):
        """测试成功请求"""
        expected_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Generated response"}]
                    },
                    "finishReason": "STOP"
                }
            ]
        }
        
        # 确保不会创建真正的会话
        with patch.object(gemini_client, '_ensure_session'):
            mock_session = Mock()
            mock_response = MockResponse(200, expected_response)
            
            # 使用 Mock 创建 request 方法，返回异步上下文管理器
            mock_session.request = Mock(return_value=AsyncContextManagerMock(mock_response))
            
            gemini_client.session = mock_session
            
            result = await gemini_client._make_request(
                "POST", 
                "https://test.googleapis.com/test",
                json_data={"test": "data"}
            )
            
            assert result == expected_response
            mock_session.request.assert_called_once()
    
    @pytest.mark.asyncio 
    async def test_api_error_response(self, gemini_client):
        """测试API错误响应"""
        error_response = {
            "error": {
                "code": 400,
                "message": "Invalid request",
                "status": "INVALID_ARGUMENT"
            }
        }
        
        with patch.object(gemini_client, '_ensure_session'):
            mock_session = Mock()
            mock_response = MockResponse(400, error_response)
            
            mock_session.request = Mock(return_value=AsyncContextManagerMock(mock_response))
            
            gemini_client.session = mock_session
            
            with pytest.raises(GeminiHTTPError) as exc_info:
                await gemini_client._make_request(
                    "POST",
                    "https://test.googleapis.com/test",
                    json_data={"test": "data"}
                )
            
            assert exc_info.value.status_code == 400
            assert "Invalid request" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_network_error(self, gemini_client):
        """测试网络错误"""
        with patch.object(gemini_client, '_ensure_session'):
            mock_session = Mock()
            mock_session.request = Mock(side_effect=ClientError("Network error"))
            
            gemini_client.session = mock_session
            
            with pytest.raises(GeminiHTTPError) as exc_info:
                await gemini_client._make_request(
                    "POST",
                    "https://test.googleapis.com/test"
                )
            
            assert "网络请求失败" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_timeout_error(self, gemini_client):
        """测试超时错误"""
        with patch.object(gemini_client, '_ensure_session'):
            mock_session = Mock()
            mock_session.request = Mock(side_effect=asyncio.TimeoutError())
            
            gemini_client.session = mock_session
            
            with pytest.raises(GeminiHTTPError) as exc_info:
                await gemini_client._make_request(
                    "POST",
                    "https://test.googleapis.com/test"
                )
            
            assert "请求超时" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_retry_on_server_error(self, gemini_client):
        """测试服务器错误时的重试"""
        # 第一次返回500错误，第二次成功
        success_response = {"candidates": [{"content": {"parts": [{"text": "Success"}]}}]}
        
        with patch.object(gemini_client, '_ensure_session'):
            mock_session = Mock()
            
            # 创建失败和成功的响应
            error_response = MockResponse(500, {"error": {"message": "Internal error"}})
            success_response_mock = MockResponse(200, success_response)
            
            # 设置调用序列：第一次失败，第二次成功
            mock_session.request = Mock(side_effect=[
                AsyncContextManagerMock(error_response),
                AsyncContextManagerMock(success_response_mock)
            ])
            
            gemini_client.session = mock_session
            
            # 模拟等待时间
            with patch('asyncio.sleep'):
                result = await gemini_client._make_request(
                    "POST",
                    "https://test.googleapis.com/test"
                )
            
            assert result == success_response
            assert mock_session.request.call_count == 2
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, gemini_client):
        """测试超过最大重试次数"""
        with patch.object(gemini_client, '_ensure_session'):
            mock_session = Mock()
            error_response = MockResponse(500, {"error": {"message": "Server error"}})
            
            mock_session.request = Mock(return_value=AsyncContextManagerMock(error_response))
            gemini_client.session = mock_session
            
            with patch('asyncio.sleep'):
                with pytest.raises(GeminiHTTPError) as exc_info:
                    await gemini_client._make_request(
                        "POST",
                        "https://test.googleapis.com/test"
                    )
            
            assert exc_info.value.status_code == 500
            # 应该重试max_retries次：初始请求 + 2次重试 = 3次总请求
            assert mock_session.request.call_count == 3


class TestGeminiClientResponseParsing:
    """测试客户端响应解析"""
    
    def test_extract_generated_text_success(self, gemini_client):
        """测试成功提取生成文本"""
        response = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Generated text"}]
                    }
                }
            ]
        }
        
        text = gemini_client.extract_generated_text(response)
        assert text == "Generated text"
    
    def test_extract_generated_text_alternative_format(self, gemini_client):
        """测试从替代格式提取文本"""
        response = {"text": "Direct text response"}
        
        text = gemini_client.extract_generated_text(response)
        assert text == "Direct text response"
    
    def test_extract_generated_text_empty(self, gemini_client):
        """测试从空响应提取文本"""
        response = {}
        
        text = gemini_client.extract_generated_text(response)
        assert text == ""
    
    def test_extract_usage_info(self, gemini_client):
        """测试提取使用信息"""
        response = {
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 20,
                "totalTokenCount": 30
            }
        }
        
        usage = gemini_client.extract_usage_info(response)
        
        expected_usage = {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30
        }
        
        assert usage == expected_usage
    
    def test_extract_usage_info_none(self, gemini_client):
        """测试没有使用信息时的提取"""
        response = {}
        
        usage = gemini_client.extract_usage_info(response)
        assert usage is None
    
    def test_extract_safety_ratings(self, gemini_client):
        """测试提取安全评级"""
        response = {
            "candidates": [
                {
                    "safetyRatings": [
                        {
                            "category": "HARM_CATEGORY_HARASSMENT",
                            "probability": "LOW"
                        }
                    ]
                }
            ]
        }
        
        safety_ratings = gemini_client.extract_safety_ratings(response)
        
        expected_ratings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "probability": "LOW"
            }
        ]
        
        assert safety_ratings == expected_ratings


class TestGeminiClientAPIEndpoints:
    """测试客户端API端点"""
    
    def test_get_endpoint_url(self, gemini_client):
        """测试获取端点URL"""
        url = gemini_client._get_endpoint_url("generate", "gemini-1.5-flash-002")
        expected = "https://test.googleapis.com/v1beta/models/gemini-1.5-flash-002:generateContent"
        assert url == expected
    
    def test_get_endpoint_url_with_enum(self, gemini_client):
        """测试使用枚举获取端点URL"""
        url = gemini_client._get_endpoint_url("generate", GeminiModel.GEMINI_15_PRO)
        expected = "https://test.googleapis.com/v1beta/models/gemini-1.5-pro-002:generateContent"
        assert url == expected
    
    @pytest.mark.asyncio
    async def test_generate_content(self, gemini_client):
        """测试生成内容方法"""
        expected_response = {"candidates": []}
        
        with patch.object(gemini_client, '_make_request', return_value=expected_response) as mock_request:
            request_data = {"contents": [{"parts": [{"text": "Hello"}]}]}
            
            result = await gemini_client.generate_content("gemini-1.5-flash-002", request_data)
            
            assert result == expected_response
            mock_request.assert_called_once()
            
            # 验证调用参数
            args, kwargs = mock_request.call_args
            assert args[0] == "POST"
            assert "generateContent" in args[1]
            assert kwargs["json_data"] == request_data
    
    @pytest.mark.asyncio  
    async def test_chat_completion(self, gemini_client):
        """测试对话完成方法"""
        expected_response = {"candidates": []}
        
        with patch.object(gemini_client, '_make_request', return_value=expected_response) as mock_request:
            request_data = {"contents": []}
            
            result = await gemini_client.chat_completion("gemini-1.5-flash-002", request_data)
            
            assert result == expected_response
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_analyze_text(self, gemini_client):
        """测试文本分析方法"""
        expected_response = {"candidates": []}
        
        with patch.object(gemini_client, '_make_request', return_value=expected_response) as mock_request:
            request_data = {"contents": []}
            
            result = await gemini_client.analyze_text("gemini-1.5-flash-002", request_data)
            
            assert result == expected_response
            mock_request.assert_called_once()


class TestGeminiClientErrorHandling:
    """测试客户端错误处理"""
    
    def test_should_retry_retryable_status(self, gemini_client):
        """测试可重试状态码判断"""
        retryable_codes = [429, 500, 502, 503, 504]
        
        for code in retryable_codes:
            assert gemini_client._should_retry(code, 0) is True
    
    def test_should_retry_non_retryable_status(self, gemini_client):
        """测试不可重试状态码判断"""  
        non_retryable_codes = [400, 401, 403, 404]
        
        for code in non_retryable_codes:
            assert gemini_client._should_retry(code, 0) is False
    
    def test_should_retry_max_retries_exceeded(self, gemini_client):
        """测试超过最大重试次数"""
        assert gemini_client._should_retry(500, 3) is False
    
    def test_extract_error_message_with_error_field(self, gemini_client):
        """测试从错误字段提取消息"""
        error_data = {
            "error": {
                "message": "Detailed error message"
            }
        }
        
        message = gemini_client._extract_error_message(error_data, 400)
        assert message == "Detailed error message"
    
    def test_extract_error_message_with_message_field(self, gemini_client):
        """测试从消息字段提取"""
        error_data = {"message": "Simple error message"}
        
        message = gemini_client._extract_error_message(error_data, 400)
        assert message == "Simple error message"
    
    def test_extract_error_message_fallback(self, gemini_client):
        """测试错误消息回退"""
        error_data = {}
        
        message = gemini_client._extract_error_message(error_data, 500)
        assert "未知API错误" in message
        assert "500" in message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])