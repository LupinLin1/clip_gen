"""
测试 Gemini 数据模型
"""

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.gemini_kling_mcp.services.gemini.models import (
    GeminiModel, MessageRole, GeminiMessage,
    TextGenerationRequest, TextGenerationResponse,
    ChatCompletionRequest, ChatCompletionResponse,
    TextAnalysisRequest, TextAnalysisResponse,
    create_safety_settings, HarmBlockThreshold,
    DEFAULT_SAFETY_SETTINGS
)


class TestGeminiModel:
    """测试 GeminiModel 枚举"""
    
    def test_gemini_model_values(self):
        """测试模型枚举值"""
        assert GeminiModel.GEMINI_15_PRO.value == "gemini-1.5-pro-002"
        assert GeminiModel.GEMINI_15_FLASH.value == "gemini-1.5-flash-002"
        assert GeminiModel.GEMINI_15_FLASH_8B.value == "gemini-1.5-flash-8b-001"
        assert GeminiModel.GEMINI_10_PRO.value == "gemini-1.0-pro-001"
    
    def test_get_default_model(self):
        """测试获取默认模型"""
        default_model = GeminiModel.get_default()
        assert default_model == GeminiModel.GEMINI_15_FLASH


class TestGeminiMessage:
    """测试 GeminiMessage 数据类"""
    
    def test_create_message(self):
        """测试创建消息"""
        message = GeminiMessage(
            role=MessageRole.USER,
            content="Hello, world!"
        )
        
        assert message.role == MessageRole.USER
        assert message.content == "Hello, world!"
    
    def test_message_to_dict(self):
        """测试消息转换为字典"""
        message = GeminiMessage(
            role=MessageRole.MODEL,
            content="Hello back!"
        )
        
        expected = {
            "role": "model",
            "parts": [{"text": "Hello back!"}]
        }
        
        assert message.to_dict() == expected
    
    def test_message_from_dict(self):
        """测试从字典创建消息"""
        data = {
            "role": "user",
            "content": "Test message"
        }
        
        message = GeminiMessage.from_dict(data)
        assert message.role == MessageRole.USER
        assert message.content == "Test message"
    
    def test_message_from_dict_with_parts(self):
        """测试从包含parts的字典创建消息"""
        data = {
            "role": "model",
            "parts": [{"text": "Response message"}]
        }
        
        message = GeminiMessage.from_dict(data)
        assert message.role == MessageRole.MODEL
        assert message.content == "Response message"
    
    def test_message_from_dict_empty_content(self):
        """测试从没有内容的字典创建消息"""
        data = {"role": "user"}
        
        message = GeminiMessage.from_dict(data)
        assert message.role == MessageRole.USER
        assert message.content == ""


class TestTextGenerationRequest:
    """测试 TextGenerationRequest 模型"""
    
    def test_minimal_request(self):
        """测试最小请求"""
        request = TextGenerationRequest(prompt="Generate some text")
        
        assert request.prompt == "Generate some text"
        assert request.model == GeminiModel.get_default()
        assert request.max_tokens == 1000
        assert request.temperature == 0.7
    
    def test_full_request(self):
        """测试完整请求"""
        request = TextGenerationRequest(
            prompt="Generate creative text",
            model=GeminiModel.GEMINI_15_PRO,
            max_tokens=2000,
            temperature=0.9,
            top_p=0.8,
            top_k=50,
            stop_sequences=["END", "STOP"],
            safety_settings=DEFAULT_SAFETY_SETTINGS
        )
        
        assert request.prompt == "Generate creative text"
        assert request.model == GeminiModel.GEMINI_15_PRO
        assert request.max_tokens == 2000
        assert request.temperature == 0.9
        assert request.top_p == 0.8
        assert request.top_k == 50
        assert request.stop_sequences == ["END", "STOP"]
        assert request.safety_settings == DEFAULT_SAFETY_SETTINGS
    
    def test_invalid_max_tokens(self):
        """测试无效的max_tokens"""
        with pytest.raises(PydanticValidationError):
            TextGenerationRequest(
                prompt="Test",
                max_tokens=10000  # 超过最大值
            )
        
        with pytest.raises(PydanticValidationError):
            TextGenerationRequest(
                prompt="Test",
                max_tokens=0  # 小于最小值
            )
    
    def test_invalid_temperature(self):
        """测试无效的temperature"""
        with pytest.raises(PydanticValidationError):
            TextGenerationRequest(
                prompt="Test",
                temperature=3.0  # 超过最大值
            )
        
        with pytest.raises(PydanticValidationError):
            TextGenerationRequest(
                prompt="Test", 
                temperature=-0.1  # 小于最小值
            )
    
    def test_invalid_top_p(self):
        """测试无效的top_p"""
        with pytest.raises(PydanticValidationError):
            TextGenerationRequest(
                prompt="Test",
                top_p=1.5  # 超过最大值
            )
        
        with pytest.raises(PydanticValidationError):
            TextGenerationRequest(
                prompt="Test",
                top_p=-0.1  # 小于最小值
            )
    
    def test_invalid_top_k(self):
        """测试无效的top_k"""
        with pytest.raises(PydanticValidationError):
            TextGenerationRequest(
                prompt="Test",
                top_k=150  # 超过最大值
            )
        
        with pytest.raises(PydanticValidationError):
            TextGenerationRequest(
                prompt="Test",
                top_k=0  # 小于最小值
            )


