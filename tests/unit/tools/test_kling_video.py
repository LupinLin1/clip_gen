"""
测试 Kling 视频生成 MCP 工具
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from src.gemini_kling_mcp.tools.kling_video import KlingVideoTools
from src.gemini_kling_mcp.config import Config, KlingConfig, ServerConfig, GeminiConfig, FileConfig
from src.gemini_kling_mcp.exceptions import ConfigurationError
from src.gemini_kling_mcp.services.kling import (
    KlingVideoResponse,
    KlingTaskStatus,
    KlingVideoResult
)

@pytest.fixture
def config_with_kling():
    """创建包含 Kling 配置的配置对象"""
    return Config(
        server=ServerConfig(),
        gemini=GeminiConfig(api_key="test-gemini-key"),
        kling=KlingConfig(api_key="test-kling-key"),
        file=FileConfig()
    )

@pytest.fixture
def config_without_kling():
    """创建不包含 Kling 配置的配置对象"""
    return Config(
        server=ServerConfig(),
        gemini=GeminiConfig(api_key="test-gemini-key"),
        kling=None,
        file=FileConfig()
    )

class TestKlingVideoTools:
    """测试 Kling 视频工具"""
    
    def test_init_with_kling_config(self, config_with_kling):
        """测试使用 Kling 配置初始化"""
        tools = KlingVideoTools(config_with_kling)
        
        assert tools.config is config_with_kling
        assert tools.service is None  # 延迟初始化
    
    def test_init_without_kling_config(self, config_without_kling):
        """测试没有 Kling 配置时初始化失败"""
        with pytest.raises(ConfigurationError) as exc_info:
            KlingVideoTools(config_without_kling)
        
        assert "Kling 配置未找到" in str(exc_info.value)
    
    def test_init_without_api_key(self):
        """测试没有 API 密钥时初始化失败"""
        config = Config(
            server=ServerConfig(),
            gemini=GeminiConfig(api_key="test-key"),
            kling=KlingConfig(api_key=""),  # 空的 API 密钥
            file=FileConfig()
        )
        
        with pytest.raises(ConfigurationError) as exc_info:
            KlingVideoTools(config)
        
        assert "Kling API 密钥未配置" in str(exc_info.value)
    
    def test_get_tools(self, config_with_kling):
        """测试获取工具列表"""
        tools = KlingVideoTools(config_with_kling)
        tool_list = tools.get_tools()
        
        # 验证工具数量
        assert len(tool_list) == 8
        
        # 验证工具名称
        tool_names = [tool.name for tool in tool_list]
        expected_tools = [
            "kling_text_to_video",
            "kling_image_to_video", 
            "kling_get_task_status",
            "kling_list_tasks",
            "kling_cancel_task",
            "kling_download_video",
            "kling_wait_for_tasks",
            "kling_service_info"
        ]
        
        for expected in expected_tools:
            assert expected in tool_names
    
    def test_text_to_video_tool_schema(self, config_with_kling):
        """测试文本生成视频工具的模式"""
        tools = KlingVideoTools(config_with_kling)
        tool_list = tools.get_tools()
        
        text_to_video_tool = next(
            tool for tool in tool_list if tool.name == "kling_text_to_video"
        )
        
        schema = text_to_video_tool.inputSchema
        properties = schema["properties"]
        
        # 验证必需参数
        assert "prompt" in schema["required"]
        assert properties["prompt"]["type"] == "string"
        
        # 验证可选参数
        optional_params = [
            "model", "mode", "aspect_ratio", "duration", 
            "fps", "motion_strength", "cfg_scale", "negative_prompt",
            "loop", "seed", "wait_for_completion"
        ]
        
        for param in optional_params:
            assert param in properties
        
        # 验证枚举值
        assert "kling-v1" in properties["model"]["enum"]
        assert "standard" in properties["mode"]["enum"] 
        assert "16:9" in properties["aspect_ratio"]["enum"]
        assert "5s" in properties["duration"]["enum"]
    
    def test_image_to_video_tool_schema(self, config_with_kling):
        """测试图像生成视频工具的模式"""
        tools = KlingVideoTools(config_with_kling)
        tool_list = tools.get_tools()
        
        image_to_video_tool = next(
            tool for tool in tool_list if tool.name == "kling_image_to_video"
        )
        
        schema = image_to_video_tool.inputSchema
        properties = schema["properties"]
        
        # 验证必需参数
        assert "prompt" in schema["required"]
        
        # 验证图像输入参数
        assert "image_path" in properties
        assert "image_url" in properties
        assert properties["image_path"]["type"] == "string"
        assert properties["image_url"]["type"] == "string"
    
    @pytest.mark.asyncio
    async def test_get_service(self, config_with_kling):
        """测试获取服务实例"""
        tools = KlingVideoTools(config_with_kling)
        
        with patch('src.gemini_kling_mcp.tools.kling_video.KlingVideoService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.__aenter__ = AsyncMock(return_value=mock_service)
            mock_service_class.return_value = mock_service
            
            service = await tools._get_service()
            
            assert service is mock_service
            assert tools.service is mock_service
            
            # 验证服务初始化参数
            mock_service_class.assert_called_once_with(
                api_key="test-kling-key",
                base_url="https://api.klingai.com",
                file_manager=None
            )
    
    @pytest.mark.asyncio
    async def test_close(self, config_with_kling):
        """测试关闭工具"""
        tools = KlingVideoTools(config_with_kling)
        
        # 模拟服务
        mock_service = AsyncMock()
        tools.service = mock_service
        
        await tools.close()
        
        mock_service.close.assert_called_once()
        assert tools.service is None

class TestKlingVideoToolHandlers:
    """测试 Kling 视频工具处理器"""
    
    @pytest.fixture
    def tools_with_mock_service(self, config_with_kling):
        """创建带模拟服务的工具"""
        tools = KlingVideoTools(config_with_kling)
        mock_service = AsyncMock()
        tools.service = mock_service
        return tools, mock_service
    
    @pytest.mark.asyncio
    async def test_handle_text_to_video(self, tools_with_mock_service):
        """测试处理文本生成视频"""
        tools, mock_service = tools_with_mock_service
        
        # 模拟服务响应
        mock_response = KlingVideoResponse(
            task_id="test-123",
            status=KlingTaskStatus.PENDING
        )
        mock_service.text_to_video = AsyncMock(return_value=mock_response)
        
        # 准备参数
        args = {
            "prompt": "A beautiful sunset",
            "model": "kling-v1-5",
            "mode": "pro",
            "aspect_ratio": "16:9",
            "duration": "10s",
            "wait_for_completion": False
        }
        
        result = await tools.handle_tool_call("kling_text_to_video", args)
        
        # 验证结果
        assert result["success"] is True
        assert result["task_id"] == "test-123"
        assert result["status"] == "pending"
        
        # 验证服务调用
        mock_service.text_to_video.assert_called_once()
        call_args = mock_service.text_to_video.call_args
        
        # 验证传递的参数
        assert call_args.kwargs["prompt"] == "A beautiful sunset"
        assert call_args.kwargs["wait_for_completion"] is False
        
        # 验证配置
        config = call_args.kwargs["config"]
        assert config.model.value == "kling-v1-5"
        assert config.mode.value == "pro"
        assert config.aspect_ratio.value == "16:9"
        assert config.duration.value == "10s"
    
    @pytest.mark.asyncio
    async def test_handle_image_to_video(self, tools_with_mock_service):
        """测试处理图像生成视频"""
        tools, mock_service = tools_with_mock_service
        
        # 模拟服务响应
        mock_response = KlingVideoResponse(
            task_id="test-124",
            status=KlingTaskStatus.PROCESSING
        )
        mock_service.image_to_video = AsyncMock(return_value=mock_response)
        
        # 准备参数
        args = {
            "prompt": "Animate this image",
            "image_path": "/path/to/image.jpg",
            "model": "kling-pro"
        }
        
        result = await tools.handle_tool_call("kling_image_to_video", args)
        
        # 验证结果
        assert result["success"] is True
        assert result["task_id"] == "test-124"
        assert result["status"] == "processing"
        
        # 验证服务调用
        mock_service.image_to_video.assert_called_once()
        call_args = mock_service.image_to_video.call_args
        assert call_args.kwargs["prompt"] == "Animate this image"
        assert call_args.kwargs["image_path"] == "/path/to/image.jpg"
    
    @pytest.mark.asyncio
    async def test_handle_get_task_status(self, tools_with_mock_service):
        """测试处理获取任务状态"""
        tools, mock_service = tools_with_mock_service
        
        # 模拟服务响应
        mock_response = KlingVideoResponse(
            task_id="test-123",
            status=KlingTaskStatus.COMPLETED,
            result=KlingVideoResult(video_url="https://example.com/video.mp4")
        )
        mock_service.get_task_status = AsyncMock(return_value=mock_response)
        
        args = {"task_id": "test-123"}
        
        result = await tools.handle_tool_call("kling_get_task_status", args)
        
        # 验证结果
        assert result["success"] is True
        assert result["task_id"] == "test-123"
        assert result["status"] == "completed"
        assert result["result"]["video_url"] == "https://example.com/video.mp4"
        
        # 验证服务调用
        mock_service.get_task_status.assert_called_once_with("test-123")
    
    @pytest.mark.asyncio
    async def test_handle_list_tasks(self, tools_with_mock_service):
        """测试处理获取任务列表"""
        tools, mock_service = tools_with_mock_service
        
        # 模拟服务响应
        mock_tasks = [
            KlingVideoResponse(task_id="task-1", status=KlingTaskStatus.COMPLETED),
            KlingVideoResponse(task_id="task-2", status=KlingTaskStatus.PROCESSING)
        ]
        mock_service.list_tasks = AsyncMock(return_value=mock_tasks)
        
        args = {"limit": 10, "status": "processing"}
        
        result = await tools.handle_tool_call("kling_list_tasks", args)
        
        # 验证结果
        assert result["success"] is True
        assert len(result["tasks"]) == 2
        assert result["tasks"][0]["task_id"] == "task-1"
        assert result["tasks"][1]["task_id"] == "task-2"
        
        # 验证服务调用
        mock_service.list_tasks.assert_called_once()
        call_args = mock_service.list_tasks.call_args
        assert call_args.kwargs["limit"] == 10
        assert call_args.kwargs["status"].value == "processing"
    
    @pytest.mark.asyncio
    async def test_handle_cancel_task(self, tools_with_mock_service):
        """测试处理取消任务"""
        tools, mock_service = tools_with_mock_service
        
        mock_service.cancel_task = AsyncMock(return_value=True)
        
        args = {"task_id": "test-123"}
        
        result = await tools.handle_tool_call("kling_cancel_task", args)
        
        # 验证结果
        assert result["success"] is True
        assert result["task_id"] == "test-123"
        assert "任务已取消" in result["message"]
        
        # 验证服务调用
        mock_service.cancel_task.assert_called_once_with("test-123")
    
    @pytest.mark.asyncio
    async def test_handle_download_video(self, tools_with_mock_service):
        """测试处理下载视频"""
        tools, mock_service = tools_with_mock_service
        
        mock_service.download_video = AsyncMock(return_value="/path/to/local/video.mp4")
        
        args = {
            "video_url": "https://example.com/video.mp4",
            "save_path": "/custom/path/video.mp4"
        }
        
        result = await tools.handle_tool_call("kling_download_video", args)
        
        # 验证结果
        assert result["success"] is True
        assert result["video_url"] == "https://example.com/video.mp4"
        assert result["local_path"] == "/path/to/local/video.mp4"
        
        # 验证服务调用
        mock_service.download_video.assert_called_once_with(
            video_url="https://example.com/video.mp4",
            save_path="/custom/path/video.mp4"
        )
    
    @pytest.mark.asyncio
    async def test_handle_wait_for_tasks(self, tools_with_mock_service):
        """测试处理等待任务完成"""
        tools, mock_service = tools_with_mock_service
        
        # 模拟服务响应
        mock_results = {
            "task-1": KlingVideoResponse(
                task_id="task-1", 
                status=KlingTaskStatus.COMPLETED,
                result=KlingVideoResult(video_url="https://example.com/video1.mp4")
            ),
            "task-2": KlingVideoResponse(
                task_id="task-2", 
                status=KlingTaskStatus.FAILED
            )
        }
        mock_service.wait_for_tasks = AsyncMock(return_value=mock_results)
        
        args = {
            "task_ids": ["task-1", "task-2"],
            "timeout": 1800
        }
        
        result = await tools.handle_tool_call("kling_wait_for_tasks", args)
        
        # 验证结果
        assert result["success"] is True
        assert len(result["results"]) == 2
        assert result["results"]["task-1"]["status"] == "completed"
        assert result["results"]["task-2"]["status"] == "failed"
        assert result["summary"]["total"] == 2
        assert result["summary"]["completed"] == 1
        assert result["summary"]["failed"] == 1
        
        # 验证服务调用
        mock_service.wait_for_tasks.assert_called_once_with(
            task_ids=["task-1", "task-2"],
            timeout=1800
        )
    
    @pytest.mark.asyncio
    async def test_handle_service_info(self, tools_with_mock_service):
        """测试处理获取服务信息"""
        tools, mock_service = tools_with_mock_service
        
        mock_info = {
            "service_name": "Kling Video Service",
            "version": "0.1.0",
            "active_tasks": 2,
            "tracking_tasks": ["task-1", "task-2"]
        }
        mock_service.get_service_info = Mock(return_value=mock_info)
        
        result = await tools.handle_tool_call("kling_service_info", {})
        
        # 验证结果
        assert result["success"] is True
        assert result["service_name"] == "Kling Video Service"
        assert result["version"] == "0.1.0"
        assert result["active_tasks"] == 2
        
        # 验证服务调用
        mock_service.get_service_info.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_tool_call_error(self, tools_with_mock_service):
        """测试工具调用错误处理"""
        tools, mock_service = tools_with_mock_service
        
        # 模拟服务抛出异常
        mock_service.text_to_video = AsyncMock(side_effect=Exception("Service error"))
        
        args = {"prompt": "Test prompt"}
        
        result = await tools.handle_tool_call("kling_text_to_video", args)
        
        # 验证错误处理
        assert result["success"] is False
        assert "Service error" in result["error"]
        assert result["tool_name"] == "kling_text_to_video"
    
    @pytest.mark.asyncio
    async def test_handle_unknown_tool(self, tools_with_mock_service):
        """测试未知工具调用"""
        tools, mock_service = tools_with_mock_service
        
        result = await tools.handle_tool_call("unknown_tool", {})
        
        # 验证错误处理
        assert result["success"] is False
        assert "未知工具" in result["error"]
        assert result["tool_name"] == "unknown_tool"

class TestKlingVideoToolsIntegration:
    """测试 Kling 视频工具集成"""
    
    @pytest.mark.asyncio
    async def test_full_service_lifecycle(self, config_with_kling):
        """测试完整的服务生命周期"""
        tools = KlingVideoTools(config_with_kling)
        
        with patch('src.gemini_kling_mcp.tools.kling_video.KlingVideoService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.__aenter__ = AsyncMock(return_value=mock_service)
            mock_service.close = AsyncMock()
            mock_service_class.return_value = mock_service
            
            # 获取服务
            service1 = await tools._get_service()
            service2 = await tools._get_service()  # 应该返回相同实例
            
            assert service1 is service2
            assert service1 is mock_service
            
            # 关闭服务
            await tools.close()
            
            mock_service.close.assert_called_once()
            assert tools.service is None