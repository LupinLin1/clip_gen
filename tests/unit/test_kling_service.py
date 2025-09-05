"""
Kling 视频服务单元测试

测试 Kling 视频生成服务的核心功能。
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock, Mock
from typing import Dict, Any

from src.gemini_kling_mcp.services.kling.video_service import KlingVideoService
from src.gemini_kling_mcp.services.kling.models import (
    KlingVideoRequest, KlingVideoResponse, KlingVideoConfig,
    KlingModel, KlingVideoMode, KlingAspectRatio, KlingDuration,
    KlingTaskStatus, KlingTaskInfo, KlingVideoResult,
    KlingError, KlingValidationError
)
from src.gemini_kling_mcp.exceptions import ValidationError, ServiceError
from tests.test_data_generator import test_data_generator


@pytest.mark.unit
class TestKlingVideoService:
    """Kling视频服务测试类"""
    
    @pytest.fixture
    def kling_config(self):
        """Kling配置"""
        return KlingVideoConfig(
            model=KlingModel.KLING_V1,
            mode=KlingVideoMode.STD,
            aspect_ratio=KlingAspectRatio.R_16_9,
            duration=KlingDuration.DURATION_5_SEC,
            fps=24,
            cfg_scale=0.5
        )
    
    @pytest.fixture
    def mock_kling_client(self):
        """Mock Kling客户端"""
        client = AsyncMock()
        
        # Mock响应数据
        task_info = KlingTaskInfo(
            task_id="test_task_123",
            status=KlingTaskStatus.PENDING,
            progress=0,
            estimated_wait_time=30,
            created_at="2023-01-01T00:00:00Z",
            updated_at="2023-01-01T00:00:00Z"
        )
        
        video_result = KlingVideoResult(
            video_url="https://example.com/video.mp4",
            thumbnail_url="https://example.com/thumb.jpg",
            duration=5,
            width=1920,
            height=1080,
            file_size=1024000
        )
        
        response = KlingVideoResponse(
            task_id="test_task_123",
            status=KlingTaskStatus.COMPLETED,
            task_info=task_info,
            result=video_result
        )
        
        # 设置方法返回值
        client.text_to_video.return_value = response
        client.image_to_video.return_value = response
        client.get_task_status.return_value = response
        client.cancel_task.return_value = True
        client.list_tasks.return_value = [response]
        client.__aenter__.return_value = client
        client.__aexit__.return_value = None
        
        return client
    
    @pytest.fixture
    def mock_progress_tracker(self):
        """Mock进度跟踪器"""
        tracker = AsyncMock()
        tracker.track_task.return_value = AsyncMock()
        tracker.start_background_tracking.return_value = None
        tracker.stop_tracking.return_value = None
        tracker.stop_all_tracking.return_value = None
        tracker.wait_for_completion.return_value = {}
        tracker.get_tracking_status.return_value = {}
        return tracker
    
    @pytest.fixture
    def mock_video_utils(self):
        """Mock视频工具"""
        utils = AsyncMock()
        utils.validate_and_prepare_inputs.return_value = {
            "prompt": "test prompt",
            "image": None,
            "image_url": "https://example.com/image.jpg"
        }
        utils.download_video_from_url.return_value = "/tmp/video.mp4"
        return utils
    
    def test_service_initialization(self, temp_dir):
        """测试服务初始化"""
        service = KlingVideoService(
            api_key="test-key",
            base_url="https://test-api.com"
        )
        
        assert service.api_key == "test-key"
        assert service.base_url == "https://test-api.com"
        assert service._is_initialized is True
        assert service.client is not None
        assert service.progress_tracker is not None
        assert service.video_utils is not None
    
    def test_validate_config(self):
        """测试配置验证"""
        service = KlingVideoService(api_key="test-key")
        
        # 有效配置
        valid_config = KlingVideoConfig(
            model=KlingModel.KLING_V1,
            mode=KlingVideoMode.STD,
            aspect_ratio=KlingAspectRatio.R_16_9,
            duration=KlingDuration.DURATION_5_SEC,
            fps=24,
            cfg_scale=0.5
        )
        
        # 不应该抛出异常
        service._validate_config(valid_config)
        
        # 无效帧率
        invalid_config = KlingVideoConfig(
            model=KlingModel.KLING_V1,
            fps=100  # 超出范围
        )
        
        with pytest.raises(KlingValidationError, match="帧率必须在1-60之间"):
            service._validate_config(invalid_config)
        
        # 无效CFG scale
        invalid_config.fps = 24
        invalid_config.cfg_scale = 2.0
        
        with pytest.raises(KlingValidationError, match="CFG scale必须在0.0-1.0之间"):
            service._validate_config(invalid_config)
    
    @pytest.mark.asyncio
    async def test_text_to_video_success(self, mock_kling_client, mock_progress_tracker, mock_video_utils, kling_config):
        """测试文本生成视频成功"""
        with patch('src.gemini_kling_mcp.services.kling.video_service.KlingClient', return_value=mock_kling_client), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingProgressTracker', return_value=mock_progress_tracker), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingVideoUtils', return_value=mock_video_utils):
            
            service = KlingVideoService(api_key="test-key")
            
            response = await service.text_to_video(
                prompt="一只可爱的小猫在花园里玩耍",
                config=kling_config,
                motion_strength=0.8,
                loop=False,
                wait_for_completion=False
            )
            
            assert response is not None
            assert response.task_id == "test_task_123"
            assert response.status == KlingTaskStatus.COMPLETED
            
            # 验证客户端调用
            mock_kling_client.text_to_video.assert_called_once()
            call_args = mock_kling_client.text_to_video.call_args[0][0]
            assert isinstance(call_args, KlingVideoRequest)
            assert call_args.prompt == "一只可爱的小猫在花园里玩耍"
            assert call_args.config == kling_config
            assert call_args.motion_strength == 0.8
            assert call_args.loop is False
    
    @pytest.mark.asyncio
    async def test_text_to_video_with_completion_wait(self, mock_kling_client, mock_progress_tracker, mock_video_utils, kling_config):
        """测试等待任务完成的文本生成视频"""
        completed_response = KlingVideoResponse(
            task_id="test_task_123",
            status=KlingTaskStatus.COMPLETED,
            task_info=KlingTaskInfo(
                task_id="test_task_123",
                status=KlingTaskStatus.COMPLETED,
                progress=100,
                estimated_wait_time=0,
                created_at="2023-01-01T00:00:00Z",
                updated_at="2023-01-01T00:01:00Z"
            ),
            result=KlingVideoResult(
                video_url="https://example.com/completed_video.mp4",
                thumbnail_url="https://example.com/thumb.jpg",
                duration=5,
                width=1920,
                height=1080,
                file_size=2048000
            )
        )
        
        mock_progress_tracker.track_task.return_value = completed_response
        
        with patch('src.gemini_kling_mcp.services.kling.video_service.KlingClient', return_value=mock_kling_client), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingProgressTracker', return_value=mock_progress_tracker), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingVideoUtils', return_value=mock_video_utils):
            
            service = KlingVideoService(api_key="test-key")
            
            response = await service.text_to_video(
                prompt="测试视频生成",
                config=kling_config,
                wait_for_completion=True
            )
            
            assert response.status == KlingTaskStatus.COMPLETED
            assert response.task_info.progress == 100
            mock_progress_tracker.track_task.assert_called_once_with("test_task_123", None)
    
    @pytest.mark.asyncio
    async def test_text_to_video_validation_errors(self, mock_kling_client, mock_progress_tracker, mock_video_utils):
        """测试文本生成视频参数验证"""
        with patch('src.gemini_kling_mcp.services.kling.video_service.KlingClient', return_value=mock_kling_client), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingProgressTracker', return_value=mock_progress_tracker), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingVideoUtils', return_value=mock_video_utils):
            
            service = KlingVideoService(api_key="test-key")
            
            # 空提示文本
            with pytest.raises(KlingValidationError, match="提示文本不能为空"):
                await service.text_to_video(prompt="")
            
            # 无效运动强度
            with pytest.raises(KlingValidationError, match="运动强度必须在0.0-1.0之间"):
                await service.text_to_video(
                    prompt="测试",
                    motion_strength=1.5
                )
    
    @pytest.mark.asyncio
    async def test_image_to_video_success(self, mock_kling_client, mock_progress_tracker, mock_video_utils, kling_config):
        """测试图像生成视频成功"""
        with patch('src.gemini_kling_mcp.services.kling.video_service.KlingClient', return_value=mock_kling_client), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingProgressTracker', return_value=mock_progress_tracker), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingVideoUtils', return_value=mock_video_utils):
            
            service = KlingVideoService(api_key="test-key")
            
            response = await service.image_to_video(
                prompt="基于图像生成视频",
                image_url="https://example.com/image.jpg",
                config=kling_config,
                motion_strength=0.6,
                loop=True
            )
            
            assert response is not None
            assert response.task_id == "test_task_123"
            
            # 验证输入验证和准备调用
            mock_video_utils.validate_and_prepare_inputs.assert_called_once_with(
                "基于图像生成视频", None, "https://example.com/image.jpg"
            )
            
            # 验证客户端调用
            mock_kling_client.image_to_video.assert_called_once()
            call_args = mock_kling_client.image_to_video.call_args[0][0]
            assert isinstance(call_args, KlingVideoRequest)
            assert call_args.prompt == "基于图像生成视频"
            assert call_args.motion_strength == 0.6
            assert call_args.loop is True
    
    @pytest.mark.asyncio
    async def test_image_to_video_validation_errors(self, mock_kling_client, mock_progress_tracker, mock_video_utils):
        """测试图像生成视频验证错误"""
        with patch('src.gemini_kling_mcp.services.kling.video_service.KlingClient', return_value=mock_kling_client), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingProgressTracker', return_value=mock_progress_tracker), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingVideoUtils', return_value=mock_video_utils):
            
            service = KlingVideoService(api_key="test-key")
            
            # 既没有图像路径也没有URL
            with pytest.raises(KlingValidationError, match="必须提供图像文件路径或图像URL"):
                await service.image_to_video(prompt="测试")
            
            # 同时提供图像路径和URL
            with pytest.raises(KlingValidationError, match="不能同时提供图像文件路径和URL"):
                await service.image_to_video(
                    prompt="测试",
                    image_path="/path/to/image.jpg",
                    image_url="https://example.com/image.jpg"
                )
    
    @pytest.mark.asyncio
    async def test_keyframe_video_generation(self, mock_kling_client, mock_progress_tracker, mock_video_utils, kling_config):
        """测试关键帧控制视频生成"""
        keyframes = [
            {
                "time": 0,
                "image_url": "https://example.com/frame1.jpg"
            },
            {
                "time": 2.5,
                "image_url": "https://example.com/frame2.jpg"
            }
        ]
        
        with patch('src.gemini_kling_mcp.services.kling.video_service.KlingClient', return_value=mock_kling_client), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingProgressTracker', return_value=mock_progress_tracker), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingVideoUtils', return_value=mock_video_utils):
            
            service = KlingVideoService(api_key="test-key")
            
            response = await service.keyframe_video_generation(
                prompt="关键帧控制的视频",
                keyframes=keyframes,
                config=kling_config,
                motion_strength=0.7
            )
            
            assert response is not None
            assert response.task_id == "test_task_123"
            
            # 验证客户端调用
            mock_kling_client.image_to_video.assert_called_once()
            call_args = mock_kling_client.image_to_video.call_args[0][0]
            assert isinstance(call_args, KlingVideoRequest)
            assert call_args.keyframes == keyframes
            assert call_args.motion_strength == 0.7
            assert call_args.loop is False  # 关键帧控制通常不循环
    
    @pytest.mark.asyncio
    async def test_keyframe_validation_errors(self, mock_kling_client, mock_progress_tracker, mock_video_utils):
        """测试关键帧验证错误"""
        with patch('src.gemini_kling_mcp.services.kling.video_service.KlingClient', return_value=mock_kling_client), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingProgressTracker', return_value=mock_progress_tracker), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingVideoUtils', return_value=mock_video_utils):
            
            service = KlingVideoService(api_key="test-key")
            
            # 空关键帧列表
            with pytest.raises(KlingValidationError, match="关键帧列表不能为空"):
                await service.keyframe_video_generation(
                    prompt="测试",
                    keyframes=[]
                )
            
            # 无效关键帧格式
            with pytest.raises(KlingValidationError, match="关键帧 0 必须是字典格式"):
                await service.keyframe_video_generation(
                    prompt="测试",
                    keyframes=["invalid_keyframe"]
                )
            
            # 缺少时间信息
            with pytest.raises(KlingValidationError, match="关键帧 0 缺少时间信息"):
                await service.keyframe_video_generation(
                    prompt="测试",
                    keyframes=[{"image": "test.jpg"}]
                )
            
            # 缺少图像信息
            with pytest.raises(KlingValidationError, match="关键帧 0 缺少图像信息"):
                await service.keyframe_video_generation(
                    prompt="测试",
                    keyframes=[{"time": 0}]
                )
    
    @pytest.mark.asyncio
    async def test_get_task_status(self, mock_kling_client, mock_progress_tracker, mock_video_utils):
        """测试获取任务状态"""
        with patch('src.gemini_kling_mcp.services.kling.video_service.KlingClient', return_value=mock_kling_client), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingProgressTracker', return_value=mock_progress_tracker), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingVideoUtils', return_value=mock_video_utils):
            
            service = KlingVideoService(api_key="test-key")
            
            response = await service.get_task_status("test_task_123")
            
            assert response is not None
            assert response.task_id == "test_task_123"
            assert response.status == KlingTaskStatus.COMPLETED
            
            mock_kling_client.get_task_status.assert_called_once_with("test_task_123")
    
    @pytest.mark.asyncio
    async def test_cancel_task(self, mock_kling_client, mock_progress_tracker, mock_video_utils):
        """测试取消任务"""
        with patch('src.gemini_kling_mcp.services.kling.video_service.KlingClient', return_value=mock_kling_client), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingProgressTracker', return_value=mock_progress_tracker), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingVideoUtils', return_value=mock_video_utils):
            
            service = KlingVideoService(api_key="test-key")
            
            success = await service.cancel_task("test_task_123")
            
            assert success is True
            mock_kling_client.cancel_task.assert_called_once_with("test_task_123")
            mock_progress_tracker.stop_tracking.assert_called_once_with("test_task_123")
    
    @pytest.mark.asyncio
    async def test_list_tasks(self, mock_kling_client, mock_progress_tracker, mock_video_utils):
        """测试获取任务列表"""
        with patch('src.gemini_kling_mcp.services.kling.video_service.KlingClient', return_value=mock_kling_client), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingProgressTracker', return_value=mock_progress_tracker), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingVideoUtils', return_value=mock_video_utils):
            
            service = KlingVideoService(api_key="test-key")
            
            tasks = await service.list_tasks(limit=10, status=KlingTaskStatus.COMPLETED)
            
            assert len(tasks) == 1
            assert tasks[0].task_id == "test_task_123"
            
            mock_kling_client.list_tasks.assert_called_once_with(10, KlingTaskStatus.COMPLETED)
    
    @pytest.mark.asyncio
    async def test_wait_for_tasks(self, mock_kling_client, mock_progress_tracker, mock_video_utils):
        """测试等待多个任务完成"""
        task_results = {
            "task_1": KlingVideoResponse(
                task_id="task_1",
                status=KlingTaskStatus.COMPLETED,
                task_info=None,
                result=None
            ),
            "task_2": KlingVideoResponse(
                task_id="task_2",
                status=KlingTaskStatus.FAILED,
                task_info=None,
                result=None
            )
        }
        
        mock_progress_tracker.wait_for_completion.return_value = task_results
        
        with patch('src.gemini_kling_mcp.services.kling.video_service.KlingClient', return_value=mock_kling_client), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingProgressTracker', return_value=mock_progress_tracker), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingVideoUtils', return_value=mock_video_utils):
            
            service = KlingVideoService(api_key="test-key")
            
            results = await service.wait_for_tasks(["task_1", "task_2"], timeout=60)
            
            assert len(results) == 2
            assert results["task_1"].status == KlingTaskStatus.COMPLETED
            assert results["task_2"].status == KlingTaskStatus.FAILED
            
            mock_progress_tracker.wait_for_completion.assert_called_once_with(
                ["task_1", "task_2"], 60
            )
    
    @pytest.mark.asyncio
    async def test_download_video(self, mock_kling_client, mock_progress_tracker, mock_video_utils):
        """测试下载视频"""
        video_url = "https://example.com/video.mp4"
        local_path = "/tmp/downloaded_video.mp4"
        
        mock_video_utils.download_video_from_url.return_value = local_path
        
        with patch('src.gemini_kling_mcp.services.kling.video_service.KlingClient', return_value=mock_kling_client), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingProgressTracker', return_value=mock_progress_tracker), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingVideoUtils', return_value=mock_video_utils):
            
            service = KlingVideoService(api_key="test-key")
            
            downloaded_path = await service.download_video(video_url, "/tmp/custom_path.mp4")
            
            assert downloaded_path == local_path
            mock_video_utils.download_video_from_url.assert_called_once_with(
                video_url, "/tmp/custom_path.mp4"
            )
    
    @pytest.mark.asyncio
    async def test_download_video_with_file_manager(self, mock_kling_client, mock_progress_tracker, mock_video_utils):
        """测试使用文件管理器下载视频"""
        video_url = "https://example.com/video.mp4"
        local_path = "/tmp/downloaded_video.mp4"
        managed_path = "/managed/video_123.mp4"
        
        mock_video_utils.download_video_from_url.return_value = local_path
        
        # Mock文件管理器
        mock_file_manager = AsyncMock()
        mock_file_manager.save_file.return_value = managed_path
        
        with patch('src.gemini_kling_mcp.services.kling.video_service.KlingClient', return_value=mock_kling_client), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingProgressTracker', return_value=mock_progress_tracker), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingVideoUtils', return_value=mock_video_utils):
            
            service = KlingVideoService(api_key="test-key", file_manager=mock_file_manager)
            
            downloaded_path = await service.download_video(video_url)
            
            assert downloaded_path == managed_path
            mock_file_manager.save_file.assert_called_once_with(
                local_path,
                content_type="video",
                metadata={"source_url": video_url}
            )
    
    def test_get_service_info(self, mock_kling_client, mock_progress_tracker, mock_video_utils):
        """测试获取服务信息"""
        tracking_status = {
            "task_1": "running",
            "task_2": "completed"
        }
        mock_progress_tracker.get_tracking_status.return_value = tracking_status
        
        with patch('src.gemini_kling_mcp.services.kling.video_service.KlingClient', return_value=mock_kling_client), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingProgressTracker', return_value=mock_progress_tracker), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingVideoUtils', return_value=mock_video_utils):
            
            service = KlingVideoService(api_key="test-key", base_url="https://custom-api.com")
            
            info = service.get_service_info()
            
            assert info["service_name"] == "Kling Video Service"
            assert info["version"] == "0.1.0"
            assert info["api_base_url"] == "https://custom-api.com"
            assert info["is_initialized"] is True
            assert info["active_tasks"] == 2
            assert set(info["tracking_tasks"]) == {"task_1", "task_2"}
            assert "supported_models" in info
            assert "supported_modes" in info
            assert "supported_aspect_ratios" in info
            assert "supported_durations" in info
    
    @pytest.mark.asyncio
    async def test_service_context_manager(self, mock_kling_client, mock_progress_tracker, mock_video_utils):
        """测试服务上下文管理器"""
        with patch('src.gemini_kling_mcp.services.kling.video_service.KlingClient', return_value=mock_kling_client), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingProgressTracker', return_value=mock_progress_tracker), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingVideoUtils', return_value=mock_video_utils):
            
            async with KlingVideoService(api_key="test-key") as service:
                assert service is not None
                assert service._is_initialized is True
            
            # 验证清理方法被调用
            mock_progress_tracker.stop_all_tracking.assert_called_once()
            mock_kling_client.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_api_error_handling(self, mock_progress_tracker, mock_video_utils):
        """测试API错误处理"""
        # Mock一个会抛出异常的客户端
        mock_error_client = AsyncMock()
        mock_error_client.text_to_video.side_effect = Exception("API Error")
        mock_error_client.__aenter__.return_value = mock_error_client
        
        with patch('src.gemini_kling_mcp.services.kling.video_service.KlingClient', return_value=mock_error_client), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingProgressTracker', return_value=mock_progress_tracker), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingVideoUtils', return_value=mock_video_utils):
            
            service = KlingVideoService(api_key="test-key")
            
            with pytest.raises(ServiceError, match="文本生成视频失败"):
                await service.text_to_video(prompt="测试视频")
    
    @pytest.mark.asyncio
    async def test_service_close_error_handling(self, mock_progress_tracker, mock_video_utils):
        """测试服务关闭时的错误处理"""
        # Mock抛出异常的进度跟踪器
        mock_error_tracker = AsyncMock()
        mock_error_tracker.stop_all_tracking.side_effect = Exception("Tracking stop error")
        
        mock_error_client = AsyncMock()
        mock_error_client.close.side_effect = Exception("Client close error")
        mock_error_client.__aenter__.return_value = mock_error_client
        
        with patch('src.gemini_kling_mcp.services.kling.video_service.KlingClient', return_value=mock_error_client), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingProgressTracker', return_value=mock_error_tracker), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingVideoUtils', return_value=mock_video_utils):
            
            service = KlingVideoService(api_key="test-key")
            
            # 关闭服务时不应该抛出异常，应该记录错误日志
            await service.close()
    
    @pytest.mark.asyncio
    async def test_progress_callback_integration(self, mock_kling_client, mock_progress_tracker, mock_video_utils, kling_config):
        """测试进度回调集成"""
        progress_calls = []
        
        def progress_callback(task_id: str, progress: int, status: str):
            progress_calls.append((task_id, progress, status))
        
        with patch('src.gemini_kling_mcp.services.kling.video_service.KlingClient', return_value=mock_kling_client), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingProgressTracker', return_value=mock_progress_tracker), \
             patch('src.gemini_kling_mcp.services.kling.video_service.KlingVideoUtils', return_value=mock_video_utils):
            
            service = KlingVideoService(api_key="test-key")
            
            # 测试不等待完成但有进度回调
            await service.text_to_video(
                prompt="测试视频",
                config=kling_config,
                wait_for_completion=False,
                progress_callback=progress_callback
            )
            
            # 验证后台跟踪被启动
            mock_progress_tracker.start_background_tracking.assert_called_once_with(
                "test_task_123", progress_callback
            )