class TestTextGenerationResponse:
    """测试 TextGenerationResponse 模型"""
    
    def test_minimal_response(self):
        """测试最小响应"""
        response = TextGenerationResponse(
            text="Generated text",
            model="gemini-1.5-flash-002"
        )
        
        assert response.text == "Generated text"
        assert response.model == "gemini-1.5-flash-002"
        assert response.finish_reason is None
        assert response.usage is None
        assert response.safety_ratings is None
    
    def test_full_response(self):
        """测试完整响应"""
        usage = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        safety_ratings = [{"category": "HARASSMENT", "probability": "LOW"}]
        
        response = TextGenerationResponse(
            text="Generated creative text",
            model="gemini-1.5-pro-002",
            finish_reason="STOP",
            usage=usage,
            safety_ratings=safety_ratings
        )
        
        assert response.text == "Generated creative text"
        assert response.model == "gemini-1.5-pro-002"
        assert response.finish_reason == "STOP"
        assert response.usage == usage
        assert response.safety_ratings == safety_ratings


class TestChatCompletionRequest:
    """测试 ChatCompletionRequest 模型"""
    
    def test_minimal_request(self):
        """测试最小请求"""
        messages = [
            GeminiMessage(role=MessageRole.USER, content="Hello")
        ]
        
        request = ChatCompletionRequest(messages=messages)
        
        assert len(request.messages) == 1
        assert request.messages[0].content == "Hello"
        assert request.model == GeminiModel.get_default()
    
    def test_full_request(self):
        """测试完整请求"""
        messages = [
            GeminiMessage(role=MessageRole.USER, content="Hello"),
            GeminiMessage(role=MessageRole.MODEL, content="Hi there!"),
            GeminiMessage(role=MessageRole.USER, content="How are you?")
        ]
        
        request = ChatCompletionRequest(
            messages=messages,
            model=GeminiModel.GEMINI_15_PRO,
            max_tokens=1500,
            temperature=0.8,
            system_instruction="You are a helpful assistant."
        )
        
        assert len(request.messages) == 3
        assert request.model == GeminiModel.GEMINI_15_PRO
        assert request.max_tokens == 1500
        assert request.temperature == 0.8
        assert request.system_instruction == "You are a helpful assistant."
    
    def test_empty_messages(self):
        """测试空消息列表"""
        with pytest.raises(PydanticValidationError):
            ChatCompletionRequest(messages=[])


class TestTextAnalysisRequest:
    """测试 TextAnalysisRequest 模型"""
    
    def test_minimal_request(self):
        """测试最小请求"""
        request = TextAnalysisRequest(text="Analyze this text")
        
        assert request.text == "Analyze this text"
        assert request.model == GeminiModel.get_default()
        assert request.analysis_type == "general"
        assert request.language == "auto"
    
    def test_sentiment_analysis_request(self):
        """测试情感分析请求"""
        request = TextAnalysisRequest(
            text="I love this product!",
            analysis_type="sentiment",
            language="en",
            temperature=0.1
        )
        
        assert request.text == "I love this product!"
        assert request.analysis_type == "sentiment"
        assert request.language == "en"
        assert request.temperature == 0.1


class TestSafetySettings:
    """测试安全设置"""
    
    def test_create_default_safety_settings(self):
        """测试创建默认安全设置"""
        settings = create_safety_settings()
        
        assert len(settings) == 4
        assert all(isinstance(setting, dict) for setting in settings)
        assert all("category" in setting and "threshold" in setting for setting in settings)
    
    def test_create_custom_safety_settings(self):
        """测试创建自定义安全设置"""
        settings = create_safety_settings(HarmBlockThreshold.BLOCK_HIGH_AND_ABOVE)
        
        for setting in settings:
            assert setting["threshold"] == "BLOCK_HIGH_AND_ABOVE"
    
    def test_default_safety_settings_constant(self):
        """测试默认安全设置常量"""
        assert len(DEFAULT_SAFETY_SETTINGS) == 4
        assert all(isinstance(setting, dict) for setting in DEFAULT_SAFETY_SETTINGS)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])