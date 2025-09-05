"""
测试 Kling 模型定义
"""

import pytest
from datetime import datetime
from src.gemini_kling_mcp.services.kling.models import (
    KlingModel,
    KlingVideoMode, 
    KlingAspectRatio,
    KlingDuration,
    KlingTaskStatus,
    KlingVideoConfig,
    KlingVideoRequest,
    KlingVideoResponse,
    KlingTaskInfo,
    KlingVideoResult,
    KlingError,
    KlingValidationError,
    KlingTaskError,
    KlingQuotaError
)

class TestKlingEnums:
    """测试 Kling 枚举类型"""
    
    def test_kling_model_values(self):
        """测试 Kling 模型枚举值"""
        assert KlingModel.KLING_V1.value == "kling-v1"
        assert KlingModel.KLING_V1_5.value == "kling-v1-5"
        assert KlingModel.KLING_PRO.value == "kling-pro"
    
    def test_video_mode_values(self):
        """测试视频模式枚举值"""
        assert KlingVideoMode.STANDARD.value == "standard"
        assert KlingVideoMode.PRO.value == "pro"
        assert KlingVideoMode.ULTRA.value == "ultra"
    
    def test_aspect_ratio_values(self):
        """测试宽高比枚举值"""
        assert KlingAspectRatio.SQUARE.value == "1:1"
        assert KlingAspectRatio.PORTRAIT.value == "9:16"
        assert KlingAspectRatio.LANDSCAPE.value == "16:9"
        assert KlingAspectRatio.CINEMA.value == "21:9"
        assert KlingAspectRatio.VERTICAL.value == "3:4"
        assert KlingAspectRatio.HORIZONTAL.value == "4:3"
    
    def test_duration_values(self):
        """测试时长枚举值"""
        assert KlingDuration.SHORT.value == "5s"
        assert KlingDuration.MEDIUM.value == "10s"
        assert KlingDuration.LONG.value == "15s"
    
    def test_task_status_values(self):
        """测试任务状态枚举值"""
        assert KlingTaskStatus.PENDING.value == "pending"
        assert KlingTaskStatus.PROCESSING.value == "processing"
        assert KlingTaskStatus.COMPLETED.value == "completed"
        assert KlingTaskStatus.FAILED.value == "failed"
        assert KlingTaskStatus.CANCELLED.value == "cancelled"

