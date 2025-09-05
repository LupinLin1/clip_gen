"""
Gemini API 数据模型

定义与 Gemini API 交互所需的所有数据结构。
"""

from enum import Enum
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, field_validator

class GeminiModel(str, Enum):
    """Gemini 模型枚举"""
    GEMINI_15_PRO = "gemini-1.5-pro-002"
    GEMINI_15_FLASH = "gemini-1.5-flash-002"  
    GEMINI_15_FLASH_8B = "gemini-1.5-flash-8b-001"
    GEMINI_10_PRO = "gemini-1.0-pro-001"
    
    @classmethod
    def get_default(cls) -> "GeminiModel":
        """获取默认模型"""
        return cls.GEMINI_15_FLASH

class MessageRole(str, Enum):
    """消息角色"""
    USER = "user"
    MODEL = "model"

@dataclass
class GeminiMessage:
    """Gemini 消息"""
    role: MessageRole
    content: str
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "role": self.role.value,
            "parts": [{"text": self.content}]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GeminiMessage":
        """从字典创建"""
        role = MessageRole(data.get("role", "user"))
        # 处理content或parts格式
        if "content" in data:
            content = data["content"]
        elif "parts" in data and len(data["parts"]) > 0:
            content = data["parts"][0].get("text", "")
        else:
            content = ""
        
        return cls(role=role, content=content)

class TextGenerationRequest(BaseModel):
    """文本生成请求"""
    prompt: str = Field(..., description="生成文本的提示")
    model: GeminiModel = Field(default=GeminiModel.get_default(), description="使用的模型")
    max_tokens: Optional[int] = Field(default=1000, ge=1, le=8192, description="最大令牌数")
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0, description="生成温度")
    top_p: Optional[float] = Field(default=0.95, ge=0.0, le=1.0, description="核采样参数")
    top_k: Optional[int] = Field(default=None, ge=1, le=100, description="Top-K采样参数")
    stop_sequences: Optional[List[str]] = Field(default=None, description="停止序列")
    safety_settings: Optional[List[Dict[str, Any]]] = Field(default=None, description="安全设置")
    
    @field_validator('max_tokens')
    def validate_max_tokens(cls, v):
        if v and v > 8192:
            raise ValueError('max_tokens不能超过8192')
        return v

class TextGenerationResponse(BaseModel):
    """文本生成响应"""
    text: str = Field(..., description="生成的文本")
    model: str = Field(..., description="使用的模型")
    finish_reason: Optional[str] = Field(default=None, description="完成原因")
    usage: Optional[Dict[str, int]] = Field(default=None, description="令牌使用情况")
    safety_ratings: Optional[List[Dict[str, Any]]] = Field(default=None, description="安全评级")

class ChatCompletionRequest(BaseModel):
    """对话完成请求"""
    messages: List[GeminiMessage] = Field(..., description="对话消息历史")
    model: GeminiModel = Field(default=GeminiModel.get_default(), description="使用的模型")
    max_tokens: Optional[int] = Field(default=1000, ge=1, le=8192, description="最大令牌数")
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0, description="生成温度")
    top_p: Optional[float] = Field(default=0.95, ge=0.0, le=1.0, description="核采样参数")
    top_k: Optional[int] = Field(default=None, ge=1, le=100, description="Top-K采样参数")
    stop_sequences: Optional[List[str]] = Field(default=None, description="停止序列")
    safety_settings: Optional[List[Dict[str, Any]]] = Field(default=None, description="安全设置")
    system_instruction: Optional[str] = Field(default=None, description="系统指令")
    
    @field_validator('messages')
    def validate_messages(cls, v):
        if not v:
            raise ValueError('消息列表不能为空')
        return v

class ChatCompletionResponse(BaseModel):
    """对话完成响应"""
    message: GeminiMessage = Field(..., description="生成的消息")
    model: str = Field(..., description="使用的模型")
    finish_reason: Optional[str] = Field(default=None, description="完成原因")
    usage: Optional[Dict[str, int]] = Field(default=None, description="令牌使用情况")
    safety_ratings: Optional[List[Dict[str, Any]]] = Field(default=None, description="安全评级")

class TextAnalysisRequest(BaseModel):
    """文本分析请求"""
    text: str = Field(..., description="待分析的文本")
    model: GeminiModel = Field(default=GeminiModel.get_default(), description="使用的模型")
    analysis_type: str = Field(default="general", description="分析类型")
    language: Optional[str] = Field(default="auto", description="文本语言")
    max_tokens: Optional[int] = Field(default=1000, ge=1, le=8192, description="最大令牌数")
    temperature: Optional[float] = Field(default=0.3, ge=0.0, le=2.0, description="生成温度")

class TextAnalysisResponse(BaseModel):
    """文本分析响应"""
    analysis: str = Field(..., description="分析结果")
    model: str = Field(..., description="使用的模型")
    confidence: Optional[float] = Field(default=None, description="置信度")
    categories: Optional[List[str]] = Field(default=None, description="分类标签")
    sentiment: Optional[Dict[str, Any]] = Field(default=None, description="情感分析")
    entities: Optional[List[Dict[str, Any]]] = Field(default=None, description="实体识别")
    usage: Optional[Dict[str, int]] = Field(default=None, description="令牌使用情况")

class GeminiError(BaseModel):
    """Gemini API 错误"""
    code: int = Field(..., description="错误代码")
    message: str = Field(..., description="错误消息")
    status: str = Field(..., description="错误状态")
    details: Optional[Dict[str, Any]] = Field(default=None, description="错误详情")

class GeminiApiResponse(BaseModel):
    """Gemini API 原始响应"""
    candidates: Optional[List[Dict[str, Any]]] = Field(default=None, description="候选结果")
    usage_metadata: Optional[Dict[str, Any]] = Field(default=None, description="使用元数据")
    error: Optional[GeminiError] = Field(default=None, description="错误信息")

# 安全设置相关的常量
class HarmCategory(str, Enum):
    """危害类别"""
    HARM_CATEGORY_HARASSMENT = "HARM_CATEGORY_HARASSMENT"
    HARM_CATEGORY_HATE_SPEECH = "HARM_CATEGORY_HATE_SPEECH"
    HARM_CATEGORY_SEXUALLY_EXPLICIT = "HARM_CATEGORY_SEXUALLY_EXPLICIT"
    HARM_CATEGORY_DANGEROUS_CONTENT = "HARM_CATEGORY_DANGEROUS_CONTENT"

class HarmBlockThreshold(str, Enum):
    """危害阻止阈值"""
    BLOCK_NONE = "BLOCK_NONE"
    BLOCK_LOW_AND_ABOVE = "BLOCK_LOW_AND_ABOVE"
    BLOCK_MEDIUM_AND_ABOVE = "BLOCK_MEDIUM_AND_ABOVE"
    BLOCK_HIGH_AND_ABOVE = "BLOCK_HIGH_AND_ABOVE"

def create_safety_settings(threshold: HarmBlockThreshold = HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE) -> List[Dict[str, str]]:
    """创建安全设置"""
    return [
        {
            "category": category.value,
            "threshold": threshold.value
        }
        for category in HarmCategory
    ]

# 工具参数映射
GEMINI_MODELS = [model.value for model in GeminiModel]

DEFAULT_SAFETY_SETTINGS = create_safety_settings()