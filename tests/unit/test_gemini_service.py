"""
Gemini服务单元测试

测试Gemini文本和图像服务的核心功能。
"""

import pytest
from unittest.mock import patch, AsyncMock, Mock
import json

from src.gemini_kling_mcp.services.gemini.text_service import GeminiTextService
from src.gemini_kling_mcp.services.gemini.image_service import GeminiImageService
from src.gemini_kling_mcp.services.gemini.models import (
    TextGenerationRequest, ChatCompletionRequest, TextAnalysisRequest,
    ImageGenerationRequest, GeminiModel, MessageRole, GeminiMessage
)
from src.gemini_kling_mcp.exceptions import ToolExecutionError, ValidationError
from tests.test_data_generator import test_data_generator


@pytest.mark.unit
class TestGeminiTextService:
    """Gemini文本服务测试类"""
    
    @pytest.mark.asyncio
    async def test_generate_text_success(self, gemini_config, mock_gemini_client):
        """测试文本生成成功"""
        service = GeminiTextService(gemini_config)
        request = test_data_generator.generate_gemini_text_request()
        
        with patch.object(service, '_get_client') as mock_get_client:
            mock_get_client.return_value.__aenter__.return_value = mock_gemini_client
            
            response = await service.generate_text(request)
            
            assert response is not None
            assert hasattr(response, 'text')
            assert hasattr(response, 'model')
            assert hasattr(response, 'finish_reason')
            assert len(response.text) > 0
            assert response.model == request.model.value
    
    @pytest.mark.asyncio
    async def test_generate_text_dict_request(self, gemini_config, mock_gemini_client):
        """测试使用字典格式请求生成文本"""
        service = GeminiTextService(gemini_config)
        request_dict = {
            "prompt": "测试提示",
            "model": GeminiModel.GEMINI_15_FLASH,
            "max_tokens": 100,
            "temperature": 0.7
        }
        
        with patch.object(service, '_get_client') as mock_get_client:
            mock_get_client.return_value.__aenter__.return_value = mock_gemini_client
            
            response = await service.generate_text(request_dict)
            
            assert response is not None
            assert len(response.text) > 0
    
    @pytest.mark.asyncio
    async def test_generate_text_invalid_request(self, gemini_config):
        """测试无效请求格式"""
        service = GeminiTextService(gemini_config)
        invalid_request = {"invalid": "request"}
        
        with pytest.raises(ValidationError, match="请求参数无效"):
            await service.generate_text(invalid_request)
    
    @pytest.mark.asyncio
    async def test_generate_text_api_error(self, gemini_config):
        """测试API错误处理"""
        service = GeminiTextService(gemini_config)
        request = test_data_generator.generate_gemini_text_request()
        
        with patch.object(service, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.generate_content.side_effect = Exception("API Error")
            mock_get_client.return_value.__aenter__.return_value = mock_client
            
            with pytest.raises(ToolExecutionError, match="文本生成异常"):
                await service.generate_text(request)
    
    @pytest.mark.asyncio
    async def test_complete_chat_success(self, gemini_config, mock_gemini_client):
        """测试对话完成成功"""
        service = GeminiTextService(gemini_config)
        request = test_data_generator.generate_gemini_chat_request()
        
        with patch.object(service, '_get_client') as mock_get_client:
            mock_get_client.return_value.__aenter__.return_value = mock_gemini_client
            
            response = await service.complete_chat(request)
            
            assert response is not None
            assert hasattr(response, 'message')
            assert response.message.role == MessageRole.MODEL
            assert len(response.message.content) > 0
    
    @pytest.mark.asyncio
    async def test_complete_chat_dict_messages(self, gemini_config, mock_gemini_client):
        """测试使用字典格式消息的对话完成"""
        service = GeminiTextService(gemini_config)
        request_dict = {
            "messages": [
                {"role": "user", "content": "你好"},
                {"role": "model", "content": "你好！有什么可以帮助你的吗？"},
                {"role": "user", "content": "介绍一下AI"}
            ],
            "model": GeminiModel.GEMINI_15_FLASH,
            "max_tokens": 200
        }
        
        with patch.object(service, '_get_client') as mock_get_client:
            mock_get_client.return_value.__aenter__.return_value = mock_gemini_client
            
            response = await service.complete_chat(request_dict)
            
            assert response is not None
            assert response.message.role == MessageRole.MODEL
    
    @pytest.mark.asyncio
    async def test_analyze_text_success(self, gemini_config, mock_gemini_client):
        """测试文本分析成功"""
        service = GeminiTextService(gemini_config)
        request = test_data_generator.generate_text_analysis_request()
        
        with patch.object(service, '_get_client') as mock_get_client:
            mock_get_client.return_value.__aenter__.return_value = mock_gemini_client
            
            response = await service.analyze_text(request)
            
            assert response is not None
            assert hasattr(response, 'analysis')
            assert len(response.analysis) > 0
            assert response.model == request.model.value
    
    @pytest.mark.asyncio
    async def test_analyze_text_sentiment(self, gemini_config, mock_gemini_client):
        """测试情感分析"""
        service = GeminiTextService(gemini_config)
        request = TextAnalysisRequest(
            text="我非常喜欢这个产品！",
            model=GeminiModel.GEMINI_15_FLASH,
            analysis_type="sentiment"
        )
        
        # Mock返回JSON格式的情感分析结果
        mock_response = {
            "choices": [{
                "message": {
                    "content": json.dumps({"sentiment": "positive", "confidence": 0.9})
                }
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        }
        
        with patch.object(service, '_get_client') as mock_get_client:
            mock_client = mock_gemini_client
            mock_client.analyze_text.return_value = mock_response
            mock_get_client.return_value.__aenter__.return_value = mock_client
            
            response = await service.analyze_text(request)
            
            assert response is not None
            assert response.sentiment is not None
            assert response.confidence is not None
    
    def test_build_generation_request(self, gemini_config):
        """测试构建文本生成请求"""
        service = GeminiTextService(gemini_config)
        request = TextGenerationRequest(
            prompt="测试提示",
            model=GeminiModel.GEMINI_15_FLASH,
            max_tokens=100,
            temperature=0.7,
            stop_sequences=["STOP"]
        )
        
        api_request = service._build_generation_request(request)
        
        assert "model" in api_request
        assert "messages" in api_request
        assert "max_tokens" in api_request
        assert "temperature" in api_request
        assert "stop" in api_request
        
        assert api_request["model"] == request.model.value
        assert api_request["max_tokens"] == request.max_tokens
        assert api_request["temperature"] == request.temperature
        assert api_request["stop"] == request.stop_sequences
        assert len(api_request["messages"]) == 1
        assert api_request["messages"][0]["role"] == "user"
        assert api_request["messages"][0]["content"] == request.prompt
    
    def test_build_chat_request(self, gemini_config):
        """测试构建对话请求"""
        service = GeminiTextService(gemini_config)
        messages = [
            GeminiMessage(role=MessageRole.USER, content="你好"),
            GeminiMessage(role=MessageRole.MODEL, content="你好！")
        ]
        request = ChatCompletionRequest(
            messages=messages,
            model=GeminiModel.GEMINI_15_FLASH,
            system_instruction="你是一个有用的助手"
        )
        
        api_request = service._build_chat_request(request)
        
        assert "model" in api_request
        assert "messages" in api_request
        assert len(api_request["messages"]) == 3  # system + 2 user messages
        assert api_request["messages"][0]["role"] == "system"
        assert api_request["messages"][0]["content"] == "你是一个有用的助手"


@pytest.mark.unit
class TestGeminiImageService:
    """Gemini图像服务测试类"""
    
    @pytest.mark.asyncio
    async def test_generate_image_success(self, gemini_config, mock_gemini_client):
        """测试图像生成成功"""
        service = GeminiImageService(gemini_config)
        request = test_data_generator.generate_image_request()
        
        with patch.object(service, '_get_client') as mock_get_client:
            mock_get_client.return_value.__aenter__.return_value = mock_gemini_client
            
            response = await service.generate_image(request)
            
            assert response is not None
            assert hasattr(response, 'model')
            assert response.model == request.model
            
            # 根据输出模式检查结果
            if request.output_mode == "base64":
                assert hasattr(response, 'images')
                assert len(response.images) > 0
            else:
                assert hasattr(response, 'file_paths')
                assert len(response.file_paths) > 0
    
    @pytest.mark.asyncio
    async def test_generate_image_dict_request(self, gemini_config, mock_gemini_client):
        """测试使用字典格式请求生成图像"""
        service = GeminiImageService(gemini_config)
        request_dict = {
            "prompt": "一只可爱的小猫",
            "model": "imagen-3.0-generate-001",
            "num_images": 2,
            "aspect_ratio": "1:1",
            "output_mode": "file"
        }
        
        with patch.object(service, '_get_client') as mock_get_client:
            mock_get_client.return_value.__aenter__.return_value = mock_gemini_client
            
            response = await service.generate_image(request_dict)
            
            assert response is not None
            assert len(response.file_paths) > 0
    
    @pytest.mark.asyncio
    async def test_generate_image_base64_mode(self, gemini_config, mock_gemini_client):
        """测试base64输出模式"""
        service = GeminiImageService(gemini_config)
        request = ImageGenerationRequest(
            prompt="测试图像",
            model="imagen-3.0-generate-001",
            num_images=1,
            output_mode="base64"
        )
        
        with patch.object(service, '_get_client') as mock_get_client:
            mock_get_client.return_value.__aenter__.return_value = mock_gemini_client
            
            response = await service.generate_image(request)
            
            assert response is not None
            assert len(response.images) > 0
            assert "data" in response.images[0]
    
    @pytest.mark.asyncio
    async def test_generate_image_invalid_request(self, gemini_config):
        """测试无效图像请求"""
        service = GeminiImageService(gemini_config)
        invalid_request = {"invalid": "request"}
        
        with pytest.raises(ValidationError, match="请求参数无效"):
            await service.generate_image(invalid_request)
    
    @pytest.mark.asyncio
    async def test_generate_image_api_error(self, gemini_config):
        """测试图像生成API错误"""
        service = GeminiImageService(gemini_config)
        request = test_data_generator.generate_image_request()
        
        with patch.object(service, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.generate_image.side_effect = Exception("Image API Error")
            mock_get_client.return_value.__aenter__.return_value = mock_client
            
            with pytest.raises(ToolExecutionError, match="图像生成异常"):
                await service.generate_image(request)


@pytest.mark.unit
class TestGeminiServiceIntegration:
    """Gemini服务集成测试"""
    
    @pytest.mark.asyncio
    async def test_text_and_image_workflow(self, gemini_config, mock_gemini_client):
        """测试文本和图像生成的工作流"""
        text_service = GeminiTextService(gemini_config)
        image_service = GeminiImageService(gemini_config)
        
        # 先生成文本
        text_request = TextGenerationRequest(
            prompt="描述一个美丽的风景",
            model=GeminiModel.GEMINI_15_FLASH,
            max_tokens=200
        )
        
        with patch.object(text_service, '_get_client') as mock_text_client, \
             patch.object(image_service, '_get_client') as mock_image_client:
            
            mock_text_client.return_value.__aenter__.return_value = mock_gemini_client
            mock_image_client.return_value.__aenter__.return_value = mock_gemini_client
            
            text_response = await text_service.generate_text(text_request)
            assert len(text_response.text) > 0
            
            # 基于文本生成图像
            image_request = ImageGenerationRequest(
                prompt=f"基于描述创建图像: {text_response.text[:100]}",
                model="imagen-3.0-generate-001",
                num_images=1
            )
            
            image_response = await image_service.generate_image(image_request)
            assert len(image_response.file_paths) > 0
    
    @pytest.mark.asyncio
    async def test_service_resource_cleanup(self, gemini_config):
        """测试服务资源清理"""
        service = GeminiTextService(gemini_config)
        
        # 确保服务可以正确关闭
        await service.close()
        
        # 再次关闭应该不会出错
        await service.close()
    
    def test_service_configuration(self, gemini_config):
        """测试服务配置"""
        service = GeminiTextService(gemini_config)
        
        assert service.config == gemini_config
        assert service.config.api_key == "test-gemini-key"
        assert service.config.base_url == "https://gptproto.com"