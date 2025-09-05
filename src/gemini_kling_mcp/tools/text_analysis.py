"""
Gemini 文本分析 MCP 工具

提供文本分析功能的 MCP 工具实现。
"""

from typing import Dict, Any, Optional, List
import json

from ..logger import get_logger
from ..services.gemini import GeminiService, TextAnalysisRequest, GeminiModel
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
    name="gemini_analyze_text",
    description="使用 Google Gemini 模型分析文本。支持多种分析类型：情感分析、摘要、关键词提取、实体识别等。",
    parameters={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "待分析的文本内容"
            },
            "analysis_type": {
                "type": "string",
                "description": "分析类型",
                "enum": [
                    "general",
                    "sentiment", 
                    "summarize",
                    "keywords",
                    "entities",
                    "classify",
                    "translate",
                    "grammar"
                ],
                "default": "general"
            },
            "language": {
                "type": "string",
                "description": "文本语言（可选，auto表示自动检测）",
                "default": "auto"
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
                "description": "生成分析的最大令牌数",
                "minimum": 1,
                "maximum": 8192,
                "default": 1000
            },
            "temperature": {
                "type": "number",
                "description": "生成温度 (0.0-2.0)，分析任务建议使用较低值",
                "minimum": 0.0,
                "maximum": 2.0,
                "default": 0.3
            }
        },
        "required": ["text"],
        "additionalProperties": False
    }
)
async def analyze_text(
    text: str,
    analysis_type: str = "general",
    language: str = "auto",
    model: str = "gemini-1.5-flash-002",
    max_tokens: int = 1000,
    temperature: float = 0.3
) -> Dict[str, Any]:
    """
    分析文本
    
    Args:
        text: 待分析的文本
        analysis_type: 分析类型
        language: 文本语言
        model: 使用的模型
        max_tokens: 最大令牌数
        temperature: 生成温度
    
    Returns:
        包含分析结果的字典
    """
    logger = get_logger("gemini_analyze_text")
    logger.info(
        "开始文本分析工具调用",
        text_length=len(text),
        analysis_type=analysis_type,
        language=language,
        model=model
    )
    
    try:
        # 创建请求对象
        request = TextAnalysisRequest(
            text=text,
            model=GeminiModel(model),
            analysis_type=analysis_type,
            language=language,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        # 获取服务并分析文本
        service = await _get_service()
        response = await service.analyze_text(request)
        
        # 构建返回结果
        result = {
            "analysis": response.analysis,
            "analysis_type": analysis_type,
            "model": response.model,
            "usage": response.usage or {},
            "success": True
        }
        
        # 添加结构化数据（如果有）
        if response.confidence is not None:
            result["confidence"] = response.confidence
        
        if response.categories:
            result["categories"] = response.categories
        
        if response.sentiment:
            result["sentiment"] = response.sentiment
        
        if response.entities:
            result["entities"] = response.entities
        
        logger.info(
            "文本分析工具调用完成",
            analysis_length=len(response.analysis),
            has_sentiment=response.sentiment is not None,
            has_entities=response.entities is not None
        )
        
        return result
        
    except Exception as e:
        logger.error(f"文本分析工具调用失败: {str(e)}")
        return {
            "analysis": "",
            "analysis_type": analysis_type,
            "error": str(e),
            "success": False
        }

@tool(
    name="gemini_sentiment_analysis", 
    description="专门的情感分析工具，返回详细的情感评分和分类。",
    parameters={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "待分析情感的文本内容"
            },
            "detailed": {
                "type": "boolean",
                "description": "是否返回详细的情感分析结果",
                "default": True
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
            "language": {
                "type": "string",
                "description": "文本语言",
                "default": "auto"
            }
        },
        "required": ["text"],
        "additionalProperties": False
    }
)
async def sentiment_analysis(
    text: str,
    detailed: bool = True,
    model: str = "gemini-1.5-flash-002",
    language: str = "auto"
) -> Dict[str, Any]:
    """
    情感分析
    
    Args:
        text: 待分析的文本
        detailed: 是否返回详细结果
        model: 使用的模型
        language: 文本语言
    
    Returns:
        包含情感分析结果的字典
    """
    logger = get_logger("gemini_sentiment_analysis")
    logger.info(
        "开始情感分析",
        text_length=len(text),
        detailed=detailed,
        language=language
    )
    
    try:
        # 构建专门的情感分析提示
        if detailed:
            prompt = f"""请对以下文本进行详细的情感分析，并以JSON格式返回结果：

分析要求：
1. 总体情感倾向（positive/negative/neutral）
2. 情感强度评分（0-1，0表示非常消极，0.5表示中性，1表示非常积极）
3. 具体情感标签（如快乐、愤怒、悲伤、恐惧等）
4. 关键情感词汇
5. 情感原因分析

请返回如下JSON格式：
{{
    "overall_sentiment": "positive/negative/neutral",
    "sentiment_score": 0.0-1.0,
    "intensity": "weak/moderate/strong",
    "emotion_labels": ["情感标签列表"],
    "key_phrases": ["关键情感词汇"],
    "reasoning": "情感分析的原因解释"
}}

待分析文本：
{text}"""
        else:
            prompt = f"""请对以下文本进行情感分析，返回JSON格式结果：

{{
    "sentiment": "positive/negative/neutral",
    "confidence": 0.0-1.0
}}

待分析文本：
{text}"""
        
        # 创建请求对象
        request = TextAnalysisRequest(
            text=prompt,
            model=GeminiModel(model),
            analysis_type="sentiment",
            language=language,
            temperature=0.1  # 更低的温度确保一致性
        )
        
        # 获取服务并分析
        service = await _get_service()
        response = await service.analyze_text(request)
        
        # 尝试解析JSON结果
        try:
            sentiment_data = json.loads(response.analysis.strip())
        except json.JSONDecodeError:
            # 如果解析失败，从文本中提取基本信息
            sentiment_data = {
                "raw_analysis": response.analysis,
                "sentiment": "neutral",
                "confidence": 0.5
            }
        
        result = {
            "sentiment_analysis": sentiment_data,
            "raw_text": text,
            "model": response.model,
            "usage": response.usage or {},
            "success": True
        }
        
        logger.info(
            "情感分析完成",
            sentiment=sentiment_data.get("sentiment", "unknown"),
            confidence=sentiment_data.get("confidence", 0.0)
        )
        
        return result
        
    except Exception as e:
        logger.error(f"情感分析失败: {str(e)}")
        return {
            "sentiment_analysis": {
                "sentiment": "neutral",
                "confidence": 0.0,
                "error": str(e)
            },
            "success": False
        }

