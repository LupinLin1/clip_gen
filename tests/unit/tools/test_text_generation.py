"""
测试 Gemini 文本生成工具
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from src.gemini_kling_mcp.tools.text_generation import (
    generate_text,
    generate_text_batch,
    cleanup_text_generation
)


class TestTextGenerationTool:
    """测试文本生成工具"""
    
    @pytest.mark.asyncio
    async def test_generate_text_success(self):
        """测试成功生成文本"""
        # 模拟服务响应
        mock_response = Mock()
        mock_response.text = "Generated text content"
        mock_response.model = "gemini-1.5-flash-002"
        mock_response.finish_reason = "STOP"
        mock_response.usage = {"total_tokens": 50}
        mock_response.safety_ratings = []
        
        mock_service = AsyncMock()
        mock_service.generate_text.return_value = mock_response
        
        # 模拟服务获取
        with patch('src.gemini_kling_mcp.tools.text_generation._get_service', return_value=mock_service):
            result = await generate_text(
                prompt="Generate a story",
                model="gemini-1.5-flash-002",
                max_tokens=1000,
                temperature=0.7
            )
        
        # 验证结果
        assert result["success"] is True
        assert result["text"] == "Generated text content"
        assert result["model"] == "gemini-1.5-flash-002"
        assert result["finish_reason"] == "STOP"
        assert result["usage"]["total_tokens"] == 50
        
        # 验证服务调用
        mock_service.generate_text.assert_called_once()
        call_args = mock_service.generate_text.call_args[0][0]
        assert call_args.prompt == "Generate a story"
        assert call_args.max_tokens == 1000
        assert call_args.temperature == 0.7
    
    @pytest.mark.asyncio
    async def test_generate_text_with_optional_parameters(self):
        """测试带可选参数的文本生成"""
        mock_response = Mock()
        mock_response.text = "Generated text"
        mock_response.model = "gemini-1.5-pro-002"
        mock_response.finish_reason = "STOP"
        mock_response.usage = {}
        mock_response.safety_ratings = None
        
        mock_service = AsyncMock()
        mock_service.generate_text.return_value = mock_response
        
        with patch('src.gemini_kling_mcp.tools.text_generation._get_service', return_value=mock_service):
            result = await generate_text(
                prompt="Test prompt",
                model="gemini-1.5-pro-002",
                max_tokens=2000,
                temperature=0.9,
                top_p=0.8,
                top_k=50,
                stop_sequences=["END", "STOP"]
            )
        
        assert result["success"] is True
        assert result["text"] == "Generated text"
        
        # 验证参数传递
        call_args = mock_service.generate_text.call_args[0][0]
        assert call_args.top_p == 0.8
        assert call_args.top_k == 50
        assert call_args.stop_sequences == ["END", "STOP"]
    
    @pytest.mark.asyncio
    async def test_generate_text_with_safety_ratings(self):
        """测试包含安全评级的生成"""
        mock_response = Mock()
        mock_response.text = "Safe generated text"
        mock_response.model = "gemini-1.5-flash-002"
        mock_response.finish_reason = "STOP"
        mock_response.usage = {}
        mock_response.safety_ratings = [
            {"category": "HARASSMENT", "probability": "LOW"}
        ]
        
        mock_service = AsyncMock()
        mock_service.generate_text.return_value = mock_response
        
        with patch('src.gemini_kling_mcp.tools.text_generation._get_service', return_value=mock_service):
            result = await generate_text(prompt="Safe prompt")
        
        assert result["success"] is True
        assert "safety_ratings" in result
        assert result["safety_ratings"][0]["category"] == "HARASSMENT"
    
    @pytest.mark.asyncio
    async def test_generate_text_error_handling(self):
        """测试错误处理"""
        mock_service = AsyncMock()
        mock_service.generate_text.side_effect = ValueError("Service error")
        
        with patch('src.gemini_kling_mcp.tools.text_generation._get_service', return_value=mock_service):
            result = await generate_text(prompt="Test prompt")
        
        assert result["success"] is False
        assert result["text"] == ""
        assert "Service error" in result["error"]
    
    @pytest.mark.asyncio
    async def test_generate_text_default_parameters(self):
        """测试默认参数"""
        mock_response = Mock()
        mock_response.text = "Default generated text"
        mock_response.model = "gemini-1.5-flash-002"
        mock_response.finish_reason = "STOP"
        mock_response.usage = {}
        mock_response.safety_ratings = []
        
        mock_service = AsyncMock()
        mock_service.generate_text.return_value = mock_response
        
        with patch('src.gemini_kling_mcp.tools.text_generation._get_service', return_value=mock_service):
            result = await generate_text(prompt="Test with defaults")
        
        # 验证默认参数
        call_args = mock_service.generate_text.call_args[0][0]
        assert call_args.model.value == "gemini-1.5-flash-002"
        assert call_args.max_tokens == 1000
        assert call_args.temperature == 0.7
        assert call_args.top_p == 0.95


class TestBatchTextGeneration:
    """测试批量文本生成工具"""
    
    @pytest.mark.asyncio
    async def test_generate_text_batch_success(self):
        """测试成功批量生成"""
        prompts = [
            "Generate story 1",
            "Generate story 2", 
            "Generate story 3"
        ]
        
        # 模拟每个提示的响应
        def create_mock_response(index):
            mock_response = Mock()
            mock_response.text = f"Generated text {index + 1}"
            mock_response.model = "gemini-1.5-flash-002"
            mock_response.finish_reason = "STOP"
            mock_response.usage = {"total_tokens": 20 + index * 5}
            return mock_response
        
        mock_service = AsyncMock()
        mock_service.generate_text.side_effect = [
            create_mock_response(i) for i in range(len(prompts))
        ]
        
        with patch('src.gemini_kling_mcp.tools.text_generation._get_service', return_value=mock_service):
            result = await generate_text_batch(
                prompts=prompts,
                model="gemini-1.5-flash-002",
                max_tokens=500,
                temperature=0.8,
                concurrent_limit=2
            )
        
        # 验证结果
        assert result["success"] is True
        assert len(result["results"]) == 3
        assert result["summary"]["total"] == 3
        assert result["summary"]["successful"] == 3
        assert result["summary"]["failed"] == 0
        
        # 验证每个结果
        for i, res in enumerate(result["results"]):
            assert res["success"] is True
            assert res["index"] == i
            assert res["prompt"] == prompts[i]
            assert res["text"] == f"Generated text {i + 1}"
        
        # 验证服务调用次数
        assert mock_service.generate_text.call_count == 3
    
    @pytest.mark.asyncio
    async def test_generate_text_batch_partial_failure(self):
        """测试部分失败的批量生成"""
        prompts = ["Prompt 1", "Prompt 2", "Prompt 3"]
        
        # 第二个提示失败
        mock_responses = [
            Mock(text="Success 1", model="test", finish_reason="STOP", usage={}),
            ValueError("API Error"),  # 失败
            Mock(text="Success 3", model="test", finish_reason="STOP", usage={})
        ]
        
        mock_service = AsyncMock()
        mock_service.generate_text.side_effect = mock_responses
        
        with patch('src.gemini_kling_mcp.tools.text_generation._get_service', return_value=mock_service):
            result = await generate_text_batch(prompts=prompts)
        
        assert result["success"] is True
        assert result["summary"]["total"] == 3
        assert result["summary"]["successful"] == 2
        assert result["summary"]["failed"] == 1
        
        # 验证失败的结果
        failed_result = next(r for r in result["results"] if not r["success"])
        assert failed_result["index"] == 1
        assert "API Error" in failed_result["error"]
    
    @pytest.mark.asyncio
    async def test_generate_text_batch_empty_prompts(self):
        """测试空提示列表"""
        with patch('src.gemini_kling_mcp.tools.text_generation._get_service'):
            result = await generate_text_batch(prompts=[])
        
        assert result["success"] is False
        assert "error" in result
    
    @pytest.mark.asyncio
    async def test_generate_text_batch_concurrent_limit(self):
        """测试并发限制"""
        prompts = [f"Prompt {i}" for i in range(5)]
        
        mock_response = Mock()
        mock_response.text = "Generated"
        mock_response.model = "test"
        mock_response.finish_reason = "STOP"
        mock_response.usage = {}
        
        mock_service = AsyncMock()
        mock_service.generate_text.return_value = mock_response
        
        with patch('src.gemini_kling_mcp.tools.text_generation._get_service', return_value=mock_service):
            # 设置较小的并发限制
            result = await generate_text_batch(
                prompts=prompts,
                concurrent_limit=2
            )
        
        assert result["success"] is True
        assert result["summary"]["total"] == 5
        assert result["summary"]["successful"] == 5
    
    @pytest.mark.asyncio
    async def test_generate_text_batch_service_error(self):
        """测试服务获取错误"""
        with patch('src.gemini_kling_mcp.tools.text_generation._get_service', side_effect=Exception("Service unavailable")):
            result = await generate_text_batch(prompts=["Test"])
        
        assert result["success"] is False
        assert "Service unavailable" in result["error"]


class TestServiceManagement:
    """测试服务管理"""
    
    @pytest.mark.asyncio
    async def test_service_caching(self):
        """测试服务缓存"""
        mock_service = AsyncMock()
        
        with patch('src.gemini_kling_mcp.services.gemini.GeminiService', return_value=mock_service):
            # 导入模块以获取全局变量
            import src.gemini_kling_mcp.tools.text_generation as text_gen_module
            
            # 第一次调用
            service1 = await text_gen_module._get_service()
            # 第二次调用
            service2 = await text_gen_module._get_service()
            
            # 应该返回同一个实例
            assert service1 is service2
    
    @pytest.mark.asyncio
    async def test_cleanup_text_generation(self):
        """测试清理函数"""
        import src.gemini_kling_mcp.tools.text_generation as text_gen_module
        
        # 设置模拟服务
        mock_service = AsyncMock()
        text_gen_module._gemini_service = mock_service
        
        await cleanup_text_generation()
        
        # 验证清理
        mock_service.close.assert_called_once()
        assert text_gen_module._gemini_service is None
    
    @pytest.mark.asyncio
    async def test_cleanup_no_service(self):
        """测试没有服务时的清理"""
        import src.gemini_kling_mcp.tools.text_generation as text_gen_module
        
        text_gen_module._gemini_service = None
        
        await cleanup_text_generation()
        # 不应抛出异常


class TestParameterValidation:
    """测试参数验证"""
    
    @pytest.mark.asyncio
    async def test_invalid_model_parameter(self):
        """测试无效模型参数"""
        mock_service = AsyncMock()
        mock_service.generate_text.side_effect = ValueError("Invalid model")
        
        with patch('src.gemini_kling_mcp.tools.text_generation._get_service', return_value=mock_service):
            result = await generate_text(
                prompt="Test",
                model="invalid-model"
            )
        
        assert result["success"] is False
        assert "Invalid model" in result["error"]
    
    @pytest.mark.asyncio  
    async def test_temperature_bounds(self):
        """测试温度参数边界"""
        mock_response = Mock()
        mock_response.text = "Test response"
        mock_response.model = "test"
        mock_response.finish_reason = "STOP"
        mock_response.usage = {}
        mock_response.safety_ratings = []
        
        mock_service = AsyncMock()
        mock_service.generate_text.return_value = mock_response
        
        with patch('src.gemini_kling_mcp.tools.text_generation._get_service', return_value=mock_service):
            # 测试边界值
            result = await generate_text(prompt="Test", temperature=0.0)
            assert result["success"] is True
            
            result = await generate_text(prompt="Test", temperature=2.0)
            assert result["success"] is True
    
    @pytest.mark.asyncio
    async def test_max_tokens_validation(self):
        """测试最大令牌数验证"""
        mock_response = Mock()
        mock_response.text = "Test"
        mock_response.model = "test"
        mock_response.finish_reason = "STOP"
        mock_response.usage = {}
        mock_response.safety_ratings = []
        
        mock_service = AsyncMock()
        mock_service.generate_text.return_value = mock_response
        
        with patch('src.gemini_kling_mcp.tools.text_generation._get_service', return_value=mock_service):
            # 测试有效范围
            result = await generate_text(prompt="Test", max_tokens=100)
            assert result["success"] is True
            
            result = await generate_text(prompt="Test", max_tokens=8192)
            assert result["success"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])