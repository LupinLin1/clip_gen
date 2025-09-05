"""
测试 Kling HTTP 客户端
"""

import pytest
import json
import aiohttp
from unittest.mock import AsyncMock, Mock, patch
from aiohttp import ClientSession

from src.gemini_kling_mcp.services.kling.client import (
    KlingClient,
    KlingHTTPError
)
from src.gemini_kling_mcp.services.kling.models import (
    KlingVideoRequest,
    KlingVideoConfig,
    KlingModel,
    KlingTaskStatus
)

@pytest.fixture
def client():
    """创建测试客户端"""
    return KlingClient("test-api-key", "https://api.test.com")

@pytest.fixture 
def sample_request():
    """创建示例请求"""
    return KlingVideoRequest(
        prompt="Test video generation",
        config=KlingVideoConfig()
    )

class TestKlingClient:
    """测试 Kling 客户端"""
    
    def test_init(self):
        """测试客户端初始化"""
        client = KlingClient("test-key", "https://api.test.com")
        
        assert client.api_key == "test-key"
        assert client.base_url == "https://api.test.com"
        assert client.timeout == 300
        assert client.max_retries == 3
        assert client.session is None
    
    def test_init_with_trailing_slash(self):
        """测试带尾部斜杠的 URL 初始化"""
        client = KlingClient("test-key", "https://api.test.com/")
        
        assert client.base_url == "https://api.test.com"
    
    async def test_context_manager(self):
        """测试异步上下文管理器"""
        client = KlingClient("test-key", "https://api.test.com")
        
        async with client as c:
            assert c is client
            assert c.session is not None
            assert isinstance(c.session, ClientSession)
        
        # 上下文退出后应该关闭会话
        assert client.session.closed
    
    async def test_ensure_session(self, client):
        """测试会话创建"""
        assert client.session is None
        
        await client._ensure_session()
        
        assert client.session is not None
        assert isinstance(client.session, ClientSession)
        assert client.session._timeout.total == 300
        
        await client.close()
    
    def test_get_endpoint_url(self, client):
        """测试端点 URL 生成"""
        # 测试字符串模型
        url = client._get_endpoint_url("text_to_video")
        assert url == "https://api.test.com/v1/video_generation"
        
        # 测试任务状态端点
        url = client._get_endpoint_url("task_status", task_id="test-123")
        assert url == "https://api.test.com/v1/query/test-123"
    
    @pytest.mark.asyncio
    async def test_make_request_success(self, client):
        """测试成功的 HTTP 请求"""
        mock_response_data = {"task_id": "test-123", "status": "pending"}
        
        with patch.object(client, '_ensure_session') as mock_ensure:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value=json.dumps(mock_response_data))
            
            # 创建正确的异步上下文管理器mock
            mock_context_manager = AsyncMock()
            mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
            mock_context_manager.__aexit__ = AsyncMock(return_value=None)
            
            mock_session.request = Mock(return_value=mock_context_manager)
            client.session = mock_session
            
            result = await client._make_request(
                "POST", 
                "https://api.test.com/test",
                {"test": "data"}
            )
            
            assert result == mock_response_data
            mock_session.request.assert_called_once_with(
                method="POST",
                url="https://api.test.com/test",
                json={"test": "data"},
                params=None
            )
    
    @pytest.mark.asyncio
    async def test_make_request_http_error(self, client):
        """测试 HTTP 错误响应"""
        from src.gemini_kling_mcp.services.kling.models import KlingValidationError
        
        error_data = {"error": {"message": "API error", "code": "TEST_ERROR"}}
        
        with patch.object(client, '_ensure_session'):
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 400
            mock_response.text = AsyncMock(return_value=json.dumps(error_data))
            
            # 创建正确的异步上下文管理器mock
            mock_context_manager = AsyncMock()
            mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
            mock_context_manager.__aexit__ = AsyncMock(return_value=None)
            
            mock_session.request = Mock(return_value=mock_context_manager)
            client.session = mock_session
            
            with pytest.raises(KlingValidationError) as exc_info:
                await client._make_request("POST", "https://api.test.com/test")
            
            assert exc_info.value.status_code == 400
            assert "API error" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_make_request_json_decode_error(self, client):
        """测试 JSON 解析错误"""
        with patch.object(client, '_ensure_session'):
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value="invalid json")
            
            # 创建正确的异步上下文管理器mock
            mock_context_manager = AsyncMock()
            mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
            mock_context_manager.__aexit__ = AsyncMock(return_value=None)
            
            mock_session.request = Mock(return_value=mock_context_manager)
            client.session = mock_session
            
            with pytest.raises(KlingHTTPError) as exc_info:
                await client._make_request("POST", "https://api.test.com/test")
            
            assert "响应格式错误" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_make_request_network_error(self, client):
        """测试网络错误"""
        with patch.object(client, '_ensure_session'):
            # 直接给客户端设置一个会抛出异常的session
            client.session = AsyncMock()
            
            # 创建一个异步上下文管理器，但是在__aenter__时抛出异常
            mock_context_manager = AsyncMock()
            
            async def raise_client_error(*args, **kwargs):
                raise aiohttp.ClientError("Network error")
            
            mock_context_manager.__aenter__ = raise_client_error
            mock_context_manager.__aexit__ = AsyncMock(return_value=None)
            
            client.session.request = Mock(return_value=mock_context_manager)
            
            with pytest.raises(KlingHTTPError) as exc_info:
                await client._make_request("POST", "https://api.test.com/test")
            
            assert "网络请求失败" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_make_request_retry(self, client):
        """测试请求重试机制"""
        success_data = {"task_id": "test-123", "status": "pending"}
        
        with patch.object(client, '_ensure_session'):
            mock_session = AsyncMock()
            
            # 第一次请求失败（500错误）
            mock_response_fail = AsyncMock()
            mock_response_fail.status = 500
            mock_response_fail.text = AsyncMock(return_value='{"error": "Server error"}')
            
            # 第二次请求成功
            mock_response_success = AsyncMock()
            mock_response_success.status = 200
            mock_response_success.text = AsyncMock(return_value=json.dumps(success_data))
            
            # 创建异步上下文管理器mock
            mock_context_manager_fail = AsyncMock()
            mock_context_manager_fail.__aenter__ = AsyncMock(return_value=mock_response_fail)
            mock_context_manager_fail.__aexit__ = AsyncMock(return_value=None)
            
            mock_context_manager_success = AsyncMock()
            mock_context_manager_success.__aenter__ = AsyncMock(return_value=mock_response_success)
            mock_context_manager_success.__aexit__ = AsyncMock(return_value=None)
            
            # 模拟请求序列
            mock_session.request = Mock(side_effect=[mock_context_manager_fail, mock_context_manager_success])
            client.session = mock_session
            
            # 模拟等待时间（加速测试）
            with patch.object(client, '_wait_before_retry', new=AsyncMock()):
                result = await client._make_request("POST", "https://api.test.com/test")
            
            assert result == success_data
            assert mock_session.request.call_count == 2
    
    def test_extract_error_info(self, client):
        """测试错误信息提取"""
        # 标准错误格式
        error_data = {"error": {"message": "Test error", "code": "TEST_CODE"}}
        message, code = client._extract_error_info(error_data, 400)
        assert message == "Test error"
        assert code == "TEST_CODE"
        
        # 简单消息格式
        error_data = {"message": "Simple error"}
        message, code = client._extract_error_info(error_data, 400)
        assert message == "Simple error"
        assert code is None
        
        # MiniMax API 格式
        error_data = {"base_resp": {"status_msg": "API error", "status_code": 123}}
        message, code = client._extract_error_info(error_data, 400)
        assert message == "API error"
        assert code == "123"
        
        # 未知格式
        error_data = {"unknown": "format"}
        message, code = client._extract_error_info(error_data, 500)
        assert "API错误 (状态码: 500)" in message
        assert code is None
    
    def test_should_retry(self, client):
        """测试重试判断逻辑"""
        # 可重试的状态码
        retryable_codes = [429, 500, 502, 503, 504]
        for code in retryable_codes:
            assert client._should_retry(code, 0)
            assert client._should_retry(code, 1)
            assert not client._should_retry(code, 3)  # 超过最大重试次数
        
        # 不可重试的状态码
        non_retryable_codes = [400, 401, 403, 404]
        for code in non_retryable_codes:
            assert not client._should_retry(code, 0)
    
    def test_get_exception_class(self, client):
        """测试异常类选择"""
        from src.gemini_kling_mcp.services.kling.models import (
            KlingValidationError, KlingQuotaError, KlingTaskError
        )
        
        # 验证错误
        assert client._get_exception_class(400, None) == KlingValidationError
        
        # 配额错误
        assert client._get_exception_class(402, None) == KlingQuotaError
        assert client._get_exception_class(429, None) == KlingQuotaError
        
        # 任务错误
        assert client._get_exception_class(500, None) == KlingTaskError
        assert client._get_exception_class(503, None) == KlingTaskError
        
        # 默认错误
        assert client._get_exception_class(404, None) == KlingHTTPError

