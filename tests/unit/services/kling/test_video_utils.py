"""
测试 Kling 视频处理工具
"""

import pytest
import os
import tempfile
import base64
from unittest.mock import patch, AsyncMock, Mock
from PIL import Image
import aiohttp

from src.gemini_kling_mcp.services.kling.video_utils import (
    VideoFormatConverter,
    KlingVideoUtils
)
from src.gemini_kling_mcp.exceptions import ValidationError, FileOperationError

class TestVideoFormatConverter:
    """测试视频格式转换器"""
    
    def test_init(self):
        """测试初始化"""
        converter = VideoFormatConverter()
        
        assert "mp4" in converter.supported_formats
        assert "jpg" in converter.supported_image_formats
        assert converter.supported_formats["mp4"] == "video/mp4"
        assert converter.supported_image_formats["jpg"] == "image/jpeg"
    
    def test_get_video_info_file_not_exists(self):
        """测试获取不存在文件的信息"""
        converter = VideoFormatConverter()
        
        with pytest.raises(FileOperationError) as exc_info:
            converter.get_video_info("/nonexistent/file.mp4")
        
        assert "视频文件不存在" in str(exc_info.value)
    
    def test_get_video_info_existing_file(self):
        """测试获取存在文件的信息"""
        converter = VideoFormatConverter()
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
            tmp_file.write(b"fake video content")
            tmp_path = tmp_file.name
        
        try:
            info = converter.get_video_info(tmp_path)
            
            assert info["path"] == tmp_path
            assert info["size"] > 0
            assert info["format"] == "mp4"
            assert info["mime_type"] == "video/mp4"
            assert "width" in info
            assert "height" in info
            assert "duration" in info
            
        finally:
            os.unlink(tmp_path)
    
    def test_validate_video_file_not_exists(self):
        """测试验证不存在的文件"""
        converter = VideoFormatConverter()
        
        with pytest.raises(ValidationError) as exc_info:
            converter.validate_video_file("/nonexistent/file.mp4")
        
        assert "视频文件不存在" in str(exc_info.value)
    
    def test_validate_video_file_too_large(self):
        """测试验证过大的文件"""
        converter = VideoFormatConverter()
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
            tmp_file.write(b"x" * (10 * 1024 * 1024))  # 10MB
            tmp_path = tmp_file.name
        
        try:
            with pytest.raises(ValidationError) as exc_info:
                converter.validate_video_file(tmp_path, max_size_mb=5)
            
            assert "视频文件过大" in str(exc_info.value)
            
        finally:
            os.unlink(tmp_path)
    
    def test_validate_video_file_unsupported_format(self):
        """测试验证不支持的格式"""
        converter = VideoFormatConverter()
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as tmp_file:
            tmp_file.write(b"fake content")
            tmp_path = tmp_file.name
        
        try:
            with pytest.raises(ValidationError) as exc_info:
                converter.validate_video_file(tmp_path)
            
            assert "不支持的视频格式" in str(exc_info.value)
            
        finally:
            os.unlink(tmp_path)
    
    def test_validate_video_file_success(self):
        """测试验证成功的文件"""
        converter = VideoFormatConverter()
        
        # 创建小的临时文件
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
            tmp_file.write(b"fake video")
            tmp_path = tmp_file.name
        
        try:
            result = converter.validate_video_file(tmp_path)
            assert result is True
            
        finally:
            os.unlink(tmp_path)

