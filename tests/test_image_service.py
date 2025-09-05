"""
Gemini图像服务测试

测试图像生成、编辑、分析和批量处理功能。
"""

import asyncio
import base64
import io
import pytest
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from src.gemini_kling_mcp.config import GeminiConfig, get_config
from src.gemini_kling_mcp.file_manager.core import FileManager
from src.gemini_kling_mcp.services.gemini.image_service import (
    GeminiImageService, ImageServiceError
)
from src.gemini_kling_mcp.services.gemini.models import (
    ImageModel, ImageFormat, ImageResolution, ImageEditMode,
    ImageGenerationRequest, ImageGenerationResponse,
    ImageEditRequest, ImageEditResponse,
    ImageAnalysisRequest, ImageAnalysisResponse,
    ImageBatchRequest, ImageBatchResponse,
    ImageData, GeminiModel
)
from src.gemini_kling_mcp.services.gemini.client import GeminiClient
from src.gemini_kling_mcp.exceptions import ValidationError, ToolExecutionError

class TestGeminiImageService:
    """Gemini图像服务测试类"""
    
    @pytest.fixture
    def mock_config(self):
        """模拟配置"""
        config = Mock(spec=GeminiConfig)
        config.api_key = "test_api_key"
        config.base_url = "https://generativelanguage.googleapis.com"
        config.timeout = 30
        config.max_retries = 3
        return config
    
    @pytest.fixture
    def mock_file_manager(self):
        """模拟文件管理器"""
        file_manager = Mock(spec=FileManager)
        file_manager.save_output_file = AsyncMock(return_value="/tmp/test_output.png")
        return file_manager
    
    @pytest.fixture
    def sample_image_data(self):
        """样例图像数据"""
        # 创建1x1像素PNG图像数据
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
        )
        return ImageData(
            data=png_data,
            format=ImageFormat.PNG,
            width=1,
            height=1,
            size=len(png_data),
            checksum="test_checksum"
        )
    
    @pytest.fixture
    def mock_api_response(self):
        """模拟API响应"""
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "inlineData": {
                                    "mimeType": "image/png",
                                    "data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
                                }
                            }
                        ]
                    }
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 20,
                "totalTokenCount": 30
            }
        }
    
    @pytest.mark.asyncio
    async def test_image_service_initialization(self, mock_config, mock_file_manager):
        """测试图像服务初始化"""
        service = GeminiImageService(mock_config, mock_file_manager)
        
        assert service.config == mock_config
        assert service.file_manager == mock_file_manager
        assert service.client is None
        assert service.image_processor is not None
        assert service.image_codec is not None
        assert service.image_io is not None
        assert service.executor is not None
    
    @pytest.mark.asyncio
    async def test_context_manager(self, mock_config, mock_file_manager):
        """测试异步上下文管理器"""
        service = GeminiImageService(mock_config, mock_file_manager)
        
        async with service as svc:
            assert svc.client is not None
            assert isinstance(svc.client, GeminiClient)
        
        # 验证客户端已关闭（通过检查是否调用了close方法）
        assert service.executor._shutdown
    
    @pytest.mark.asyncio
    async def test_generate_image_success(self, mock_config, mock_file_manager, mock_api_response):
        """测试图像生成成功"""
        service = GeminiImageService(mock_config, mock_file_manager)
        
        # 模拟客户端
        mock_client = Mock(spec=GeminiClient)
        mock_client.generate_image = AsyncMock(return_value=mock_api_response)
        mock_client.extract_image_data = Mock(return_value=[{
            "data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
        }])
        mock_client.extract_usage_info = Mock(return_value={"total_tokens": 30})
        service.client = mock_client
        
        # 模拟_save_image_file方法
        service._save_image_file = AsyncMock(return_value=Path("/tmp/test_generated.png"))
        
        # 执行测试
        response = await service.generate_image(
            prompt="Generate a red rose",
            model=ImageModel.GEMINI_25_FLASH_IMAGE,
            num_images=1,
            resolution=ImageResolution.RESOLUTION_1024x1024,
            save_to_file=True
        )
        
        # 验证结果
        assert isinstance(response, ImageGenerationResponse)
        assert len(response.images) == 1
        assert response.model == ImageModel.GEMINI_25_FLASH_IMAGE.value
        assert response.prompt == "Generate a red rose"
        assert response.num_images == 1
        assert response.resolution == ImageResolution.RESOLUTION_1024x1024.value
        assert response.usage == {"total_tokens": 30}
        
        # 验证调用
        mock_client.generate_image.assert_called_once()
        service._save_image_file.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_image_validation_error(self, mock_config, mock_file_manager):
        """测试图像生成参数验证错误"""
        service = GeminiImageService(mock_config, mock_file_manager)
        service.client = Mock(spec=GeminiClient)
        
        # 测试空提示词
        with pytest.raises(ImageServiceError, match="图像生成失败"):
            await service.generate_image(
                prompt="",  # 空提示词
                num_images=1
            )
    
    @pytest.mark.asyncio
    async def test_edit_image_success(self, mock_config, mock_file_manager, mock_api_response, sample_image_data):
        """测试图像编辑成功"""
        service = GeminiImageService(mock_config, mock_file_manager)
        
        # 模拟客户端
        mock_client = Mock(spec=GeminiClient)
        mock_client.edit_image = AsyncMock(return_value=mock_api_response)
        mock_client.extract_image_data = Mock(return_value=[{
            "data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
        }])
        mock_client.extract_usage_info = Mock(return_value={"total_tokens": 25})
        service.client = mock_client
        
        # 模拟图像加载和保存
        service._load_image_data = AsyncMock(return_value=sample_image_data)
        service._save_image_file = AsyncMock(return_value=Path("/tmp/test_edited.png"))
        
        # 执行测试
        response = await service.edit_image(
            image_input=sample_image_data,
            prompt="Make the rose blue",
            edit_mode=ImageEditMode.EDIT,
            strength=0.8
        )
        
        # 验证结果
        assert isinstance(response, ImageEditResponse)
        assert response.model == ImageModel.get_default().value
        assert response.prompt == "Make the rose blue"
        assert response.edit_mode == ImageEditMode.EDIT.value
        assert response.strength == 0.8
        assert response.usage == {"total_tokens": 25}
        
        # 验证调用
        mock_client.edit_image.assert_called_once()
        service._save_image_file.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_analyze_image_success(self, mock_config, mock_file_manager, sample_image_data):
        """测试图像分析成功"""
        service = GeminiImageService(mock_config, mock_file_manager)
        
        # 模拟API响应
        api_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": "这是一朵美丽的红玫瑰，花瓣鲜艳，背景简洁。"
                            }
                        ]
                    }
                }
            ],
            "usageMetadata": {
                "totalTokenCount": 15
            }
        }
        
        # 模拟客户端
        mock_client = Mock(spec=GeminiClient)
        mock_client.analyze_image = AsyncMock(return_value=api_response)
        mock_client.extract_image_analysis = Mock(return_value="这是一朵美丽的红玫瑰，花瓣鲜艳，背景简洁。")
        mock_client.extract_usage_info = Mock(return_value={"total_tokens": 15})
        service.client = mock_client
        
        # 模拟图像加载
        service._load_image_data = AsyncMock(return_value=sample_image_data)
        
        # 执行测试
        response = await service.analyze_image(
            image_input=sample_image_data,
            analysis_type="general",
            language="zh"
        )
        
        # 验证结果
        assert isinstance(response, ImageAnalysisResponse)
        assert response.analysis == "这是一朵美丽的红玫瑰，花瓣鲜艳，背景简洁。"
        assert response.model == GeminiModel.get_default().value
        assert response.analysis_type == "general"
        assert response.usage == {"total_tokens": 15}
        
        # 验证调用
        mock_client.analyze_image.assert_called_once()
        service._load_image_data.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_batch_process_success(self, mock_config, mock_file_manager):
        """测试批量处理成功"""
        service = GeminiImageService(mock_config, mock_file_manager)
        service.client = Mock(spec=GeminiClient)
        
        # 创建测试请求
        requests = [
            ImageGenerationRequest(
                prompt="Generate a cat",
                model=ImageModel.GEMINI_25_FLASH_IMAGE,
                num_images=1
            ),
            ImageGenerationRequest(
                prompt="Generate a dog", 
                model=ImageModel.GEMINI_25_FLASH_IMAGE,
                num_images=1
            )
        ]
        
        # 模拟单个生成方法
        mock_response = ImageGenerationResponse(
            images=[Mock(spec=ImageData)],
            model=ImageModel.GEMINI_25_FLASH_IMAGE.value,
            prompt="Generated",
            num_images=1,
            resolution=ImageResolution.RESOLUTION_1024x1024.value
        )
        
        service.generate_image = AsyncMock(return_value=mock_response)
        
        # 执行测试
        batch_response = await service.batch_process(
            requests=requests,
            max_concurrent=2,
            timeout=60
        )
        
        # 验证结果
        assert isinstance(batch_response, ImageBatchResponse)
        assert batch_response.success_count == 2
        assert batch_response.error_count == 0
        assert len(batch_response.results) == 2
        assert batch_response.total_time > 0
        
        # 验证调用次数
        assert service.generate_image.call_count == 2
    
    @pytest.mark.asyncio
    async def test_batch_process_partial_failure(self, mock_config, mock_file_manager):
        """测试批量处理部分失败"""
        service = GeminiImageService(mock_config, mock_file_manager)
        service.client = Mock(spec=GeminiClient)
        
        # 创建测试请求
        requests = [
            ImageGenerationRequest(
                prompt="Generate success",
                model=ImageModel.GEMINI_25_FLASH_IMAGE,
                num_images=1
            ),
            ImageGenerationRequest(
                prompt="Generate failure",
                model=ImageModel.GEMINI_25_FLASH_IMAGE,
                num_images=1
            )
        ]
        
        # 模拟一个成功一个失败
        mock_success = ImageGenerationResponse(
            images=[Mock(spec=ImageData)],
            model=ImageModel.GEMINI_25_FLASH_IMAGE.value,
            prompt="Generated",
            num_images=1,
            resolution=ImageResolution.RESOLUTION_1024x1024.value
        )
        
        async def mock_generate_side_effect(*args, **kwargs):
            if "success" in kwargs.get("prompt", ""):
                return mock_success
            else:
                raise ImageServiceError("Generation failed")
        
        service.generate_image = AsyncMock(side_effect=mock_generate_side_effect)
        
        # 执行测试
        batch_response = await service.batch_process(
            requests=requests,
            max_concurrent=2,
            timeout=60
        )
        
        # 验证结果
        assert isinstance(batch_response, ImageBatchResponse)
        assert batch_response.success_count == 1
        assert batch_response.error_count == 1
        assert len(batch_response.results) == 1
        assert len(batch_response.errors) == 1
        assert batch_response.total_time > 0
    
    @pytest.mark.asyncio
    async def test_batch_process_timeout(self, mock_config, mock_file_manager):
        """测试批量处理超时"""
        service = GeminiImageService(mock_config, mock_file_manager)
        service.client = Mock(spec=GeminiClient)
        
        # 创建测试请求
        requests = [
            ImageGenerationRequest(
                prompt="Slow generation",
                model=ImageModel.GEMINI_25_FLASH_IMAGE,
                num_images=1
            )
        ]
        
        # 模拟长时间执行
        async def slow_generate(*args, **kwargs):
            await asyncio.sleep(2)  # 模拟慢操作
            return Mock(spec=ImageGenerationResponse)
        
        service.generate_image = AsyncMock(side_effect=slow_generate)
        
        # 执行测试（短超时）
        with pytest.raises(ImageServiceError, match="批量处理超时"):
            await service.batch_process(
                requests=requests,
                max_concurrent=1,
                timeout=1  # 1秒超时
            )
    
    @pytest.mark.asyncio
    async def test_load_image_data_from_path(self, mock_config, mock_file_manager, sample_image_data):
        """测试从文件路径加载图像数据"""
        service = GeminiImageService(mock_config, mock_file_manager)
        
        # 创建临时图像文件
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_file.write(sample_image_data.data)
            temp_path = Path(temp_file.name)
        
        try:
            # 模拟image_io.load_from_file
            service.image_io.load_from_file = Mock(return_value=sample_image_data)
            
            # 执行测试
            result = await service._load_image_data(temp_path)
            
            # 验证结果
            assert result == sample_image_data
            service.image_io.load_from_file.assert_called_once_with(temp_path)
            
        finally:
            # 清理临时文件
            temp_path.unlink()
    
    @pytest.mark.asyncio
    async def test_load_image_data_from_bytes(self, mock_config, mock_file_manager, sample_image_data):
        """测试从字节数据加载图像数据"""
        service = GeminiImageService(mock_config, mock_file_manager)
        
        # 模拟编码解码
        service.image_codec.encode_to_base64 = Mock(return_value="encoded_data")
        service.image_io.load_from_base64 = Mock(return_value=sample_image_data)
        
        # 执行测试
        result = await service._load_image_data(sample_image_data.data)
        
        # 验证结果
        assert result == sample_image_data
        service.image_codec.encode_to_base64.assert_called_once_with(sample_image_data.data)
        service.image_io.load_from_base64.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_load_image_data_from_image_data(self, mock_config, mock_file_manager, sample_image_data):
        """测试从ImageData对象加载图像数据"""
        service = GeminiImageService(mock_config, mock_file_manager)
        
        # 执行测试
        result = await service._load_image_data(sample_image_data)
        
        # 验证结果
        assert result == sample_image_data
    
    @pytest.mark.asyncio
    async def test_load_image_data_invalid_type(self, mock_config, mock_file_manager):
        """测试加载不支持类型的图像数据"""
        service = GeminiImageService(mock_config, mock_file_manager)
        
        # 执行测试
        with pytest.raises(ValidationError, match="不支持的图像输入类型"):
            await service._load_image_data(12345)  # 不支持的类型
    
    @pytest.mark.asyncio
    async def test_save_image_file_with_file_manager(self, mock_config, mock_file_manager, sample_image_data):
        """测试使用文件管理器保存图像文件"""
        service = GeminiImageService(mock_config, mock_file_manager)
        
        # 模拟临时文件创建
        temp_path = Path("/tmp/temp_image.png")
        service.image_io.create_temp_file = Mock(return_value=temp_path)
        
        # 执行测试
        result_path = await service._save_image_file(sample_image_data, "test_image.png")
        
        # 验证结果
        assert result_path == Path("/tmp/test_output.png")
        service.image_io.create_temp_file.assert_called_once()
        mock_file_manager.save_output_file.assert_called_once_with(
            str(temp_path), "test_image.png", overwrite=True
        )
    
    @pytest.mark.asyncio
    async def test_save_image_file_without_file_manager(self, mock_config, sample_image_data):
        """测试不使用文件管理器保存图像文件"""
        service = GeminiImageService(mock_config, None)  # 没有文件管理器
        
        # 模拟保存操作
        temp_dir = Path(tempfile.gettempdir())
        expected_path = temp_dir / "test_image.png"
        service.image_io.save_to_file = Mock(return_value=expected_path)
        
        # 执行测试
        result_path = await service._save_image_file(sample_image_data, "test_image.png")
        
        # 验证结果
        assert result_path == expected_path
        service.image_io.save_to_file.assert_called_once_with(
            sample_image_data, expected_path, overwrite=True
        )
    
    def test_get_supported_formats(self, mock_config, mock_file_manager):
        """测试获取支持的图像格式"""
        service = GeminiImageService(mock_config, mock_file_manager)
        
        formats = service.get_supported_formats()
        
        assert isinstance(formats, list)
        assert len(formats) > 0
        assert "png" in formats
        assert "jpeg" in formats
        assert "webp" in formats
    
    def test_get_supported_resolutions(self, mock_config, mock_file_manager):
        """测试获取支持的图像分辨率"""
        service = GeminiImageService(mock_config, mock_file_manager)
        
        resolutions = service.get_supported_resolutions()
        
        assert isinstance(resolutions, list)
        assert len(resolutions) > 0
        assert "1024x1024" in resolutions
        assert "512x512" in resolutions
    
    def test_get_supported_models(self, mock_config, mock_file_manager):
        """测试获取支持的图像模型"""
        service = GeminiImageService(mock_config, mock_file_manager)
        
        models = service.get_supported_models()
        
        assert isinstance(models, list)
        assert len(models) > 0
        assert ImageModel.GEMINI_25_FLASH_IMAGE.value in models
    
    def test_create_placeholder_image(self, mock_config, mock_file_manager):
        """测试创建占位符图像"""
        service = GeminiImageService(mock_config, mock_file_manager)
        
        # 执行测试
        placeholder_data = service._create_placeholder_image(256, 256)
        
        # 验证结果
        assert isinstance(placeholder_data, bytes)
        assert len(placeholder_data) > 0
        
        # 验证是有效的图像数据
        info = service.image_processor.get_image_info(placeholder_data)
        assert info["size"] > 0
    
    @pytest.mark.asyncio
    async def test_prepare_generation_request(self, mock_config, mock_file_manager):
        """测试准备图像生成API请求"""
        service = GeminiImageService(mock_config, mock_file_manager)
        
        request = ImageGenerationRequest(
            prompt="Generate a sunset",
            model=ImageModel.GEMINI_25_FLASH_IMAGE,
            num_images=2
        )
        
        api_request = service._prepare_generation_request(request)
        
        assert isinstance(api_request, dict)
        assert "contents" in api_request
        assert "generationConfig" in api_request
        assert "Generate 2 image(s) with the following description: Generate a sunset" in str(api_request["contents"])
    
    @pytest.mark.asyncio
    async def test_prepare_edit_request(self, mock_config, mock_file_manager):
        """测试准备图像编辑API请求"""
        service = GeminiImageService(mock_config, mock_file_manager)
        
        request = ImageEditRequest(
            image_data="base64_image_data",
            prompt="Edit this image",
            model=ImageModel.GEMINI_25_FLASH_IMAGE,
            edit_mode=ImageEditMode.EDIT
        )
        
        api_request = service._prepare_edit_request(request)
        
        assert isinstance(api_request, dict)
        assert "contents" in api_request
        assert "generationConfig" in api_request
        # 验证包含图像数据
        parts = api_request["contents"][0]["parts"]
        assert any("inlineData" in part for part in parts)
    
    @pytest.mark.asyncio
    async def test_prepare_analysis_request(self, mock_config, mock_file_manager):
        """测试准备图像分析API请求"""
        service = GeminiImageService(mock_config, mock_file_manager)
        
        request = ImageAnalysisRequest(
            image_data="base64_image_data",
            model=GeminiModel.GEMINI_15_FLASH,
            analysis_type="detailed",
            prompt="Describe this image"
        )
        
        api_request = service._prepare_analysis_request(request)
        
        assert isinstance(api_request, dict)
        assert "contents" in api_request
        assert "generationConfig" in api_request
        # 验证包含分析提示和图像数据
        parts = api_request["contents"][0]["parts"]
        assert any("text" in part for part in parts)
        assert any("inlineData" in part for part in parts)

