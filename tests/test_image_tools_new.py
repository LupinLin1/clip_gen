"""
测试新的图像工具函数
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

class TestImageTools:
    """图像工具测试"""
    
    @pytest.mark.asyncio
    @patch('src.gemini_kling_mcp.tools.image_tools.get_config')
    @patch('src.gemini_kling_mcp.tools.image_tools.FileManager')
    @patch('src.gemini_kling_mcp.tools.image_tools.GeminiImageService')
    async def test_generate_image_success(self, mock_service_class, mock_file_manager, mock_config):
        """测试图像生成成功"""
        # 设置模拟
        mock_config.return_value = Mock()
        mock_file_manager.return_value = Mock()
        
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
        
        # 执行测试
        arguments = {
            "prompt": "Generate a beautiful landscape",
            "num_images": 1,
            "resolution": "1024x1024"
        }
        
        result = await generate_image(arguments)
        
        # 验证结果
        assert isinstance(result, str)
        assert "成功生成 1 张图像" in result
        assert "模型: gemini-2.5-flash-image-preview" in result
        assert "分辨率: 1024x1024" in result
        
        # 验证调用
        mock_service.generate_image.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_image_validation_error(self):
        """测试图像生成参数验证错误"""
        # 测试缺少必需参数
        arguments = {}
        
        result = await generate_image(arguments)
        
        assert isinstance(result, str)
        assert "参数错误" in result
        assert "prompt参数是必需的" in result
    
    @pytest.mark.asyncio
    async def test_generate_image_invalid_model(self):
        """测试不支持的模型"""
        arguments = {
            "prompt": "Test prompt",
            "model": "invalid-model"
        }
        
        result = await generate_image(arguments)
        
        assert isinstance(result, str)
        assert "参数错误" in result
        assert "不支持的图像模型" in result
    
    @pytest.mark.asyncio
    @patch('src.gemini_kling_mcp.tools.image_tools.get_config')
    @patch('src.gemini_kling_mcp.tools.image_tools.FileManager')
    @patch('src.gemini_kling_mcp.tools.image_tools.GeminiImageService')
    async def test_edit_image_success(self, mock_service_class, mock_file_manager, mock_config):
        """测试图像编辑成功"""
        # 设置模拟
        mock_config.return_value = Mock()
        mock_file_manager.return_value = Mock()
        
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
        
        # 执行测试
        arguments = {
            "image_input": "base64_image_data",
            "prompt": "Make it blue"
        }
        
        result = await edit_image(arguments)
        
        # 验证结果
        assert isinstance(result, str)
        assert "图像编辑完成" in result
        assert "编辑模式: edit" in result
        
        # 验证调用
        mock_service.edit_image.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_edit_image_missing_params(self):
        """测试图像编辑缺少参数"""
        arguments = {
            "image_input": "base64_data"
            # 缺少prompt
        }
        
        result = await edit_image(arguments)
        
        assert isinstance(result, str)
        assert "参数错误" in result
        assert "prompt参数是必需的" in result
    
    @pytest.mark.asyncio
    @patch('src.gemini_kling_mcp.tools.image_tools.get_config')
    @patch('src.gemini_kling_mcp.tools.image_tools.FileManager')
    @patch('src.gemini_kling_mcp.tools.image_tools.GeminiImageService')
    async def test_analyze_image_success(self, mock_service_class, mock_file_manager, mock_config):
        """测试图像分析成功"""
        # 设置模拟
        mock_config.return_value = Mock()
        mock_file_manager.return_value = Mock()
        
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
        
        # 执行测试
        arguments = {
            "image_input": "base64_image_data"
        }
        
        result = await analyze_image(arguments)
        
        # 验证结果
        assert isinstance(result, str)
        assert "图像分析完成" in result
        assert "分析类型: general" in result
        assert "这是一张美丽的风景照片" in result
        
        # 验证调用
        mock_service.analyze_image.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_analyze_image_invalid_temperature(self):
        """测试图像分析无效温度参数"""
        arguments = {
            "image_input": "base64_data",
            "temperature": 3.0  # 超过最大值
        }
        
        result = await analyze_image(arguments)
        
        assert isinstance(result, str)
        assert "参数错误" in result
        assert "temperature必须是0.0-2.0之间的数值" in result