class TestKlingVideoUtils:
    """测试 Kling 视频工具"""
    
    @pytest.fixture
    def video_utils(self):
        """创建视频工具实例"""
        return KlingVideoUtils()
    
    @pytest.fixture
    def test_image_path(self):
        """创建测试图像文件"""
        # 创建小的测试图像
        image = Image.new('RGB', (100, 100), color='red')
        
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_file:
            image.save(tmp_file.name, 'JPEG')
            yield tmp_file.name
        
        # 清理
        if os.path.exists(tmp_file.name):
            os.unlink(tmp_file.name)
    
    @pytest.mark.asyncio
    async def test_encode_image_to_base64(self, video_utils, test_image_path):
        """测试图像Base64编码"""
        result = await video_utils.encode_image_to_base64(test_image_path)
        
        assert result.startswith("data:image/jpeg;base64,")
        
        # 验证Base64内容
        base64_content = result.split(',')[1]
        decoded = base64.b64decode(base64_content)
        assert len(decoded) > 0
    
    @pytest.mark.asyncio
    async def test_encode_image_file_not_exists(self, video_utils):
        """测试编码不存在的图像文件"""
        with pytest.raises(FileOperationError) as exc_info:
            await video_utils.encode_image_to_base64("/nonexistent/image.jpg")
        
        assert "图像文件不存在" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_encode_image_unsupported_format(self, video_utils):
        """测试编码不支持的格式"""
        # 创建不支持格式的临时文件
        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as tmp_file:
            tmp_file.write(b"fake content")
            tmp_path = tmp_file.name
        
        try:
            with pytest.raises(ValidationError) as exc_info:
                await video_utils.encode_image_to_base64(tmp_path)
            
            assert "不支持的图像格式" in str(exc_info.value)
            
        finally:
            os.unlink(tmp_path)
    
    @pytest.mark.asyncio
    async def test_download_image_from_url(self, video_utils):
        """测试从URL下载图像"""
        test_url = "https://example.com/test.jpg"
        fake_image_data = b"fake image content"
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            # 设置mock会话
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {'content-type': 'image/jpeg'}
            
            # 模拟异步迭代器
            async def fake_iter_chunked(size):
                yield fake_image_data
            
            mock_response.content.iter_chunked = fake_iter_chunked
            
            # 正确的异步上下文管理器mock
            mock_context_manager = AsyncMock()
            mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
            mock_context_manager.__aexit__ = AsyncMock(return_value=None)
            
            mock_session.get = Mock(return_value=mock_context_manager)
            
            # session本身也是异步上下文管理器
            mock_session_context_manager = AsyncMock()
            mock_session_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_context_manager.__aexit__ = AsyncMock(return_value=None)
            
            mock_session_class.return_value = mock_session_context_manager
            
            # 测试下载
            result_path = await video_utils.download_image_from_url(test_url)
            
            # 验证文件被创建
            assert os.path.exists(result_path)
            assert result_path.endswith('.jpg')
            
            # 验证内容
            with open(result_path, 'rb') as f:
                content = f.read()
                assert content == fake_image_data
            
            # 清理
            os.unlink(result_path)
    
    @pytest.mark.asyncio
    async def test_download_image_http_error(self, video_utils):
        """测试下载图像时HTTP错误"""
        test_url = "https://example.com/notfound.jpg"
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 404
            
            # 正确的异步上下文管理器mock
            mock_context_manager = AsyncMock()
            mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
            mock_context_manager.__aexit__ = AsyncMock(return_value=None)
            
            mock_session.get = Mock(return_value=mock_context_manager)
            
            # session本身也是异步上下文管理器
            mock_session_context_manager = AsyncMock()
            mock_session_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_context_manager.__aexit__ = AsyncMock(return_value=None)
            
            mock_session_class.return_value = mock_session_context_manager
            
            with pytest.raises(FileOperationError) as exc_info:
                await video_utils.download_image_from_url(test_url)
            
            assert "下载图像失败" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_download_video_from_url(self, video_utils):
        """测试从URL下载视频"""
        test_url = "https://example.com/test.mp4"
        fake_video_data = b"fake video content"
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {
                'content-type': 'video/mp4',
                'content-length': str(len(fake_video_data))
            }
            
            async def fake_iter_chunked(size):
                yield fake_video_data
            
            mock_response.content.iter_chunked = fake_iter_chunked
            
            # 正确的异步上下文管理器mock
            mock_context_manager = AsyncMock()
            mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
            mock_context_manager.__aexit__ = AsyncMock(return_value=None)
            
            mock_session.get = Mock(return_value=mock_context_manager)
            
            # session本身也是异步上下文管理器
            mock_session_context_manager = AsyncMock()
            mock_session_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_context_manager.__aexit__ = AsyncMock(return_value=None)
            
            mock_session_class.return_value = mock_session_context_manager
            
            result_path = await video_utils.download_video_from_url(test_url)
            
            assert os.path.exists(result_path)
            assert result_path.endswith('.mp4')
            
            with open(result_path, 'rb') as f:
                content = f.read()
                assert content == fake_video_data
            
            os.unlink(result_path)
    
    def test_optimize_image_for_video(self, video_utils, test_image_path):
        """测试优化图像用于视频生成"""
        # 创建一个较大的测试图像以便测试缩放
        large_image = Image.new('RGB', (400, 300), color='blue')
        
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_file:
            large_image.save(tmp_file.name, 'JPEG')
            large_path = tmp_file.name
        
        try:
            optimized_path = video_utils.optimize_image_for_video(
                large_path,
                target_width=200,
                target_height=200,
                quality=80
            )
            
            try:
                assert os.path.exists(optimized_path)
                assert "_optimized" in optimized_path
                
                # 验证优化后的图像
                with Image.open(optimized_path) as img:
                    assert img.size == (200, 200)
                    assert img.mode == 'RGB'
                
            finally:
                if os.path.exists(optimized_path):
                    os.unlink(optimized_path)
                    
        finally:
            os.unlink(large_path)
    
    def test_optimize_image_larger_original(self, video_utils):
        """测试优化大图像"""
        # 创建大图像
        large_image = Image.new('RGB', (2000, 1500), color='blue')
        
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_file:
            large_image.save(tmp_file.name, 'JPEG')
            large_path = tmp_file.name
        
        try:
            optimized_path = video_utils.optimize_image_for_video(
                large_path,
                target_width=1024,
                target_height=1024,
                quality=85
            )
            
            # 验证缩放
            with Image.open(optimized_path) as img:
                assert img.size == (1024, 1024)
            
            # 清理
            os.unlink(optimized_path)
            
        finally:
            os.unlink(large_path)
    
    def test_get_aspect_ratio_dimensions(self, video_utils):
        """测试获取宽高比尺寸"""
        test_cases = [
            ("1:1", (1024, 1024)),
            ("9:16", (608, 1080)),
            ("16:9", (1360, 768)),
            ("21:9", (1792, 768)),
            ("3:4", (768, 1024)),
            ("4:3", (1024, 768))
        ]
        
        for aspect_ratio, expected in test_cases:
            result = video_utils.get_aspect_ratio_dimensions(aspect_ratio)
            assert result == expected
        
        # 测试未知宽高比
        result = video_utils.get_aspect_ratio_dimensions("unknown")
        assert result == (1024, 1024)  # 默认值
    
    @pytest.mark.asyncio
    async def test_validate_and_prepare_inputs_basic(self, video_utils):
        """测试验证和准备基础输入"""
        result = await video_utils.validate_and_prepare_inputs("Test prompt")
        
        assert result["prompt"] == "Test prompt"
        assert "image" not in result
        assert "image_url" not in result
    
    @pytest.mark.asyncio
    async def test_validate_and_prepare_inputs_empty_prompt(self, video_utils):
        """测试空提示文本验证"""
        with pytest.raises(ValidationError) as exc_info:
            await video_utils.validate_and_prepare_inputs("")
        
        assert "提示文本不能为空" in str(exc_info.value)
        
        with pytest.raises(ValidationError) as exc_info:
            await video_utils.validate_and_prepare_inputs("   ")
        
        assert "提示文本不能为空" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_validate_and_prepare_inputs_short_prompt(self, video_utils):
        """测试过短的提示文本"""
        with pytest.raises(ValidationError) as exc_info:
            await video_utils.validate_and_prepare_inputs("Hi")
        
        assert "提示文本过短" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_validate_and_prepare_inputs_with_image(self, video_utils, test_image_path):
        """测试包含图像路径的输入"""
        result = await video_utils.validate_and_prepare_inputs(
            "Test prompt",
            image_path=test_image_path
        )
        
        assert result["prompt"] == "Test prompt"
        assert "image" in result
        assert result["image"].startswith("data:image/jpeg;base64,")
    
    @pytest.mark.asyncio
    async def test_validate_and_prepare_inputs_with_image_url(self, video_utils):
        """测试包含图像URL的输入"""
        test_url = "https://example.com/test.jpg"
        
        result = await video_utils.validate_and_prepare_inputs(
            "Test prompt",
            image_url=test_url
        )
        
        assert result["prompt"] == "Test prompt"
        assert result["image_url"] == test_url
    
    @pytest.mark.asyncio
    async def test_validate_and_prepare_inputs_both_image_inputs(self, video_utils, test_image_path):
        """测试同时提供图像路径和URL"""
        with pytest.raises(ValidationError) as exc_info:
            await video_utils.validate_and_prepare_inputs(
                "Test prompt",
                image_path=test_image_path,
                image_url="https://example.com/test.jpg"
            )
        
        assert "不能同时提供图像文件路径和URL" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_validate_and_prepare_inputs_nonexistent_image(self, video_utils):
        """测试不存在的图像文件"""
        with pytest.raises(FileOperationError) as exc_info:
            await video_utils.validate_and_prepare_inputs(
                "Test prompt",
                image_path="/nonexistent/image.jpg"
            )
        
        assert "图像文件不存在" in str(exc_info.value)