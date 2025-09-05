"""
测试 Gemini 文本服务
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from contextlib import asynccontextmanager

from src.gemini_kling_mcp.config import GeminiConfig
from src.gemini_kling_mcp.exceptions import ToolExecutionError, ValidationError
from src.gemini_kling_mcp.services.gemini.text_service import GeminiTextService
from src.gemini_kling_mcp.services.gemini.models import (
    TextGenerationRequest, TextGenerationResponse,
    ChatCompletionRequest, ChatCompletionResponse,
    TextAnalysisRequest, TextAnalysisResponse,
    GeminiMessage, MessageRole, GeminiModel
)
from src.gemini_kling_mcp.services.gemini.client import GeminiHTTPError


@pytest.fixture
def gemini_config():
    """创建测试配置"""
    return GeminiConfig(
        api_key="test-api-key",
        base_url="https://test.googleapis.com",
        timeout=30,
        max_retries=2
    )


@pytest.fixture
def gemini_service(gemini_config):
    """创建测试服务"""
    return GeminiTextService(gemini_config)


class MockGeminiClient:
    """模拟Gemini客户端"""
    
    def __init__(self):
        self.generate_content = AsyncMock()
        self.chat_completion = AsyncMock()
        self.analyze_text = AsyncMock()
        self.extract_generated_text = Mock()
        self.extract_usage_info = Mock()
        self.extract_safety_ratings = Mock()


class TestGeminiTextServiceInit:
    """测试服务初始化"""
    
    def test_service_init_with_config(self, gemini_config):
        """测试使用配置初始化服务"""
        service = GeminiTextService(gemini_config)
        
        assert service.config == gemini_config
        assert service._client is None
    
    @patch('src.gemini_kling_mcp.services.gemini.text_service.get_config')
    def test_service_init_without_config(self, mock_get_config, gemini_config):
        """测试不提供配置时的初始化"""
        mock_config = Mock()
        mock_config.gemini = gemini_config
        mock_get_config.return_value = mock_config
        
        service = GeminiTextService()
        
        assert service.config == gemini_config
        mock_get_config.assert_called_once()


class TestTextGeneration:
    """测试文本生成功能"""
    
    @pytest.mark.asyncio
    async def test_generate_text_success(self, gemini_service):
        """测试成功生成文本"""
        # 创建请求
        request = TextGenerationRequest(
            prompt="Generate a story",
            model=GeminiModel.GEMINI_15_FLASH,
            max_tokens=500,
            temperature=0.8
        )
        
        # 模拟API响应
        api_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Once upon a time..."}]
                    },
                    "finishReason": "STOP"
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 5,
                "candidatesTokenCount": 20,
                "totalTokenCount": 25
            }
        }
        
        # 创建模拟客户端
        mock_client = MockGeminiClient()
        mock_client.generate_content.return_value = api_response
        mock_client.extract_generated_text.return_value = "Once upon a time..."
        mock_client.extract_usage_info.return_value = {
            "prompt_tokens": 5,
            "completion_tokens": 20,
            "total_tokens": 25
        }
        mock_client.extract_safety_ratings.return_value = []
        
        # 模拟上下文管理器
        @asynccontextmanager
        async def mock_get_client():
            yield mock_client
        
        gemini_service._get_client = mock_get_client
        
        # 执行测试
        response = await gemini_service.generate_text(request)
        
        # 验证结果
        assert isinstance(response, TextGenerationResponse)
        assert response.text == "Once upon a time..."
        assert response.model == GeminiModel.GEMINI_15_FLASH.value
        assert response.finish_reason == "STOP"
        assert response.usage["total_tokens"] == 25
        
        # 验证API调用
        mock_client.generate_content.assert_called_once()
        args, kwargs = mock_client.generate_content.call_args
        assert args[0] == GeminiModel.GEMINI_15_FLASH
        
        # 验证请求数据结构
        request_data = args[1]
        assert "contents" in request_data
        assert "generationConfig" in request_data
        assert request_data["generationConfig"]["maxOutputTokens"] == 500
        assert request_data["generationConfig"]["temperature"] == 0.8
    
    @pytest.mark.asyncio
    async def test_generate_text_with_dict_request(self, gemini_service):
        """测试使用字典请求生成文本"""
        request_dict = {
            "prompt": "Generate text from dict",
            "model": "gemini-1.5-flash-002",
            "max_tokens": 300
        }
        
        api_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Generated from dict"}]
                    }
                }
            ]
        }
        
        mock_client = MockGeminiClient()
        mock_client.generate_content.return_value = api_response
        mock_client.extract_generated_text.return_value = "Generated from dict"
        mock_client.extract_usage_info.return_value = {}
        mock_client.extract_safety_ratings.return_value = []
        
        @asynccontextmanager
        async def mock_get_client():
            yield mock_client
        
        gemini_service._get_client = mock_get_client
        
        response = await gemini_service.generate_text(request_dict)
        
        assert response.text == "Generated from dict"
        mock_client.generate_content.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_text_invalid_dict_request(self, gemini_service):
        """测试无效字典请求"""
        invalid_request = {
            "model": "gemini-1.5-flash-002"
            # 缺少必需的prompt字段
        }
        
        with pytest.raises(ValidationError) as exc_info:
            await gemini_service.generate_text(invalid_request)
        
        assert "请求参数无效" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_generate_text_api_error(self, gemini_service):
        """测试API错误处理"""
        request = TextGenerationRequest(prompt="Test prompt")
        
        mock_client = MockGeminiClient()
        mock_client.generate_content.side_effect = GeminiHTTPError(
            "API Error",
            status_code=400,
            response_data={"error": "Invalid request"}
        )
        
        @asynccontextmanager
        async def mock_get_client():
            yield mock_client
        
        gemini_service._get_client = mock_get_client
        
        with pytest.raises(ToolExecutionError) as exc_info:
            await gemini_service.generate_text(request)
        
        assert "文本生成失败" in str(exc_info.value)
        assert exc_info.value.tool_name == "gemini_generate_text"
    
    @pytest.mark.asyncio
    async def test_generate_text_unexpected_error(self, gemini_service):
        """测试意外错误处理"""
        request = TextGenerationRequest(prompt="Test prompt")
        
        mock_client = MockGeminiClient()
        mock_client.generate_content.side_effect = ValueError("Unexpected error")
        
        @asynccontextmanager
        async def mock_get_client():
            yield mock_client
        
        gemini_service._get_client = mock_get_client
        
        with pytest.raises(ToolExecutionError) as exc_info:
            await gemini_service.generate_text(request)
        
        assert "文本生成异常" in str(exc_info.value)


class TestChatCompletion:
    """测试对话完成功能"""
    
    @pytest.mark.asyncio
    async def test_complete_chat_success(self, gemini_service):
        """测试成功完成对话"""
        messages = [
            GeminiMessage(role=MessageRole.USER, content="Hello"),
            GeminiMessage(role=MessageRole.MODEL, content="Hi there!"),
            GeminiMessage(role=MessageRole.USER, content="How are you?")
        ]
        
        request = ChatCompletionRequest(
            messages=messages,
            model=GeminiModel.GEMINI_15_FLASH,
            system_instruction="You are a helpful assistant"
        )
        
        api_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "I'm doing well, thank you!"}]
                    },
                    "finishReason": "STOP"
                }
            ]
        }
        
        mock_client = MockGeminiClient()
        mock_client.chat_completion.return_value = api_response
        mock_client.extract_generated_text.return_value = "I'm doing well, thank you!"
        mock_client.extract_usage_info.return_value = {"total_tokens": 15}
        mock_client.extract_safety_ratings.return_value = []
        
        @asynccontextmanager
        async def mock_get_client():
            yield mock_client
        
        gemini_service._get_client = mock_get_client
        
        response = await gemini_service.complete_chat(request)
        
        assert isinstance(response, ChatCompletionResponse)
        assert response.message.role == MessageRole.MODEL
        assert response.message.content == "I'm doing well, thank you!"
        assert response.finish_reason == "STOP"
        
        # 验证API调用
        mock_client.chat_completion.assert_called_once()
        args, kwargs = mock_client.chat_completion.call_args
        request_data = args[1]
        
        # 验证消息转换
        assert "contents" in request_data
        assert len(request_data["contents"]) == 3
        assert "systemInstruction" in request_data
    
    @pytest.mark.asyncio
    async def test_complete_chat_with_dict_request(self, gemini_service):
        """测试使用字典请求完成对话"""
        request_dict = {
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "model", "content": "Hi!"}
            ],
            "model": "gemini-1.5-flash-002"
        }
        
        api_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Response from dict"}]
                    }
                }
            ]
        }
        
        mock_client = MockGeminiClient()
        mock_client.chat_completion.return_value = api_response
        mock_client.extract_generated_text.return_value = "Response from dict"
        mock_client.extract_usage_info.return_value = {}
        mock_client.extract_safety_ratings.return_value = []
        
        @asynccontextmanager
        async def mock_get_client():
            yield mock_client
        
        gemini_service._get_client = mock_get_client
        
        response = await gemini_service.complete_chat(request_dict)
        
        assert response.message.content == "Response from dict"
        mock_client.chat_completion.assert_called_once()


class TestTextAnalysis:
    """测试文本分析功能"""
    
    @pytest.mark.asyncio
    async def test_analyze_text_success(self, gemini_service):
        """测试成功分析文本"""
        request = TextAnalysisRequest(
            text="This is a great product! I love it.",
            analysis_type="sentiment",
            language="en"
        )
        
        api_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": '{"sentiment": "positive", "confidence": 0.9}'}]
                    }
                }
            ]
        }
        
        mock_client = MockGeminiClient()
        mock_client.analyze_text.return_value = api_response
        mock_client.extract_generated_text.return_value = '{"sentiment": "positive", "confidence": 0.9}'
        mock_client.extract_usage_info.return_value = {"total_tokens": 10}
        
        @asynccontextmanager
        async def mock_get_client():
            yield mock_client
        
        gemini_service._get_client = mock_get_client
        
        response = await gemini_service.analyze_text(request)
        
        assert isinstance(response, TextAnalysisResponse)
        assert '{"sentiment": "positive", "confidence": 0.9}' in response.analysis
        assert response.model == GeminiModel.GEMINI_15_FLASH.value
        
        # 验证API调用
        mock_client.analyze_text.assert_called_once()
        args, kwargs = mock_client.analyze_text.call_args
        request_data = args[1]
        
        # 验证分析提示构建
        assert "contents" in request_data
        prompt_text = request_data["contents"][0]["parts"][0]["text"]
        assert "情感倾向" in prompt_text
        assert request.text in prompt_text
    
    @pytest.mark.asyncio  
    async def test_analyze_text_with_structured_response(self, gemini_service):
        """测试结构化分析响应"""
        request = TextAnalysisRequest(
            text="Test text for analysis",
            analysis_type="sentiment"
        )
        
        # 模拟返回JSON格式的分析结果
        json_response = '{"sentiment": {"score": "positive"}, "confidence": 0.8, "entities": [{"name": "Test", "type": "NOUN"}]}'
        
        api_response = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": json_response}]
                    }
                }
            ]
        }
        
        mock_client = MockGeminiClient()
        mock_client.analyze_text.return_value = api_response
        mock_client.extract_generated_text.return_value = json_response
        mock_client.extract_usage_info.return_value = {}
        
        @asynccontextmanager
        async def mock_get_client():
            yield mock_client
        
        gemini_service._get_client = mock_get_client
        
        response = await gemini_service.analyze_text(request)
        
        assert response.analysis == json_response
        # JSON解析应该填充结构化字段
        assert response.sentiment is not None
        assert response.entities is not None
    
    @pytest.mark.asyncio
    async def test_analyze_different_types(self, gemini_service):
        """测试不同类型的分析"""
        analysis_types = [
            "general", "sentiment", "summarize", "keywords",
            "entities", "classify", "translate", "grammar"
        ]
        
        for analysis_type in analysis_types:
            request = TextAnalysisRequest(
                text="Test text",
                analysis_type=analysis_type
            )
            
            api_response = {
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": f"Analysis result for {analysis_type}"}]
                        }
                    }
                ]
            }
            
            mock_client = MockGeminiClient()
            mock_client.analyze_text.return_value = api_response
            mock_client.extract_generated_text.return_value = f"Analysis result for {analysis_type}"
            mock_client.extract_usage_info.return_value = {}
            
            @asynccontextmanager
            async def mock_get_client():
                yield mock_client
            
            gemini_service._get_client = mock_get_client
            
            response = await gemini_service.analyze_text(request)
            
            assert f"Analysis result for {analysis_type}" in response.analysis


class TestServiceHelperMethods:
    """测试服务辅助方法"""
    
    def test_build_generation_request(self, gemini_service):
        """测试构建生成请求"""
        request = TextGenerationRequest(
            prompt="Test prompt",
            max_tokens=500,
            temperature=0.8,
            top_p=0.9,
            top_k=50,
            stop_sequences=["END"]
        )
        
        api_request = gemini_service._build_generation_request(request)
        
        assert "contents" in api_request
        assert "generationConfig" in api_request
        assert "safetySettings" in api_request
        
        config = api_request["generationConfig"]
        assert config["maxOutputTokens"] == 500
        assert config["temperature"] == 0.8
        assert config["topP"] == 0.9
        assert config["topK"] == 50
        assert config["stopSequences"] == ["END"]
        
        # 验证内容格式
        assert api_request["contents"][0]["parts"][0]["text"] == "Test prompt"
    
    def test_build_chat_request(self, gemini_service):
        """测试构建对话请求"""
        messages = [
            GeminiMessage(role=MessageRole.USER, content="Hello"),
            GeminiMessage(role=MessageRole.MODEL, content="Hi!")
        ]
        
        request = ChatCompletionRequest(
            messages=messages,
            system_instruction="Be helpful",
            max_tokens=300,
            temperature=0.7
        )
        
        api_request = gemini_service._build_chat_request(request)
        
        assert "contents" in api_request
        assert "generationConfig" in api_request
        assert "systemInstruction" in api_request
        assert "safetySettings" in api_request
        
        # 验证消息转换
        assert len(api_request["contents"]) == 2
        assert api_request["contents"][0]["role"] == "user"
        assert api_request["contents"][0]["parts"][0]["text"] == "Hello"
        
        # 验证系统指令
        assert api_request["systemInstruction"]["parts"][0]["text"] == "Be helpful"
    
    def test_build_analysis_prompt(self, gemini_service):
        """测试构建分析提示"""
        request = TextAnalysisRequest(
            text="Sample text for analysis",
            analysis_type="sentiment",
            language="en"
        )
        
        prompt = gemini_service._build_analysis_prompt(request)
        
        assert "情感倾向" in prompt  # 情感分析提示
        assert "Sample text for analysis" in prompt
        assert "en" in prompt  # 语言提示
        assert "JSON格式" in prompt  # 输出格式要求
    
    def test_build_analysis_prompt_different_types(self, gemini_service):
        """测试不同类型的分析提示"""
        request = TextAnalysisRequest(
            text="Test text",
            analysis_type="summarize"
        )
        
        prompt = gemini_service._build_analysis_prompt(request)
        assert "摘要" in prompt
        
        request.analysis_type = "keywords"
        prompt = gemini_service._build_analysis_prompt(request)
        assert "关键词" in prompt


class TestServiceCleanup:
    """测试服务清理"""
    
    @pytest.mark.asyncio
    async def test_service_close(self, gemini_service):
        """测试服务关闭"""
        mock_client = AsyncMock()
        gemini_service._client = mock_client
        
        await gemini_service.close()
        
        mock_client.close.assert_called_once()
        assert gemini_service._client is None
    
    @pytest.mark.asyncio
    async def test_service_close_no_client(self, gemini_service):
        """测试没有客户端时的关闭"""
        await gemini_service.close()
        # 不应抛出异常


if __name__ == "__main__":
    pytest.main([__file__, "-v"])