class TestKlingClientMethods:
    """测试 Kling 客户端方法"""
    
    @pytest.mark.asyncio
    async def test_text_to_video(self, client, sample_request):
        """测试文本生成视频"""
        mock_response_data = {"task_id": "test-123", "status": "pending"}
        
        with patch.object(client, '_make_request') as mock_make_request:
            mock_make_request.return_value = mock_response_data
            
            response = await client.text_to_video(sample_request)
            
            # 验证调用参数
            args, kwargs = mock_make_request.call_args
            assert args[0] == "POST"  # method
            assert "video_generation" in args[1]  # url
            
            # 验证请求数据
            request_data = kwargs["json_data"]
            assert request_data["prompt"] == "Test video generation"
            assert "image" not in request_data
            assert "image_url" not in request_data
            
            # 验证响应
            assert response.task_id == "test-123"
            assert response.status == KlingTaskStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_image_to_video_with_image(self, client):
        """测试图像生成视频（使用图像数据）"""
        request = KlingVideoRequest(
            prompt="Animate this image",
            image="data:image/jpeg;base64,test"
        )
        
        mock_response_data = {"task_id": "test-124", "status": "pending"}
        
        with patch.object(client, '_make_request') as mock_make_request:
            mock_make_request.return_value = mock_response_data
            
            response = await client.image_to_video(request)
            
            # 验证请求数据包含图像
            args, kwargs = mock_make_request.call_args
            request_data = kwargs["json_data"]
            assert request_data["prompt"] == "Animate this image"
            assert request_data["image"] == "data:image/jpeg;base64,test"
            
            assert response.task_id == "test-124"
    
    @pytest.mark.asyncio
    async def test_image_to_video_without_image(self, client):
        """测试图像生成视频（无图像数据）"""
        request = KlingVideoRequest(prompt="Test without image")
        
        from src.gemini_kling_mcp.services.kling.models import KlingValidationError
        
        with pytest.raises(KlingValidationError) as exc_info:
            await client.image_to_video(request)
        
        assert "图像生成视频需要提供图像数据" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_task_status(self, client):
        """测试获取任务状态"""
        mock_response_data = {
            "task_id": "test-123",
            "status": "processing",
            "task_info": {"progress": 50}
        }
        
        with patch.object(client, '_make_request') as mock_make_request:
            mock_make_request.return_value = mock_response_data
            
            response = await client.get_task_status("test-123")
            
            # 验证调用参数
            args, kwargs = mock_make_request.call_args
            assert args[0] == "GET"
            assert "query/test-123" in args[1]
            
            assert response.task_id == "test-123"
            assert response.status == KlingTaskStatus.PROCESSING
    
    @pytest.mark.asyncio
    async def test_list_tasks(self, client):
        """测试获取任务列表"""
        mock_response_data = {
            "tasks": [
                {"task_id": "task-1", "status": "completed"},
                {"task_id": "task-2", "status": "processing"}
            ]
        }
        
        with patch.object(client, '_make_request') as mock_make_request:
            mock_make_request.return_value = mock_response_data
            
            tasks = await client.list_tasks(limit=10, status=KlingTaskStatus.PROCESSING)
            
            # 验证调用参数
            args, kwargs = mock_make_request.call_args
            assert args[0] == "GET"
            assert kwargs["params"]["limit"] == 10
            assert kwargs["params"]["status"] == "processing"
            
            assert len(tasks) == 2
            assert tasks[0].task_id == "task-1"
            assert tasks[1].task_id == "task-2"
    
    @pytest.mark.asyncio
    async def test_cancel_task_success(self, client):
        """测试成功取消任务"""
        with patch.object(client, '_make_request') as mock_make_request:
            mock_make_request.return_value = {"success": True}
            
            result = await client.cancel_task("test-123")
            
            # 验证调用参数
            args, kwargs = mock_make_request.call_args
            assert args[0] == "DELETE"
            assert "query/test-123" in args[1]
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_cancel_task_not_found(self, client):
        """测试取消不存在的任务"""
        with patch.object(client, '_make_request') as mock_make_request:
            mock_make_request.side_effect = KlingHTTPError("Not found", status_code=404)
            
            result = await client.cancel_task("nonexistent")
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_cancel_task_error(self, client):
        """测试取消任务时发生其他错误"""
        with patch.object(client, '_make_request') as mock_make_request:
            mock_make_request.side_effect = KlingHTTPError("Server error", status_code=500)
            
            with pytest.raises(KlingHTTPError):
                await client.cancel_task("test-123")