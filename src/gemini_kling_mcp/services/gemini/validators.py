"""
Gemini API 参数验证器

提供额外的参数验证功能，补充 Pydantic 模型验证。
"""

import re
from typing import List, Optional, Dict, Any, Union
from ...exceptions import ValidationError
from .models import GeminiModel, GEMINI_MODELS

def validate_model_name(model: Union[str, GeminiModel]) -> str:
    """
    验证模型名称
    
    Args:
        model: 模型名称或枚举值
    
    Returns:
        有效的模型名称字符串
    
    Raises:
        ValidationError: 模型名称无效
    """
    if isinstance(model, GeminiModel):
        return model.value
    
    if isinstance(model, str):
        if model in GEMINI_MODELS:
            return model
        else:
            raise ValidationError(
                f"不支持的模型: {model}",
                details={
                    "provided_model": model,
                    "supported_models": GEMINI_MODELS
                }
            )
    
    raise ValidationError(
        f"模型参数类型错误: {type(model)}",
        details={"expected_types": ["str", "GeminiModel"]}
    )

def validate_prompt_content(prompt: str) -> None:
    """
    验证提示内容
    
    Args:
        prompt: 提示文本
    
    Raises:
        ValidationError: 提示内容无效
    """
    if not isinstance(prompt, str):
        raise ValidationError(
            f"提示必须是字符串类型，获得: {type(prompt)}",
            details={"prompt_type": str(type(prompt))}
        )
    
    if not prompt.strip():
        raise ValidationError(
            "提示内容不能为空",
            details={"prompt_length": len(prompt)}
        )
    
    # 检查提示长度（粗略估计，实际限制由API决定）
    if len(prompt) > 1000000:  # 1M字符
        raise ValidationError(
            f"提示内容过长: {len(prompt)} 字符",
            details={"max_length": 1000000, "actual_length": len(prompt)}
        )
    
    # 检查可能的有害内容标记
    harmful_patterns = [
        r"<script[^>]*>.*?</script>",  # 脚本注入
        r"javascript:",  # JavaScript URL
        r"data:text/html",  # 数据URL
    ]
    
    for pattern in harmful_patterns:
        if re.search(pattern, prompt, re.IGNORECASE | re.DOTALL):
            raise ValidationError(
                "提示内容包含可能的有害代码",
                details={"detected_pattern": pattern}
            )

def validate_generation_parameters(
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None, 
    top_p: Optional[float] = None,
    top_k: Optional[int] = None
) -> None:
    """
    验证生成参数
    
    Args:
        max_tokens: 最大令牌数
        temperature: 温度参数
        top_p: Top-P参数
        top_k: Top-K参数
    
    Raises:
        ValidationError: 参数无效
    """
    if max_tokens is not None:
        if not isinstance(max_tokens, int):
            raise ValidationError(
                f"max_tokens 必须是整数，获得: {type(max_tokens)}",
                details={"value": max_tokens, "type": str(type(max_tokens))}
            )
        
        if max_tokens <= 0:
            raise ValidationError(
                f"max_tokens 必须大于0，获得: {max_tokens}",
                details={"min_value": 1, "actual_value": max_tokens}
            )
        
        if max_tokens > 8192:
            raise ValidationError(
                f"max_tokens 不能超过8192，获得: {max_tokens}",
                details={"max_value": 8192, "actual_value": max_tokens}
            )
    
    if temperature is not None:
        if not isinstance(temperature, (int, float)):
            raise ValidationError(
                f"temperature 必须是数字，获得: {type(temperature)}",
                details={"value": temperature, "type": str(type(temperature))}
            )
        
        if not (0.0 <= temperature <= 2.0):
            raise ValidationError(
                f"temperature 必须在0.0-2.0之间，获得: {temperature}",
                details={"min_value": 0.0, "max_value": 2.0, "actual_value": temperature}
            )
    
    if top_p is not None:
        if not isinstance(top_p, (int, float)):
            raise ValidationError(
                f"top_p 必须是数字，获得: {type(top_p)}",
                details={"value": top_p, "type": str(type(top_p))}
            )
        
        if not (0.0 <= top_p <= 1.0):
            raise ValidationError(
                f"top_p 必须在0.0-1.0之间，获得: {top_p}",
                details={"min_value": 0.0, "max_value": 1.0, "actual_value": top_p}
            )
    
    if top_k is not None:
        if not isinstance(top_k, int):
            raise ValidationError(
                f"top_k 必须是整数，获得: {type(top_k)}",
                details={"value": top_k, "type": str(type(top_k))}
            )
        
        if not (1 <= top_k <= 100):
            raise ValidationError(
                f"top_k 必须在1-100之间，获得: {top_k}",
                details={"min_value": 1, "max_value": 100, "actual_value": top_k}
            )