@tool(
    name="gemini_summarize_text",
    description="文本摘要工具，可以生成不同长度和风格的摘要。",
    parameters={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "待摘要的文本内容"
            },
            "summary_length": {
                "type": "string",
                "description": "摘要长度",
                "enum": ["short", "medium", "long"],
                "default": "medium"
            },
            "summary_style": {
                "type": "string",
                "description": "摘要风格",
                "enum": ["bullet_points", "paragraph", "abstract", "key_insights"],
                "default": "paragraph"
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
            "focus_areas": {
                "type": "array",
                "description": "重点关注的领域或主题",
                "items": {
                    "type": "string"
                }
            }
        },
        "required": ["text"],
        "additionalProperties": False
    }
)
async def summarize_text(
    text: str,
    summary_length: str = "medium",
    summary_style: str = "paragraph",
    model: str = "gemini-1.5-flash-002",
    focus_areas: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    文本摘要
    
    Args:
        text: 待摘要的文本
        summary_length: 摘要长度
        summary_style: 摘要风格
        model: 使用的模型
        focus_areas: 重点关注领域
    
    Returns:
        包含摘要结果的字典
    """
    logger = get_logger("gemini_summarize_text")
    logger.info(
        "开始文本摘要",
        text_length=len(text),
        summary_length=summary_length,
        summary_style=summary_style,
        focus_areas=focus_areas
    )
    
    try:
        # 构建摘要提示
        length_instructions = {
            "short": "请生成简洁的摘要（1-2句话）",
            "medium": "请生成中等长度的摘要（2-4段落）", 
            "long": "请生成详细的摘要（5-8段落）"
        }
        
        style_instructions = {
            "bullet_points": "使用要点列表格式",
            "paragraph": "使用段落格式",
            "abstract": "使用学术摘要格式",
            "key_insights": "重点突出关键见解和要点"
        }
        
        prompt = f"{length_instructions[summary_length]}，{style_instructions[summary_style]}。"
        
        if focus_areas:
            prompt += f"\n请特别关注以下领域：{', '.join(focus_areas)}。"
        
        prompt += f"\n\n待摘要文本：\n{text}"
        
        # 创建请求对象
        request = TextAnalysisRequest(
            text=prompt,
            model=GeminiModel(model),
            analysis_type="summarize",
            temperature=0.3
        )
        
        # 获取服务并生成摘要
        service = await _get_service()
        response = await service.analyze_text(request)
        
        result = {
            "summary": response.analysis,
            "original_length": len(text),
            "summary_length": len(response.analysis),
            "compression_ratio": len(response.analysis) / len(text) if len(text) > 0 else 0,
            "summary_config": {
                "length": summary_length,
                "style": summary_style,
                "focus_areas": focus_areas
            },
            "model": response.model,
            "usage": response.usage or {},
            "success": True
        }
        
        logger.info(
            "文本摘要完成",
            summary_length=len(response.analysis),
            compression_ratio=result["compression_ratio"]
        )
        
        return result
        
    except Exception as e:
        logger.error(f"文本摘要失败: {str(e)}")
        return {
            "summary": "",
            "error": str(e),
            "success": False
        }

@tool(
    name="gemini_extract_keywords",
    description="关键词提取工具，从文本中提取重要的关键词和关键短语。",
    parameters={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "待提取关键词的文本内容"
            },
            "max_keywords": {
                "type": "integer",
                "description": "最大关键词数量",
                "minimum": 5,
                "maximum": 50,
                "default": 15
            },
            "include_phrases": {
                "type": "boolean",
                "description": "是否包含关键短语（2-3个词的组合）",
                "default": True
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
            }
        },
        "required": ["text"],
        "additionalProperties": False
    }
)
async def extract_keywords(
    text: str,
    max_keywords: int = 15,
    include_phrases: bool = True,
    model: str = "gemini-1.5-flash-002"
) -> Dict[str, Any]:
    """
    提取关键词
    
    Args:
        text: 待提取的文本
        max_keywords: 最大关键词数量
        include_phrases: 是否包含关键短语
        model: 使用的模型
    
    Returns:
        包含关键词的字典
    """
    logger = get_logger("gemini_extract_keywords")
    logger.info(
        "开始关键词提取",
        text_length=len(text),
        max_keywords=max_keywords,
        include_phrases=include_phrases
    )
    
    try:
        # 构建关键词提取提示
        prompt = f"""请从以下文本中提取最多{max_keywords}个重要的关键词"""
        
        if include_phrases:
            prompt += "和关键短语"
        
        prompt += """。请以JSON格式返回结果：

{
    "keywords": ["单个关键词列表"],"""
        
        if include_phrases:
            prompt += """
    "phrases": ["关键短语列表（2-3个词的组合）"],"""
        
        prompt += """
    "categories": ["主题分类"],
    "importance_scores": {"关键词": "重要性评分(0-1)"}
}

"""
        prompt += f"待分析文本：\n{text}"
        
        # 创建请求对象
        request = TextAnalysisRequest(
            text=prompt,
            model=GeminiModel(model),
            analysis_type="keywords",
            temperature=0.2
        )
        
        # 获取服务并提取关键词
        service = await _get_service()
        response = await service.analyze_text(request)
        
        # 尝试解析JSON结果
        try:
            keywords_data = json.loads(response.analysis.strip())
        except json.JSONDecodeError:
            # 解析失败时，从原始文本提取简单列表
            keywords_data = {
                "raw_analysis": response.analysis,
                "keywords": [],
                "phrases": []
            }
        
        result = {
            "keywords_data": keywords_data,
            "raw_text_length": len(text),
            "extracted_count": len(keywords_data.get("keywords", [])),
            "model": response.model,
            "usage": response.usage or {},
            "success": True
        }
        
        logger.info(
            "关键词提取完成",
            keywords_count=len(keywords_data.get("keywords", [])),
            phrases_count=len(keywords_data.get("phrases", []))
        )
        
        return result
        
    except Exception as e:
        logger.error(f"关键词提取失败: {str(e)}")
        return {
            "keywords_data": {
                "keywords": [],
                "error": str(e)
            },
            "success": False
        }

# 清理函数
async def cleanup_text_analysis():
    """清理文本分析工具资源"""
    global _gemini_service
    if _gemini_service:
        await _gemini_service.close()
        _gemini_service = None