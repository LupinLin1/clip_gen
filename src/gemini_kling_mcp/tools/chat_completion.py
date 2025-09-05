"""
Gemini 对话完成 MCP 工具

提供对话完成功能的 MCP 工具实现。
"""

from typing import Dict, Any, Optional, List
import json

from ..logger import get_logger
from ..services.gemini import GeminiService, ChatCompletionRequest, GeminiMessage, MessageRole, GeminiModel
from .registry import tool

# 模块级别的服务实例
_gemini_service: Optional[GeminiService] = None

async def _get_service() -> GeminiService:
    """获取或创建 Gemini 服务实例"""
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service

@tool(
    name="gemini_chat_completion",
    description="使用 Google Gemini 模型进行对话完成。支持多轮对话和系统指令。",
    parameters={
        "type": "object",
        "properties": {
            "messages": {
                "type": "array",
                "description": "对话消息历史",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {
                            "type": "string",
                            "enum": ["user", "model"],
                            "description": "消息角色"
                        },
                        "content": {
                            "type": "string",
                            "description": "消息内容"
                        }
                    },
                    "required": ["role", "content"]
                },
                "minItems": 1
            },
            "model": {
                "type": "string",
                "description": "使用的Gemini模型",
                "enum": [
                    "gemini-1.5-pro-002",
                    "gemini-1.5-flash-002",
                    "gemini-1.5-flash-8b-001",
                    "gemini-1.0-pro-001"
                ],
                "default": "gemini-1.5-flash-002"
            },
            "system_instruction": {
                "type": "string",
                "description": "系统指令，用于设定对话的角色和行为"
            },
            "max_tokens": {
                "type": "integer",
                "description": "生成文本的最大令牌数",
                "minimum": 1,
                "maximum": 8192,
                "default": 1000
            },
            "temperature": {
                "type": "number",
                "description": "生成温度，控制输出的随机性 (0.0-2.0)",
                "minimum": 0.0,
                "maximum": 2.0,
                "default": 0.7
            },
            "top_p": {
                "type": "number",
                "description": "核采样参数 (0.0-1.0)",
                "minimum": 0.0,
                "maximum": 1.0,
                "default": 0.95
            },
            "top_k": {
                "type": "integer",
                "description": "Top-K采样参数，可选",
                "minimum": 1,
                "maximum": 100
            },
            "stop_sequences": {
                "type": "array",
                "description": "停止生成的序列列表",
                "items": {
                    "type": "string"
                }
            }
        },
        "required": ["messages"],
        "additionalProperties": False
    }
)
async def chat_completion(
    messages: List[Dict[str, str]],
    model: str = "gemini-1.5-flash-002",
    system_instruction: Optional[str] = None,
    max_tokens: int = 1000,
    temperature: float = 0.7,
    top_p: float = 0.95,
    top_k: Optional[int] = None,
    stop_sequences: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    对话完成
    
    Args:
        messages: 对话消息历史
        model: 使用的模型
        system_instruction: 系统指令
        max_tokens: 最大令牌数
        temperature: 生成温度
        top_p: 核采样参数
        top_k: Top-K采样参数
        stop_sequences: 停止序列列表
    
    Returns:
        包含响应消息和相关信息的字典
    """
    logger = get_logger("gemini_chat_completion")
    logger.info(
        "开始对话完成工具调用",
        model=model,
        message_count=len(messages),
        max_tokens=max_tokens,
        temperature=temperature,
        has_system_instruction=system_instruction is not None
    )
    
    try:
        # 转换消息格式
        gemini_messages = []
        for msg in messages:
            if not isinstance(msg, dict) or "role" not in msg or "content" not in msg:
                raise ValueError(f"消息格式错误: {msg}")
            
            role = MessageRole(msg["role"])
            content = msg["content"]
            gemini_messages.append(GeminiMessage(role=role, content=content))
        
        # 创建请求对象
        request = ChatCompletionRequest(
            messages=gemini_messages,
            model=GeminiModel(model),
            system_instruction=system_instruction,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            stop_sequences=stop_sequences
        )
        
        # 获取服务并完成对话
        service = await _get_service()
        response = await service.complete_chat(request)
        
        # 构建返回结果
        result = {
            "message": {
                "role": response.message.role.value,
                "content": response.message.content
            },
            "model": response.model,
            "finish_reason": response.finish_reason,
            "usage": response.usage or {},
            "success": True
        }
        
        # 添加安全评级信息（如果有）
        if response.safety_ratings:
            result["safety_ratings"] = response.safety_ratings
        
        logger.info(
            "对话完成工具调用完成",
            response_length=len(response.message.content),
            finish_reason=response.finish_reason
        )
        
        return result
        
    except Exception as e:
        logger.error(f"对话完成工具调用失败: {str(e)}")
        return {
            "message": {
                "role": "model",
                "content": ""
            },
            "error": str(e),
            "success": False
        }

@tool(
    name="gemini_chat_with_context",
    description="基于上下文的对话完成，支持提供背景信息和特定的对话风格。",
    parameters={
        "type": "object",
        "properties": {
            "user_message": {
                "type": "string",
                "description": "用户消息"
            },
            "context": {
                "type": "string",
                "description": "对话上下文或背景信息"
            },
            "conversation_style": {
                "type": "string",
                "description": "对话风格",
                "enum": [
                    "professional",
                    "casual", 
                    "creative",
                    "analytical",
                    "helpful",
                    "educational"
                ],
                "default": "helpful"
            },
            "model": {
                "type": "string",
                "description": "使用的Gemini模型",
                "enum": [
                    "gemini-1.5-pro-002",
                    "gemini-1.5-flash-002",
                    "gemini-1.5-flash-8b-001",
                    "gemini-1.0-pro-001"
                ],
                "default": "gemini-1.5-flash-002"
            },
            "max_tokens": {
                "type": "integer",
                "description": "生成文本的最大令牌数",
                "minimum": 1,
                "maximum": 8192,
                "default": 1000
            },
            "temperature": {
                "type": "number",
                "description": "生成温度 (0.0-2.0)",
                "minimum": 0.0,
                "maximum": 2.0,
                "default": 0.7
            }
        },
        "required": ["user_message"],
        "additionalProperties": False
    }
)
async def chat_with_context(
    user_message: str,
    context: Optional[str] = None,
    conversation_style: str = "helpful",
    model: str = "gemini-1.5-flash-002",
    max_tokens: int = 1000,
    temperature: float = 0.7
) -> Dict[str, Any]:
    """
    基于上下文的对话完成
    
    Args:
        user_message: 用户消息
        context: 对话上下文
        conversation_style: 对话风格
        model: 使用的模型
        max_tokens: 最大令牌数
        temperature: 生成温度
    
    Returns:
        包含响应消息的字典
    """
    logger = get_logger("gemini_chat_with_context")
    logger.info(
        "开始上下文对话",
        message_length=len(user_message),
        has_context=context is not None,
        style=conversation_style
    )
    
    try:
        # 构建系统指令
        style_instructions = {
            "professional": "请以专业、正式的语调回应，使用准确的术语和清晰的逻辑。",
            "casual": "请以轻松、友好的语调回应，使用通俗易懂的语言。",
            "creative": "请以富有创意和想象力的方式回应，可以使用比喻和生动的描述。",
            "analytical": "请以分析性思维回应，提供详细的推理过程和数据支持。",
            "helpful": "请以乐于助人的态度回应，提供实用的建议和解决方案。",
            "educational": "请以教育性的方式回应，详细解释概念并提供学习指导。"
        }
        
        system_instruction = style_instructions.get(conversation_style, style_instructions["helpful"])
        
        if context:
            system_instruction += f"\n\n背景上下文：\n{context}"
        
        # 构建消息
        messages = [
            GeminiMessage(role=MessageRole.USER, content=user_message)
        ]
        
        # 创建请求对象
        request = ChatCompletionRequest(
            messages=messages,
            model=GeminiModel(model),
            system_instruction=system_instruction,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        # 获取服务并完成对话
        service = await _get_service()
        response = await service.complete_chat(request)
        
        result = {
            "message": {
                "role": response.message.role.value,
                "content": response.message.content
            },
            "context_used": context is not None,
            "conversation_style": conversation_style,
            "model": response.model,
            "finish_reason": response.finish_reason,
            "usage": response.usage or {},
            "success": True
        }
        
        logger.info(
            "上下文对话完成",
            response_length=len(response.message.content),
            finish_reason=response.finish_reason
        )
        
        return result
        
    except Exception as e:
        logger.error(f"上下文对话失败: {str(e)}")
        return {
            "message": {
                "role": "model", 
                "content": ""
            },
            "error": str(e),
            "success": False
        }

@tool(
    name="gemini_continue_conversation",
    description="继续现有对话，基于对话历史生成回复。",
    parameters={
        "type": "object",
        "properties": {
            "conversation_history": {
                "type": "string",
                "description": "JSON格式的对话历史，或者纯文本格式的对话内容"
            },
            "new_user_message": {
                "type": "string",
                "description": "新的用户消息"
            },
            "model": {
                "type": "string",
                "description": "使用的Gemini模型",
                "enum": [
                    "gemini-1.5-pro-002",
                    "gemini-1.5-flash-002",
                    "gemini-1.5-flash-8b-001",
                    "gemini-1.0-pro-001"
                ],
                "default": "gemini-1.5-flash-002"
            },
            "max_tokens": {
                "type": "integer",
                "description": "生成文本的最大令牌数",
                "minimum": 1,
                "maximum": 8192,
                "default": 1000
            },
            "temperature": {
                "type": "number",
                "description": "生成温度 (0.0-2.0)",
                "minimum": 0.0,
                "maximum": 2.0,
                "default": 0.7
            }
        },
        "required": ["conversation_history", "new_user_message"],
        "additionalProperties": False
    }
)
async def continue_conversation(
    conversation_history: str,
    new_user_message: str,
    model: str = "gemini-1.5-flash-002",
    max_tokens: int = 1000,
    temperature: float = 0.7
) -> Dict[str, Any]:
    """
    继续现有对话
    
    Args:
        conversation_history: 对话历史
        new_user_message: 新的用户消息
        model: 使用的模型
        max_tokens: 最大令牌数
        temperature: 生成温度
    
    Returns:
        包含响应消息的字典
    """
    logger = get_logger("gemini_continue_conversation")
    logger.info(
        "继续对话",
        history_length=len(conversation_history),
        new_message_length=len(new_user_message)
    )
    
    try:
        messages = []
        
        # 尝试解析JSON格式的历史
        try:
            history_data = json.loads(conversation_history)
            if isinstance(history_data, list):
                for msg in history_data:
                    if isinstance(msg, dict) and "role" in msg and "content" in msg:
                        role = MessageRole(msg["role"])
                        content = msg["content"]
                        messages.append(GeminiMessage(role=role, content=content))
        except json.JSONDecodeError:
            # 如果不是JSON格式，作为文本历史处理
            messages.append(GeminiMessage(
                role=MessageRole.USER, 
                content=f"对话历史：\n{conversation_history}"
            ))
        
        # 添加新的用户消息
        messages.append(GeminiMessage(role=MessageRole.USER, content=new_user_message))
        
        # 创建请求对象
        request = ChatCompletionRequest(
            messages=messages,
            model=GeminiModel(model),
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        # 获取服务并完成对话
        service = await _get_service()
        response = await service.complete_chat(request)
        
        result = {
            "message": {
                "role": response.message.role.value,
                "content": response.message.content
            },
            "model": response.model,
            "finish_reason": response.finish_reason,
            "usage": response.usage or {},
            "updated_conversation": [
                # 包含所有历史消息和新的响应
                *[{"role": msg.role.value, "content": msg.content} for msg in messages],
                {"role": response.message.role.value, "content": response.message.content}
            ],
            "success": True
        }
        
        logger.info(
            "对话继续完成",
            response_length=len(response.message.content),
            total_messages=len(result["updated_conversation"])
        )
        
        return result
        
    except Exception as e:
        logger.error(f"继续对话失败: {str(e)}")
        return {
            "message": {
                "role": "model",
                "content": ""
            },
            "error": str(e),
            "success": False
        }

# 清理函数
async def cleanup_chat_completion():
    """清理对话完成工具资源"""
    global _gemini_service
    if _gemini_service:
        await _gemini_service.close()
        _gemini_service = None