def validate_messages(messages: List[Dict[str, Any]]) -> None:
    """
    验证对话消息列表
    
    Args:
        messages: 消息列表
    
    Raises:
        ValidationError: 消息格式无效
    """
    if not isinstance(messages, list):
        raise ValidationError(
            f"消息必须是列表类型，获得: {type(messages)}",
            details={"type": str(type(messages))}
        )
    
    if not messages:
        raise ValidationError(
            "消息列表不能为空",
            details={"message_count": 0}
        )
    
    if len(messages) > 100:  # 限制消息数量
        raise ValidationError(
            f"消息数量过多: {len(messages)}，最多支持100条",
            details={"max_count": 100, "actual_count": len(messages)}
        )
    
    valid_roles = {"user", "model"}
    
    for i, message in enumerate(messages):
        if not isinstance(message, dict):
            raise ValidationError(
                f"消息{i}必须是字典类型，获得: {type(message)}",
                details={"message_index": i, "type": str(type(message))}
            )
        
        if "role" not in message:
            raise ValidationError(
                f"消息{i}缺少role字段",
                details={"message_index": i, "message": message}
            )
        
        if "content" not in message:
            raise ValidationError(
                f"消息{i}缺少content字段",
                details={"message_index": i, "message": message}
            )
        
        role = message["role"]
        content = message["content"]
        
        if role not in valid_roles:
            raise ValidationError(
                f"消息{i}的role无效: {role}",
                details={
                    "message_index": i,
                    "invalid_role": role,
                    "valid_roles": list(valid_roles)
                }
            )
        
        if not isinstance(content, str):
            raise ValidationError(
                f"消息{i}的content必须是字符串，获得: {type(content)}",
                details={"message_index": i, "content_type": str(type(content))}
            )
        
        if not content.strip():
            raise ValidationError(
                f"消息{i}的content不能为空",
                details={"message_index": i, "content_length": len(content)}
            )
        
        # 检查单条消息长度
        if len(content) > 100000:  # 100K字符
            raise ValidationError(
                f"消息{i}内容过长: {len(content)} 字符",
                details={
                    "message_index": i,
                    "max_length": 100000,
                    "actual_length": len(content)
                }
            )

def validate_stop_sequences(stop_sequences: Optional[List[str]]) -> None:
    """
    验证停止序列
    
    Args:
        stop_sequences: 停止序列列表
    
    Raises:
        ValidationError: 停止序列无效
    """
    if stop_sequences is None:
        return
    
    if not isinstance(stop_sequences, list):
        raise ValidationError(
            f"停止序列必须是列表类型，获得: {type(stop_sequences)}",
            details={"type": str(type(stop_sequences))}
        )
    
    if len(stop_sequences) > 20:  # 限制停止序列数量
        raise ValidationError(
            f"停止序列过多: {len(stop_sequences)}，最多支持20个",
            details={"max_count": 20, "actual_count": len(stop_sequences)}
        )
    
    for i, sequence in enumerate(stop_sequences):
        if not isinstance(sequence, str):
            raise ValidationError(
                f"停止序列{i}必须是字符串，获得: {type(sequence)}",
                details={"sequence_index": i, "type": str(type(sequence))}
            )
        
        if not sequence:
            raise ValidationError(
                f"停止序列{i}不能为空",
                details={"sequence_index": i}
            )
        
        if len(sequence) > 100:  # 限制单个停止序列长度
            raise ValidationError(
                f"停止序列{i}过长: {len(sequence)} 字符",
                details={
                    "sequence_index": i,
                    "max_length": 100,
                    "actual_length": len(sequence)
                }
            )

def validate_analysis_type(analysis_type: str) -> None:
    """
    验证分析类型
    
    Args:
        analysis_type: 分析类型
    
    Raises:
        ValidationError: 分析类型无效
    """
    valid_types = {
        "general", "sentiment", "summarize", "keywords",
        "entities", "classify", "translate", "grammar"
    }
    
    if not isinstance(analysis_type, str):
        raise ValidationError(
            f"分析类型必须是字符串，获得: {type(analysis_type)}",
            details={"type": str(type(analysis_type))}
        )
    
    if analysis_type not in valid_types:
        raise ValidationError(
            f"不支持的分析类型: {analysis_type}",
            details={
                "invalid_type": analysis_type,
                "valid_types": list(valid_types)
            }
        )