@pytest.mark.asyncio
async def test_create_image_service():
    """测试创建图像服务实例的便捷函数"""
    from src.gemini_kling_mcp.services.gemini.image_service import create_image_service
    
    mock_config = Mock()
    mock_file_manager = Mock()
    
    service = await create_image_service(mock_config, mock_file_manager)
    
    assert isinstance(service, GeminiImageService)
    assert service.config == mock_config
    assert service.file_manager == mock_file_manager

class TestImageServiceIntegration:
    """图像服务集成测试"""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_image_generation_workflow(self):
        """测试完整的图像生成工作流"""
        # 使用实际配置（如果可用）
        try:
            config = get_config()
            if not config.api_key:
                pytest.skip("需要API密钥进行集成测试")
        except:
            pytest.skip("配置不可用，跳过集成测试")
        
        # 创建服务并执行真实的图像生成
        async with GeminiImageService(config) as service:
            response = await service.generate_image(
                prompt="A simple test image for integration testing",
                num_images=1,
                resolution=ImageResolution.RESOLUTION_256x256,
                save_to_file=False
            )
            
            # 验证响应
            assert isinstance(response, ImageGenerationResponse)
            assert len(response.images) == 1
            assert response.images[0].size > 0
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_image_analysis_workflow(self):
        """测试完整的图像分析工作流"""
        try:
            config = get_config()
            if not config.api_key:
                pytest.skip("需要API密钥进行集成测试")
        except:
            pytest.skip("配置不可用，跳过集成测试")
        
        # 创建测试图像
        test_image_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
        )
        
        # 执行图像分析
        async with GeminiImageService(config) as service:
            response = await service.analyze_image(
                image_input=test_image_data,
                analysis_type="general",
                language="zh"
            )
            
            # 验证响应
            assert isinstance(response, ImageAnalysisResponse)
            assert len(response.analysis) > 0
            assert response.analysis_type == "general"