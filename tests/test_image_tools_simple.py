"""
简单的图像工具测试
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

class TestImageToolsBasic:
    """基础图像工具测试"""
    
    def test_import_image_tools(self):
        """测试图像工具导入"""
        from src.gemini_kling_mcp.tools import image_tools
        
        # 验证工具函数存在
        assert hasattr(image_tools, 'generate_image')
        assert hasattr(image_tools, 'edit_image')
        assert hasattr(image_tools, 'analyze_image')
    
    @pytest.mark.asyncio
    @patch('src.gemini_kling_mcp.tools.image_tools.GeminiImageService')
    @patch('src.gemini_kling_mcp.tools.image_tools.get_config')
    @patch('src.gemini_kling_mcp.tools.image_tools.FileManager')
    async def test_generate_image_function_direct(self, mock_fm, mock_config, mock_service_class):
        """直接测试图像生成函数"""
        from src.gemini_kling_mcp.tools.image_tools import generate_image
        
        # 设置模拟
        mock_config.return_value = Mock()
        mock_fm.return_value = Mock()
        
        # 模拟图像数据
        mock_image_data = Mock()
        mock_image_data.format.value = "png"
        mock_image_data.width = 1024
        mock_image_data.height = 1024
        mock_image_data.size = 1000
        mock_image_data.checksum = "test_checksum"
        
        # 模拟响应
        mock_response = Mock()
        mock_response.images = [mock_image_data]
        mock_response.model = "gemini-2.5-flash-image-preview"
        mock_response.prompt = "Test prompt"
        mock_response.resolution = "1024x1024"
        mock_response.seed = None
        mock_response.usage = {"total_tokens": 30}
        
        # 设置服务模拟
        mock_service = Mock()
        mock_service.__aenter__ = AsyncMock(return_value=mock_service)
        mock_service.__aexit__ = AsyncMock()
        mock_service.generate_image = AsyncMock(return_value=mock_response)
        mock_service_class.return_value = mock_service
        
        # 获取底层函数并直接调用
        original_func = generate_image.__wrapped__
        
        arguments = {
            "prompt": "Generate a beautiful landscape",
            "num_images": 1,
            "resolution": "1024x1024"
        }
        
        result = await original_func(arguments)
        
        # 验证结果
        assert isinstance(result, str)
        assert "成功生成 1 张图像" in result
        assert "模型: gemini-2.5-flash-image-preview" in result
        
        # 验证调用
        mock_service.generate_image.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_image_validation_error_direct(self):
        """直接测试参数验证错误"""
        from src.gemini_kling_mcp.tools.image_tools import generate_image
        
        # 获取底层函数
        original_func = generate_image.__wrapped__
        
        # 测试缺少必需参数
        arguments = {}
        
        result = await original_func(arguments)
        
        assert isinstance(result, str)
        assert "参数错误" in result
        assert "prompt参数是必需的" in result
    
    @pytest.mark.asyncio
    async def test_generate_image_invalid_model_direct(self):
        """直接测试无效模型"""
        from src.gemini_kling_mcp.tools.image_tools import generate_image
        
        # 获取底层函数
        original_func = generate_image.__wrapped__
        
        arguments = {
            "prompt": "Test prompt",
            "model": "invalid-model"
        }
        
        result = await original_func(arguments)
        
        assert isinstance(result, str)
        assert "参数错误" in result
        assert "不支持的图像模型" in result
    
    @pytest.mark.asyncio
    @patch('src.gemini_kling_mcp.tools.image_tools.GeminiImageService')
    @patch('src.gemini_kling_mcp.tools.image_tools.get_config')
    @patch('src.gemini_kling_mcp.tools.image_tools.FileManager')
    async def test_edit_image_function_direct(self, mock_fm, mock_config, mock_service_class):
        """直接测试图像编辑函数"""
        from src.gemini_kling_mcp.tools.image_tools import edit_image
        
        # 设置模拟
        mock_config.return_value = Mock()
        mock_fm.return_value = Mock()
        
        # 模拟响应
        mock_image_data = Mock()
        mock_image_data.format.value = "png"
        mock_image_data.width = 1024
        mock_image_data.height = 1024
        mock_image_data.size = 1200
        mock_image_data.checksum = "edited_checksum"
        
        mock_response = Mock()
        mock_response.image = mock_image_data
        mock_response.model = "gemini-2.5-flash-image-preview"
        mock_response.prompt = "Edit this image"
        mock_response.edit_mode = "edit"
        mock_response.strength = 0.8
        mock_response.usage = {"total_tokens": 25}
        
        # 设置服务模拟
        mock_service = Mock()
        mock_service.__aenter__ = AsyncMock(return_value=mock_service)
        mock_service.__aexit__ = AsyncMock()
        mock_service.edit_image = AsyncMock(return_value=mock_response)
        mock_service_class.return_value = mock_service
        
        # 获取底层函数并直接调用
        original_func = edit_image.__wrapped__
        
        arguments = {
            "image_input": "base64_image_data",
            "prompt": "Make it blue"
        }
        
        result = await original_func(arguments)
        
        # 验证结果
        assert isinstance(result, str)
        assert "图像编辑完成" in result
        assert "编辑模式: edit" in result
        
        # 验证调用
        mock_service.edit_image.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('src.gemini_kling_mcp.tools.image_tools.GeminiImageService')
    @patch('src.gemini_kling_mcp.tools.image_tools.get_config')
    @patch('src.gemini_kling_mcp.tools.image_tools.FileManager')
    async def test_analyze_image_function_direct(self, mock_fm, mock_config, mock_service_class):
        """直接测试图像分析函数"""
        from src.gemini_kling_mcp.tools.image_tools import analyze_image
        
        # 设置模拟
        mock_config.return_value = Mock()
        mock_fm.return_value = Mock()
        
        # 模拟响应
        mock_response = Mock()
        mock_response.analysis = "这是一张美丽的风景照片"
        mock_response.model = "gemini-1.5-flash-002"
        mock_response.analysis_type = "general"
        mock_response.confidence = 0.95
        mock_response.usage = {"total_tokens": 15}
        mock_response.objects = None
        mock_response.text = None
        mock_response.faces = None
        mock_response.colors = None
        mock_response.tags = None
        
        # 设置服务模拟
        mock_service = Mock()
        mock_service.__aenter__ = AsyncMock(return_value=mock_service)
        mock_service.__aexit__ = AsyncMock()
        mock_service.analyze_image = AsyncMock(return_value=mock_response)
        mock_service_class.return_value = mock_service
        
        # 获取底层函数并直接调用
        original_func = analyze_image.__wrapped__
        
        arguments = {
            "image_input": "base64_image_data"
        }
        
        result = await original_func(arguments)
        
        # 验证结果
        assert isinstance(result, str)
        assert "图像分析完成" in result
        assert "分析类型: general" in result
        assert "这是一张美丽的风景照片" in result
        
        # 验证调用
        mock_service.analyze_image.assert_called_once()
    
    def test_service_import_working(self):
        """测试服务可以正常导入"""
        from src.gemini_kling_mcp.services.gemini.image_service import GeminiImageService
        from src.gemini_kling_mcp.services.gemini.models import ImageModel, ImageFormat
        
        # 验证枚举值
        assert len(list(ImageModel)) > 0
        assert len(list(ImageFormat)) > 0
        
        # 验证默认值
        default_model = ImageModel.get_default()
        assert isinstance(default_model, ImageModel)