def validate_safety_settings(safety_settings: Optional[List[Dict[str, Any]]]) -> None:
    """
    验证安全设置
    
    Args:
        safety_settings: 安全设置列表
    
    Raises:
        ValidationError: 安全设置无效
    """
    if safety_settings is None:
        return
    
    if not isinstance(safety_settings, list):
        raise ValidationError(
            f"安全设置必须是列表类型，获得: {type(safety_settings)}",
            details={"type": str(type(safety_settings))}
        )
    
    valid_categories = {
        "HARM_CATEGORY_HARASSMENT",
        "HARM_CATEGORY_HATE_SPEECH",
        "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "HARM_CATEGORY_DANGEROUS_CONTENT"
    }
    
    valid_thresholds = {
        "BLOCK_NONE",
        "BLOCK_LOW_AND_ABOVE",
        "BLOCK_MEDIUM_AND_ABOVE", 
        "BLOCK_HIGH_AND_ABOVE"
    }
    
    for i, setting in enumerate(safety_settings):
        if not isinstance(setting, dict):
            raise ValidationError(
                f"安全设置{i}必须是字典类型，获得: {type(setting)}",
                details={"setting_index": i, "type": str(type(setting))}
            )
        
        if "category" not in setting:
            raise ValidationError(
                f"安全设置{i}缺少category字段",
                details={"setting_index": i, "setting": setting}
            )
        
        if "threshold" not in setting:
            raise ValidationError(
                f"安全设置{i}缺少threshold字段",
                details={"setting_index": i, "setting": setting}
            )
        
        category = setting["category"]
        threshold = setting["threshold"]
        
        if category not in valid_categories:
            raise ValidationError(
                f"安全设置{i}的category无效: {category}",
                details={
                    "setting_index": i,
                    "invalid_category": category,
                    "valid_categories": list(valid_categories)
                }
            )
        
        if threshold not in valid_thresholds:
            raise ValidationError(
                f"安全设置{i}的threshold无效: {threshold}",
                details={
                    "setting_index": i,
                    "invalid_threshold": threshold,
                    "valid_thresholds": list(valid_thresholds)
                }
            )

def validate_batch_prompts(prompts: List[str], max_batch_size: int = 10) -> None:
    """
    验证批量提示
    
    Args:
        prompts: 提示列表
        max_batch_size: 最大批次大小
    
    Raises:
        ValidationError: 批量提示无效
    """
    if not isinstance(prompts, list):
        raise ValidationError(
            f"提示列表必须是列表类型，获得: {type(prompts)}",
            details={"type": str(type(prompts))}
        )
    
    if not prompts:
        raise ValidationError(
            "提示列表不能为空",
            details={"prompt_count": 0}
        )
    
    if len(prompts) > max_batch_size:
        raise ValidationError(
            f"批次大小过大: {len(prompts)}，最多支持{max_batch_size}个",
            details={"max_batch_size": max_batch_size, "actual_size": len(prompts)}
        )
    
    for i, prompt in enumerate(prompts):
        try:
            validate_prompt_content(prompt)
        except ValidationError as e:
            raise ValidationError(
                f"提示{i}验证失败: {e.message}",
                details={"prompt_index": i, "original_error": e.details}
            )

# 综合验证函数
def validate_text_generation_request(
    prompt: str,
    model: Union[str, GeminiModel] = "gemini-1.5-flash-002",
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    top_k: Optional[int] = None,
    stop_sequences: Optional[List[str]] = None,
    safety_settings: Optional[List[Dict[str, Any]]] = None
) -> None:
    """
    验证文本生成请求的所有参数
    """
    validate_prompt_content(prompt)
    validate_model_name(model)
    validate_generation_parameters(max_tokens, temperature, top_p, top_k)
    validate_stop_sequences(stop_sequences)
    validate_safety_settings(safety_settings)

def validate_chat_completion_request(
    messages: List[Dict[str, Any]],
    model: Union[str, GeminiModel] = "gemini-1.5-flash-002",
    system_instruction: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    top_k: Optional[int] = None,
    stop_sequences: Optional[List[str]] = None,
    safety_settings: Optional[List[Dict[str, Any]]] = None
) -> None:
    """
    验证对话完成请求的所有参数
    """
    validate_messages(messages)
    validate_model_name(model)
    
    if system_instruction is not None:
        validate_prompt_content(system_instruction)
    
    validate_generation_parameters(max_tokens, temperature, top_p, top_k)
    validate_stop_sequences(stop_sequences)
    validate_safety_settings(safety_settings)

def validate_text_analysis_request(
    text: str,
    model: Union[str, GeminiModel] = "gemini-1.5-flash-002",
    analysis_type: str = "general",
    language: str = "auto",
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None
) -> None:
    """
    验证文本分析请求的所有参数
    """
    validate_prompt_content(text)
    validate_model_name(model)
    validate_analysis_type(analysis_type)
    validate_generation_parameters(max_tokens, temperature)