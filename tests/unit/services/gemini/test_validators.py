"""
测试 Gemini 参数验证器
"""

import pytest
from src.gemini_kling_mcp.exceptions import ValidationError
from src.gemini_kling_mcp.services.gemini.validators import (
    validate_model_name,
    validate_prompt_content,
    validate_generation_parameters,
    validate_messages,
    validate_stop_sequences,
    validate_analysis_type,
    validate_safety_settings,
    validate_batch_prompts,
    validate_text_generation_request,
    validate_chat_completion_request,
    validate_text_analysis_request
)
from src.gemini_kling_mcp.services.gemini.models import GeminiModel


class TestValidateModelName:
    """测试模型名称验证"""
    
    def test_valid_string_model(self):
        """测试有效的字符串模型"""
        result = validate_model_name("gemini-1.5-flash-002")
        assert result == "gemini-1.5-flash-002"
    
    def test_valid_enum_model(self):
        """测试有效的枚举模型"""
        result = validate_model_name(GeminiModel.GEMINI_15_PRO)
        assert result == "gemini-1.5-pro-002"
    
    def test_invalid_string_model(self):
        """测试无效的字符串模型"""
        with pytest.raises(ValidationError) as exc_info:
            validate_model_name("invalid-model")
        
        assert "不支持的模型" in str(exc_info.value)
        assert "supported_models" in exc_info.value.details
    
    def test_invalid_type_model(self):
        """测试无效类型的模型"""
        with pytest.raises(ValidationError) as exc_info:
            validate_model_name(123)
        
        assert "模型参数类型错误" in str(exc_info.value)


class TestValidatePromptContent:
    """测试提示内容验证"""
    
    def test_valid_prompt(self):
        """测试有效提示"""
        validate_prompt_content("This is a valid prompt")
        # 不应抛出异常
    
    def test_empty_prompt(self):
        """测试空提示"""
        with pytest.raises(ValidationError) as exc_info:
            validate_prompt_content("")
        
        assert "提示内容不能为空" in str(exc_info.value)
    
    def test_whitespace_only_prompt(self):
        """测试只有空白字符的提示"""
        with pytest.raises(ValidationError) as exc_info:
            validate_prompt_content("   \n\t  ")
        
        assert "提示内容不能为空" in str(exc_info.value)
    
    def test_non_string_prompt(self):
        """测试非字符串提示"""
        with pytest.raises(ValidationError) as exc_info:
            validate_prompt_content(123)
        
        assert "提示必须是字符串类型" in str(exc_info.value)
    
    def test_very_long_prompt(self):
        """测试过长提示"""
        long_prompt = "x" * 1000001  # 超过1M字符
        
        with pytest.raises(ValidationError) as exc_info:
            validate_prompt_content(long_prompt)
        
        assert "提示内容过长" in str(exc_info.value)
    
    def test_harmful_content_detection(self):
        """测试有害内容检测"""
        harmful_prompts = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "data:text/html,<script>alert('xss')</script>"
        ]
        
        for harmful_prompt in harmful_prompts:
            with pytest.raises(ValidationError) as exc_info:
                validate_prompt_content(harmful_prompt)
            
            assert "可能的有害代码" in str(exc_info.value)


