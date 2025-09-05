"""
Gemini 服务集成测试

测试与真实 Gemini API 的集成（需要有效的 API 密钥）
"""

import pytest
import os
from unittest.mock import patch

from src.gemini_kling_mcp.config import GeminiConfig
from src.gemini_kling_mcp.services.gemini import GeminiService
from src.gemini_kling_mcp.services.gemini.models import (
    TextGenerationRequest, ChatCompletionRequest, TextAnalysisRequest,
    GeminiMessage, MessageRole, GeminiModel
)
from src.gemini_kling_mcp.exceptions import ToolExecutionError


@pytest.fixture
def gemini_config():
    """创建测试配置"""
    api_key = os.getenv("GEMINI_API_KEY", "test-api-key")
    return GeminiConfig(
        api_key=api_key,
        base_url="https://gptproto.com",
        timeout=30,
        max_retries=2
    )


@pytest.fixture
def gemini_service(gemini_config):
    """创建测试服务"""
    return GeminiService(gemini_config)


@pytest.fixture
def skip_if_no_api_key():
    """如果没有API密钥则跳过测试"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "test-api-key":
        pytest.skip("需要真实的GEMINI_API_KEY环境变量来运行集成测试")


class TestGeminiServiceIntegration:
    """Gemini服务集成测试"""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_text_generation_integration(self, gemini_service, skip_if_no_api_key):
        """测试文本生成集成"""
        request = TextGenerationRequest(
            prompt="Write a short poem about artificial intelligence.",
            model=GeminiModel.GEMINI_15_FLASH,
            max_tokens=200,
            temperature=0.7
        )
        
        response = await gemini_service.generate_text(request)
        
        # 验证响应结构
        assert response.text is not None
        assert len(response.text) > 0
        assert response.model == GeminiModel.GEMINI_15_FLASH.value
        assert response.finish_reason in ["stop", "length", "content_filter"]
        
        # 验证使用信息
        if response.usage:
            assert "total_tokens" in response.usage
            assert response.usage["total_tokens"] > 0
        
        print(f"Generated text: {response.text[:100]}...")
        print(f"Model: {response.model}")
        print(f"Usage: {response.usage}")
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_chat_completion_integration(self, gemini_service, skip_if_no_api_key):
        """测试对话完成集成"""
        messages = [
            GeminiMessage(role=MessageRole.USER, content="Hello! What is machine learning?"),
        ]
        
        request = ChatCompletionRequest(
            messages=messages,
            model=GeminiModel.GEMINI_15_FLASH,
            max_tokens=300,
            temperature=0.5,
            system_instruction="You are a helpful AI assistant that explains technical concepts clearly."
        )
        
        response = await gemini_service.complete_chat(request)
        
        # 验证响应
        assert response.message.role == MessageRole.MODEL
        assert len(response.message.content) > 0
        assert response.model == GeminiModel.GEMINI_15_FLASH.value
        
        print(f"Chat response: {response.message.content[:100]}...")
        print(f"Finish reason: {response.finish_reason}")
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_text_analysis_integration(self, gemini_service, skip_if_no_api_key):
        """测试文本分析集成"""
        request = TextAnalysisRequest(
            text="I absolutely love this new smartphone! The camera quality is amazing and the battery life is fantastic.",
            model=GeminiModel.GEMINI_15_FLASH,
            analysis_type="sentiment",
            language="en"
        )
        
        response = await gemini_service.analyze_text(request)
        
        # 验证响应
        assert len(response.analysis) > 0
        assert response.model == GeminiModel.GEMINI_15_FLASH.value
        
        print(f"Analysis: {response.analysis[:200]}...")
        
        # 尝试解析结构化结果
        if response.sentiment:
            print(f"Sentiment: {response.sentiment}")
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_multiple_models_integration(self, gemini_service, skip_if_no_api_key):
        """测试不同模型的集成"""
        prompt = "Explain quantum computing in one sentence."
        
        models_to_test = [
            GeminiModel.GEMINI_15_FLASH,
            # GeminiModel.GEMINI_15_PRO,  # 可能需要更高级的API访问
        ]
        
        for model in models_to_test:
            request = TextGenerationRequest(
                prompt=prompt,
                model=model,
                max_tokens=100,
                temperature=0.3
            )
            
            response = await gemini_service.generate_text(request)
            
            assert response.text is not None
            assert len(response.text) > 0
            assert response.model == model.value
            
            print(f"Model {model.value}: {response.text[:80]}...")
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_long_conversation_integration(self, gemini_service, skip_if_no_api_key):
        """测试长对话集成"""
        messages = [
            GeminiMessage(role=MessageRole.USER, content="What is Python programming?"),
            GeminiMessage(role=MessageRole.MODEL, content="Python is a high-level, interpreted programming language known for its simplicity and readability."),
            GeminiMessage(role=MessageRole.USER, content="What are its main advantages?"),
            GeminiMessage(role=MessageRole.MODEL, content="Python's main advantages include easy syntax, extensive libraries, cross-platform compatibility, and strong community support."),
            GeminiMessage(role=MessageRole.USER, content="Can you give me a simple example?")
        ]
        
        request = ChatCompletionRequest(
            messages=messages,
            model=GeminiModel.GEMINI_15_FLASH,
            max_tokens=200,
            temperature=0.4
        )
        
        response = await gemini_service.complete_chat(request)
        
        assert response.message.content is not None
        assert len(response.message.content) > 0
        assert "python" in response.message.content.lower() or "print" in response.message.content.lower()
        
        print(f"Example response: {response.message.content}")
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_error_handling_integration(self, gemini_config):
        """测试错误处理集成"""
        # 使用无效的API密钥
        invalid_config = GeminiConfig(
            api_key="invalid-key",
            base_url=gemini_config.base_url,
            timeout=gemini_config.timeout,
            max_retries=1
        )
        
        service = GeminiService(invalid_config)
        
        request = TextGenerationRequest(
            prompt="Test with invalid key",
            max_tokens=50
        )
        
        with pytest.raises(ToolExecutionError) as exc_info:
            await service.generate_text(request)
        
        assert "文本生成失败" in str(exc_info.value)
        print(f"Expected error: {exc_info.value}")


class TestGeminiToolsIntegration:
    """Gemini工具集成测试"""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_text_generation_tool_integration(self, skip_if_no_api_key):
        """测试文本生成工具集成"""
        from src.gemini_kling_mcp.tools.text_generation import generate_text
        
        result = await generate_text(
            prompt="Write a haiku about technology",
            model="gemini-1.5-flash-002",
            max_tokens=100,
            temperature=0.8
        )
        
        assert result["success"] is True
        assert len(result["text"]) > 0
        assert result["model"] == "gemini-1.5-flash-002"
        
        print(f"Tool result: {result['text']}")
        print(f"Usage: {result.get('usage', {})}")
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_chat_completion_tool_integration(self, skip_if_no_api_key):
        """测试对话完成工具集成"""
        from src.gemini_kling_mcp.tools.chat_completion import chat_completion
        
        messages = [
            {"role": "user", "content": "What is the capital of France?"}
        ]
        
        result = await chat_completion(
            messages=messages,
            model="gemini-1.5-flash-002",
            max_tokens=100
        )
        
        assert result["success"] is True
        assert result["message"]["role"] == "model"
        assert len(result["message"]["content"]) > 0
        assert "paris" in result["message"]["content"].lower()
        
        print(f"Chat result: {result['message']['content']}")
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_text_analysis_tool_integration(self, skip_if_no_api_key):
        """测试文本分析工具集成"""
        from src.gemini_kling_mcp.tools.text_analysis import analyze_text
        
        result = await analyze_text(
            text="This movie was absolutely terrible! The plot was confusing and the acting was awful.",
            analysis_type="sentiment",
            model="gemini-1.5-flash-002"
        )
        
        assert result["success"] is True
        assert len(result["analysis"]) > 0
        assert result["analysis_type"] == "sentiment"
        
        print(f"Analysis result: {result['analysis']}")
        
        # 检查是否检测到负面情绪
        analysis_text = result["analysis"].lower()
        assert any(word in analysis_text for word in ["negative", "消极", "负面", "不好"])
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_batch_generation_tool_integration(self, skip_if_no_api_key):
        """测试批量生成工具集成"""
        from src.gemini_kling_mcp.tools.text_generation import generate_text_batch
        
        prompts = [
            "Write one sentence about cats",
            "Write one sentence about dogs", 
            "Write one sentence about birds"
        ]
        
        result = await generate_text_batch(
            prompts=prompts,
            model="gemini-1.5-flash-002",
            max_tokens=50,
            concurrent_limit=2
        )
        
        assert result["success"] is True
        assert len(result["results"]) == 3
        assert result["summary"]["total"] == 3
        assert result["summary"]["successful"] >= 2  # 允许部分失败
        
        # 验证每个结果
        for i, res in enumerate(result["results"]):
            if res["success"]:
                assert len(res["text"]) > 0
                assert res["index"] == i
                print(f"Batch result {i}: {res['text']}")


class TestPerformanceIntegration:
    """性能集成测试"""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_concurrent_requests(self, gemini_service, skip_if_no_api_key):
        """测试并发请求性能"""
        import asyncio
        import time
        
        async def single_request(prompt_suffix):
            request = TextGenerationRequest(
                prompt=f"Write a brief sentence about {prompt_suffix}",
                max_tokens=50,
                temperature=0.5
            )
            return await gemini_service.generate_text(request)
        
        # 并发执行多个请求
        start_time = time.time()
        tasks = [
            single_request(f"topic {i}")
            for i in range(3)  # 适度的并发数，避免API限制
        ]
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # 验证结果
        successful_responses = [r for r in responses if not isinstance(r, Exception)]
        assert len(successful_responses) >= 2  # 允许部分失败
        
        for response in successful_responses:
            assert len(response.text) > 0
        
        print(f"Concurrent requests completed in {end_time - start_time:.2f} seconds")
        print(f"Success rate: {len(successful_responses)}/{len(tasks)}")
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_large_text_analysis(self, gemini_service, skip_if_no_api_key):
        """测试大文本分析性能"""
        large_text = """
        Artificial Intelligence (AI) represents one of the most significant technological advances of our time. 
        It encompasses machine learning, deep learning, natural language processing, computer vision, and robotics. 
        AI systems can process vast amounts of data, recognize patterns, and make decisions with minimal human intervention.
        
        The applications of AI are diverse and growing rapidly. In healthcare, AI assists in medical diagnosis, 
        drug discovery, and personalized treatment plans. In finance, it powers fraud detection, algorithmic trading, 
        and risk assessment. Transportation benefits from AI through autonomous vehicles and traffic optimization.
        
        However, AI development also presents challenges. Ethical considerations around bias, privacy, and job 
        displacement need careful attention. The development of artificial general intelligence (AGI) raises 
        questions about control and alignment with human values.
        
        Despite these challenges, AI continues to evolve and improve human capabilities across numerous domains.
        """ * 2  # 扩大文本以测试处理能力
        
        import time
        start_time = time.time()
        
        request = TextAnalysisRequest(
            text=large_text,
            analysis_type="summarize",
            max_tokens=300
        )
        
        response = await gemini_service.analyze_text(request)
        
        end_time = time.time()
        
        assert len(response.analysis) > 0
        assert response.usage is not None
        
        print(f"Large text analysis completed in {end_time - start_time:.2f} seconds")
        print(f"Input length: {len(large_text)} characters")
        print(f"Summary length: {len(response.analysis)} characters")
        print(f"Summary: {response.analysis[:200]}...")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])