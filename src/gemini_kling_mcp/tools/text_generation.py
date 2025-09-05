"""
Gemini 文本生成 MCP 工具

提供文本生成功能的 MCP 工具实现。
"""

from typing import Dict, Any, Optional
import asyncio

from ..logger import get_logger
from ..services.gemini import GeminiService, TextGenerationRequest, GeminiModel
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
    name="gemini_generate_text",
    description="使用 Google Gemini 模型生成文本。支持多种模型、可调节温度和令牌数量等参数。",
    parameters={
        "type": "object", 
        "properties": {
            "prompt": {
                "type": "string",
                "description": "生成文本的提示内容"
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
        "required": ["prompt"],
        "additionalProperties": False
    }
)
async def generate_text(
    prompt: str,
    model: str = "gemini-1.5-flash-002",
    max_tokens: int = 1000,
    temperature: float = 0.7,
    top_p: float = 0.95,
    top_k: Optional[int] = None,
    stop_sequences: Optional[list] = None
) -> Dict[str, Any]:
    """
    生成文本
    
    Args:
        prompt: 生成文本的提示
        model: 使用的模型
        max_tokens: 最大令牌数
        temperature: 生成温度
        top_p: 核采样参数
        top_k: Top-K采样参数
        stop_sequences: 停止序列列表
    
    Returns:
        包含生成文本和相关信息的字典
    """
    logger = get_logger("gemini_generate_text")
    logger.info(
        "开始文本生成工具调用",
        model=model,
        prompt_length=len(prompt),
        max_tokens=max_tokens,
        temperature=temperature
    )
    
    try:
        # 创建请求对象
        request = TextGenerationRequest(
            prompt=prompt,
            model=GeminiModel(model),
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            stop_sequences=stop_sequences
        )
        
        # 获取服务并生成文本
        service = await _get_service()
        response = await service.generate_text(request)
        
        # 构建返回结果
        result = {
            "text": response.text,
            "model": response.model,
            "finish_reason": response.finish_reason,
            "usage": response.usage or {},
            "success": True
        }
        
        # 添加安全评级信息（如果有）
        if response.safety_ratings:
            result["safety_ratings"] = response.safety_ratings
        
        logger.info(
            "文本生成工具调用完成",
            generated_length=len(response.text),
            finish_reason=response.finish_reason
        )
        
        return result
        
    except Exception as e:
        logger.error(f"文本生成工具调用失败: {str(e)}")
        return {
            "text": "",
            "error": str(e),
            "success": False
        }

@tool(
    name="gemini_generate_text_batch",
    description="批量生成文本，支持同时处理多个提示。",
    parameters={
        "type": "object",
        "properties": {
            "prompts": {
                "type": "array",
                "description": "提示列表",
                "items": {
                    "type": "string"
                },
                "minItems": 1,
                "maxItems": 10
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
            },
            "concurrent_limit": {
                "type": "integer",
                "description": "并发处理数量限制",
                "minimum": 1,
                "maximum": 5,
                "default": 3
            }
        },
        "required": ["prompts"],
        "additionalProperties": False
    }
)
async def generate_text_batch(
    prompts: list,
    model: str = "gemini-1.5-flash-002",
    max_tokens: int = 1000,
    temperature: float = 0.7,
    concurrent_limit: int = 3
) -> Dict[str, Any]:
    """
    批量生成文本
    
    Args:
        prompts: 提示列表
        model: 使用的模型
        max_tokens: 最大令牌数
        temperature: 生成温度
        concurrent_limit: 并发限制
    
    Returns:
        包含所有生成结果的字典
    """
    logger = get_logger("gemini_generate_text_batch")
    logger.info(
        "开始批量文本生成",
        prompt_count=len(prompts),
        model=model,
        concurrent_limit=concurrent_limit
    )
    
    try:
        service = await _get_service()
        
        # 使用信号量控制并发
        semaphore = asyncio.Semaphore(concurrent_limit)
        
        async def generate_single(prompt: str, index: int):
            """生成单个文本"""
            async with semaphore:
                try:
                    request = TextGenerationRequest(
                        prompt=prompt,
                        model=GeminiModel(model),
                        max_tokens=max_tokens,
                        temperature=temperature
                    )
                    
                    response = await service.generate_text(request)
                    
                    return {
                        "index": index,
                        "prompt": prompt,
                        "text": response.text,
                        "model": response.model,
                        "finish_reason": response.finish_reason,
                        "usage": response.usage or {},
                        "success": True
                    }
                    
                except Exception as e:
                    logger.error(f"批量生成第{index}个失败: {str(e)}")
                    return {
                        "index": index,
                        "prompt": prompt,
                        "text": "",
                        "error": str(e),
                        "success": False
                    }
        
        # 并发执行所有任务
        tasks = [
            generate_single(prompt, i) 
            for i, prompt in enumerate(prompts)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # 统计结果
        successful_count = sum(1 for r in results if r["success"])
        failed_count = len(results) - successful_count
        
        logger.info(
            "批量文本生成完成",
            total_count=len(results),
            successful_count=successful_count,
            failed_count=failed_count
        )
        
        return {
            "results": results,
            "summary": {
                "total": len(results),
                "successful": successful_count,
                "failed": failed_count
            },
            "success": True
        }
        
    except Exception as e:
        logger.error(f"批量文本生成失败: {str(e)}")
        return {
            "results": [],
            "error": str(e),
            "success": False
        }

# 清理函数
async def cleanup_text_generation():
    """清理文本生成工具资源"""
    global _gemini_service
    if _gemini_service:
        await _gemini_service.close()
        _gemini_service = None