class TestValidateGenerationParameters:
    """测试生成参数验证"""
    
    def test_valid_parameters(self):
        """测试有效参数"""
        validate_generation_parameters(
            max_tokens=1000,
            temperature=0.7,
            top_p=0.9,
            top_k=50
        )
        # 不应抛出异常
    
    def test_none_parameters(self):
        """测试None参数"""
        validate_generation_parameters()
        # 不应抛出异常
    
    def test_invalid_max_tokens_type(self):
        """测试无效max_tokens类型"""
        with pytest.raises(ValidationError) as exc_info:
            validate_generation_parameters(max_tokens="1000")
        
        assert "max_tokens 必须是整数" in str(exc_info.value)
    
    def test_invalid_max_tokens_value(self):
        """测试无效max_tokens值"""
        with pytest.raises(ValidationError) as exc_info:
            validate_generation_parameters(max_tokens=0)
        
        assert "max_tokens 必须大于0" in str(exc_info.value)
        
        with pytest.raises(ValidationError) as exc_info:
            validate_generation_parameters(max_tokens=10000)
        
        assert "max_tokens 不能超过8192" in str(exc_info.value)
    
    def test_invalid_temperature_type(self):
        """测试无效temperature类型"""
        with pytest.raises(ValidationError) as exc_info:
            validate_generation_parameters(temperature="0.7")
        
        assert "temperature 必须是数字" in str(exc_info.value)
    
    def test_invalid_temperature_range(self):
        """测试无效temperature范围"""
        with pytest.raises(ValidationError) as exc_info:
            validate_generation_parameters(temperature=-0.1)
        
        assert "temperature 必须在0.0-2.0之间" in str(exc_info.value)
        
        with pytest.raises(ValidationError) as exc_info:
            validate_generation_parameters(temperature=2.1)
        
        assert "temperature 必须在0.0-2.0之间" in str(exc_info.value)
    
    def test_invalid_top_p_range(self):
        """测试无效top_p范围"""
        with pytest.raises(ValidationError) as exc_info:
            validate_generation_parameters(top_p=-0.1)
        
        assert "top_p 必须在0.0-1.0之间" in str(exc_info.value)
        
        with pytest.raises(ValidationError) as exc_info:
            validate_generation_parameters(top_p=1.1)
        
        assert "top_p 必须在0.0-1.0之间" in str(exc_info.value)
    
    def test_invalid_top_k_range(self):
        """测试无效top_k范围"""
        with pytest.raises(ValidationError) as exc_info:
            validate_generation_parameters(top_k=0)
        
        assert "top_k 必须在1-100之间" in str(exc_info.value)
        
        with pytest.raises(ValidationError) as exc_info:
            validate_generation_parameters(top_k=101)
        
        assert "top_k 必须在1-100之间" in str(exc_info.value)


class TestValidateMessages:
    """测试消息验证"""
    
    def test_valid_messages(self):
        """测试有效消息"""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "model", "content": "Hi there!"}
        ]
        
        validate_messages(messages)
        # 不应抛出异常
    
    def test_empty_messages(self):
        """测试空消息列表"""
        with pytest.raises(ValidationError) as exc_info:
            validate_messages([])
        
        assert "消息列表不能为空" in str(exc_info.value)
    
    def test_non_list_messages(self):
        """测试非列表消息"""
        with pytest.raises(ValidationError) as exc_info:
            validate_messages("not a list")
        
        assert "消息必须是列表类型" in str(exc_info.value)
    
    def test_too_many_messages(self):
        """测试过多消息"""
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(101)]
        
        with pytest.raises(ValidationError) as exc_info:
            validate_messages(messages)
        
        assert "消息数量过多" in str(exc_info.value)
    
    def test_invalid_message_format(self):
        """测试无效消息格式"""
        with pytest.raises(ValidationError) as exc_info:
            validate_messages([{"role": "user"}])  # 缺少content
        
        assert "缺少content字段" in str(exc_info.value)
        
        with pytest.raises(ValidationError) as exc_info:
            validate_messages([{"content": "Hello"}])  # 缺少role
        
        assert "缺少role字段" in str(exc_info.value)
    
    def test_invalid_role(self):
        """测试无效角色"""
        with pytest.raises(ValidationError) as exc_info:
            validate_messages([{"role": "invalid", "content": "Hello"}])
        
        assert "role无效" in str(exc_info.value)
    
    def test_empty_content(self):
        """测试空内容"""
        with pytest.raises(ValidationError) as exc_info:
            validate_messages([{"role": "user", "content": ""}])
        
        assert "content不能为空" in str(exc_info.value)
    
    def test_very_long_message(self):
        """测试过长消息"""
        long_content = "x" * 100001  # 超过100K字符
        
        with pytest.raises(ValidationError) as exc_info:
            validate_messages([{"role": "user", "content": long_content}])
        
        assert "内容过长" in str(exc_info.value)