class TestKlingVideoConfig:
    """测试 Kling 视频配置"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = KlingVideoConfig()
        
        assert config.model == KlingModel.KLING_V1_5
        assert config.mode == KlingVideoMode.STANDARD
        assert config.aspect_ratio == KlingAspectRatio.LANDSCAPE
        assert config.duration == KlingDuration.SHORT
        assert config.fps == 25
        assert config.cfg_scale == 0.5
        assert config.negative_prompt is None
        assert config.seed is None
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = KlingVideoConfig(
            model=KlingModel.KLING_PRO,
            mode=KlingVideoMode.PRO,
            aspect_ratio=KlingAspectRatio.PORTRAIT,
            duration=KlingDuration.MEDIUM,
            fps=30,
            cfg_scale=0.8,
            negative_prompt="low quality",
            seed=12345
        )
        
        assert config.model == KlingModel.KLING_PRO
        assert config.mode == KlingVideoMode.PRO
        assert config.aspect_ratio == KlingAspectRatio.PORTRAIT
        assert config.duration == KlingDuration.MEDIUM
        assert config.fps == 30
        assert config.cfg_scale == 0.8
        assert config.negative_prompt == "low quality"
        assert config.seed == 12345

class TestKlingVideoRequest:
    """测试 Kling 视频请求"""
    
    def test_basic_request(self):
        """测试基础请求"""
        request = KlingVideoRequest(prompt="A beautiful sunset")
        
        assert request.prompt == "A beautiful sunset"
        assert request.config.model == KlingModel.KLING_V1_5
        assert request.image is None
        assert request.image_url is None
        assert request.keyframes is None
        assert request.motion_strength == 0.8
        assert request.loop is False
    
    def test_request_with_image(self):
        """测试包含图像的请求"""
        request = KlingVideoRequest(
            prompt="Animate this image",
            image="data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQ..."
        )
        
        assert request.prompt == "Animate this image"
        assert request.image == "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQ..."
    
    def test_request_with_image_url(self):
        """测试包含图像URL的请求"""
        request = KlingVideoRequest(
            prompt="Animate this image",
            image_url="https://example.com/image.jpg"
        )
        
        assert request.prompt == "Animate this image"
        assert request.image_url == "https://example.com/image.jpg"
    
    def test_request_with_keyframes(self):
        """测试包含关键帧的请求"""
        keyframes = [
            {"time": 0, "image": "data:image/jpeg;base64,abc"},
            {"time": 5, "image": "data:image/jpeg;base64,def"}
        ]
        
        request = KlingVideoRequest(
            prompt="Video with keyframes",
            keyframes=keyframes
        )
        
        assert request.prompt == "Video with keyframes"
        assert request.keyframes == keyframes
    
    def test_to_dict_basic(self):
        """测试转换为字典格式（基础）"""
        request = KlingVideoRequest(prompt="Test video")
        data = request.to_dict()
        
        expected_keys = {
            "prompt", "model", "mode", "aspect_ratio", "duration", 
            "fps", "cfg_scale", "motion_strength", "loop"
        }
        assert set(data.keys()) == expected_keys
        
        assert data["prompt"] == "Test video"
        assert data["model"] == "kling-v1-5"
        assert data["mode"] == "standard"
        assert data["aspect_ratio"] == "16:9"
        assert data["duration"] == "5s"
        assert data["fps"] == 25
        assert data["cfg_scale"] == 0.5
        assert data["motion_strength"] == 0.8
        assert data["loop"] is False
    
    def test_to_dict_with_optional_fields(self):
        """测试转换为字典格式（包含可选字段）"""
        config = KlingVideoConfig(
            negative_prompt="bad quality",
            seed=42
        )
        
        request = KlingVideoRequest(
            prompt="Test video",
            config=config,
            image="data:image/jpeg;base64,test",
            image_url="https://example.com/test.jpg",
            keyframes=[{"time": 0, "image": "test"}]
        )
        
        data = request.to_dict()
        
        assert "negative_prompt" in data
        assert data["negative_prompt"] == "bad quality"
        assert "seed" in data
        assert data["seed"] == 42
        assert "image" in data
        assert data["image"] == "data:image/jpeg;base64,test"
        assert "image_url" in data
        assert data["image_url"] == "https://example.com/test.jpg"
        assert "keyframes" in data
        assert data["keyframes"] == [{"time": 0, "image": "test"}]

class TestKlingTaskInfo:
    """测试任务信息"""
    
    def test_task_info_creation(self):
        """测试任务信息创建"""
        now = datetime.now()
        
        task_info = KlingTaskInfo(
            task_id="test-123",
            status=KlingTaskStatus.PROCESSING,
            progress=50,
            created_at=now,
            updated_at=now,
            estimated_time=120,
            error_message=None
        )
        
        assert task_info.task_id == "test-123"
        assert task_info.status == KlingTaskStatus.PROCESSING
        assert task_info.progress == 50
        assert task_info.created_at == now
        assert task_info.updated_at == now
        assert task_info.estimated_time == 120
        assert task_info.error_message is None

class TestKlingVideoResult:
    """测试视频结果"""
    
    def test_video_result_creation(self):
        """测试视频结果创建"""
        result = KlingVideoResult(
            video_url="https://example.com/video.mp4",
            thumbnail_url="https://example.com/thumbnail.jpg",
            duration=10.5,
            width=1920,
            height=1080,
            file_size=1024*1024,
            format="mp4"
        )
        
        assert result.video_url == "https://example.com/video.mp4"
        assert result.thumbnail_url == "https://example.com/thumbnail.jpg"
        assert result.duration == 10.5
        assert result.width == 1920
        assert result.height == 1080
        assert result.file_size == 1024*1024
        assert result.format == "mp4"

class TestKlingVideoResponse:
    """测试 Kling 视频响应"""
    
    def test_from_api_response_basic(self):
        """测试从API响应创建基础响应"""
        api_data = {
            "task_id": "test-123",
            "status": "pending"
        }
        
        response = KlingVideoResponse.from_api_response(api_data)
        
        assert response.task_id == "test-123"
        assert response.status == KlingTaskStatus.PENDING
        assert response.result is None
        assert response.task_info is None
        assert response.usage is None
    
    def test_from_api_response_with_task_info(self):
        """测试从API响应创建包含任务信息的响应"""
        api_data = {
            "task_id": "test-123",
            "status": "processing",
            "task_info": {
                "progress": 75,
                "created_at": "2024-01-01T12:00:00Z",
                "updated_at": "2024-01-01T12:30:00Z",
                "estimated_time": 60
            }
        }
        
        response = KlingVideoResponse.from_api_response(api_data)
        
        assert response.task_id == "test-123"
        assert response.status == KlingTaskStatus.PROCESSING
        assert response.task_info is not None
        assert response.task_info.progress == 75
        assert response.task_info.estimated_time == 60
    
    def test_from_api_response_completed_with_result(self):
        """测试从API响应创建已完成的响应"""
        api_data = {
            "task_id": "test-123",
            "status": "completed",
            "result": {
                "video_url": "https://example.com/video.mp4",
                "thumbnail_url": "https://example.com/thumb.jpg",
                "duration": 10.0,
                "width": 1920,
                "height": 1080,
                "file_size": 2048000,
                "format": "mp4"
            }
        }
        
        response = KlingVideoResponse.from_api_response(api_data)
        
        assert response.task_id == "test-123"
        assert response.status == KlingTaskStatus.COMPLETED
        assert response.result is not None
        assert response.result.video_url == "https://example.com/video.mp4"
        assert response.result.duration == 10.0
        assert response.result.width == 1920
        assert response.result.height == 1080
    
    def test_from_api_response_invalid_status(self):
        """测试从API响应创建无效状态响应"""
        api_data = {
            "task_id": "test-123",
            "status": "invalid_status"
        }
        
        response = KlingVideoResponse.from_api_response(api_data)
        
        # 无效状态应该默认为 PENDING
        assert response.status == KlingTaskStatus.PENDING
    
    def test_to_dict(self):
        """测试转换为字典格式"""
        response = KlingVideoResponse(
            task_id="test-123",
            status=KlingTaskStatus.COMPLETED,
            result=KlingVideoResult(
                video_url="https://example.com/video.mp4",
                duration=10.0
            )
        )
        
        data = response.to_dict()
        
        assert data["task_id"] == "test-123"
        assert data["status"] == "completed"
        assert "result" in data
        assert data["result"]["video_url"] == "https://example.com/video.mp4"
        assert data["result"]["duration"] == 10.0
    
    def test_parse_datetime_formats(self):
        """测试日期时间解析"""
        # 测试不同的日期时间格式
        formats = [
            "2024-01-01T12:00:00.123Z",
            "2024-01-01T12:00:00Z",
            "2024-01-01 12:00:00"
        ]
        
        for dt_str in formats:
            dt = KlingVideoResponse._parse_datetime(dt_str)
            assert dt is not None
            assert isinstance(dt, datetime)
        
        # 测试无效格式
        assert KlingVideoResponse._parse_datetime("invalid") is None
        assert KlingVideoResponse._parse_datetime(None) is None

class TestKlingErrors:
    """测试 Kling 错误类型"""
    
    def test_kling_error_basic(self):
        """测试基础 Kling 错误"""
        error = KlingError("Test error")
        
        assert str(error) == "Test error"
        assert error.error_code is None
        assert error.details == {}
    
    def test_kling_error_with_details(self):
        """测试包含详细信息的 Kling 错误"""
        error = KlingError(
            "Test error", 
            error_code="TEST_ERROR",
            param="test_param",
            value="test_value"
        )
        
        assert str(error) == "Test error"
        assert error.error_code == "TEST_ERROR"
        assert error.details["param"] == "test_param"
        assert error.details["value"] == "test_value"
    
    def test_validation_error(self):
        """测试验证错误"""
        error = KlingValidationError("Invalid parameter")
        
        assert isinstance(error, KlingError)
        assert str(error) == "Invalid parameter"
    
    def test_task_error(self):
        """测试任务错误"""
        error = KlingTaskError("Task failed")
        
        assert isinstance(error, KlingError)
        assert str(error) == "Task failed"
    
    def test_quota_error(self):
        """测试配额错误"""
        error = KlingQuotaError("Quota exceeded")
        
        assert isinstance(error, KlingError)
        assert str(error) == "Quota exceeded"