class TestValidateStopSequences:
    """测试停止序列验证"""
    
    def test_valid_stop_sequences(self):
        """测试有效停止序列"""
        validate_stop_sequences(["END", "STOP", "\n"])
        # 不应抛出异常
    
    def test_none_stop_sequences(self):
        """测试None停止序列"""
        validate_stop_sequences(None)
        # 不应抛出异常
    
    def test_non_list_stop_sequences(self):
        """测试非列表停止序列"""
        with pytest.raises(ValidationError) as exc_info:
            validate_stop_sequences("not a list")
        
        assert "停止序列必须是列表类型" in str(exc_info.value)
    
    def test_too_many_stop_sequences(self):
        """测试过多停止序列"""
        sequences = [f"SEQ{i}" for i in range(21)]
        
        with pytest.raises(ValidationError) as exc_info:
            validate_stop_sequences(sequences)
        
        assert "停止序列过多" in str(exc_info.value)
    
    def test_empty_stop_sequence(self):
        """测试空停止序列"""
        with pytest.raises(ValidationError) as exc_info:
            validate_stop_sequences(["VALID", ""])
        
        assert "不能为空" in str(exc_info.value)
    
    def test_very_long_stop_sequence(self):
        """测试过长停止序列"""
        long_sequence = "x" * 101
        
        with pytest.raises(ValidationError) as exc_info:
            validate_stop_sequences([long_sequence])
        
        assert "过长" in str(exc_info.value)


class TestValidateAnalysisType:
    """测试分析类型验证"""
    
    def test_valid_analysis_types(self):
        """测试有效分析类型"""
        valid_types = [
            "general", "sentiment", "summarize", "keywords",
            "entities", "classify", "translate", "grammar"
        ]
        
        for analysis_type in valid_types:
            validate_analysis_type(analysis_type)
            # 不应抛出异常
    
    def test_invalid_analysis_type(self):
        """测试无效分析类型"""
        with pytest.raises(ValidationError) as exc_info:
            validate_analysis_type("invalid_type")
        
        assert "不支持的分析类型" in str(exc_info.value)
    
    def test_non_string_analysis_type(self):
        """测试非字符串分析类型"""
        with pytest.raises(ValidationError) as exc_info:
            validate_analysis_type(123)
        
        assert "分析类型必须是字符串" in str(exc_info.value)


class TestValidateBatchPrompts:
    """测试批量提示验证"""
    
    def test_valid_batch_prompts(self):
        """测试有效批量提示"""
        prompts = ["Prompt 1", "Prompt 2", "Prompt 3"]
        validate_batch_prompts(prompts)
        # 不应抛出异常
    
    def test_empty_batch_prompts(self):
        """测试空批量提示"""
        with pytest.raises(ValidationError) as exc_info:
            validate_batch_prompts([])
        
        assert "提示列表不能为空" in str(exc_info.value)
    
    def test_too_many_batch_prompts(self):
        """测试过多批量提示"""
        prompts = [f"Prompt {i}" for i in range(11)]
        
        with pytest.raises(ValidationError) as exc_info:
            validate_batch_prompts(prompts)
        
        assert "批次大小过大" in str(exc_info.value)
    
    def test_invalid_prompt_in_batch(self):
        """测试批次中的无效提示"""
        prompts = ["Valid prompt", ""]  # 第二个为空
        
        with pytest.raises(ValidationError) as exc_info:
            validate_batch_prompts(prompts)
        
        assert "提示1验证失败" in str(exc_info.value)


class TestComprehensiveValidators:
    """测试综合验证函数"""
    
    def test_valid_text_generation_request(self):
        """测试有效文本生成请求"""
        validate_text_generation_request(
            prompt="Generate text",
            model="gemini-1.5-flash-002",
            max_tokens=1000,
            temperature=0.7
        )
        # 不应抛出异常
    
    def test_valid_chat_completion_request(self):
        """测试有效对话完成请求"""
        messages = [{"role": "user", "content": "Hello"}]
        validate_chat_completion_request(
            messages=messages,
            model="gemini-1.5-flash-002"
        )
        # 不应抛出异常
    
    def test_valid_text_analysis_request(self):
        """测试有效文本分析请求"""
        validate_text_analysis_request(
            text="Analyze this text",
            model="gemini-1.5-flash-002",
            analysis_type="sentiment"
        )
        # 不应抛出异常


if __name__ == "__main__":
    pytest.main([__file__, "-v"])