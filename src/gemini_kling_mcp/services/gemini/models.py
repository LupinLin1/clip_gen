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

# 图像相关枚举和模型
class ImageModel(str, Enum):
    """图像生成模型枚举"""
    GEMINI_25_FLASH_IMAGE = "gemini-2.5-flash-image-preview"
    IMAGEN_4 = "imagen-4"
    IMAGEN_4_FAST = "imagen-4-fast"
    IMAGEN_4_ULTRA = "imagen-4-ultra"
    
    @classmethod
    def get_default(cls) -> "ImageModel":
        """获取默认图像模型"""
        return cls.GEMINI_25_FLASH_IMAGE

class ImageFormat(str, Enum):
    """支持的图像格式"""
    PNG = "png"
    JPEG = "jpeg"
    JPG = "jpg"
    WEBP = "webp"
    GIF = "gif"

class ImageResolution(str, Enum):
    """图像分辨率"""
    RESOLUTION_256x256 = "256x256"
    RESOLUTION_512x512 = "512x512" 
    RESOLUTION_1024x1024 = "1024x1024"
    RESOLUTION_1536x1024 = "1536x1024"
    RESOLUTION_1024x1536 = "1024x1536"
    RESOLUTION_2048x2048 = "2048x2048"

class ImageEditMode(str, Enum):
    """图像编辑模式"""
    GENERATE = "generate"
    EDIT = "edit"
    INPAINT = "inpaint"
    OUTPAINT = "outpaint"
    UPSCALE = "upscale"

# 图像生成请求和响应模型
class ImageGenerationRequest(BaseModel):
    """图像生成请求"""
    prompt: str = Field(..., description="图像生成提示")
    model: ImageModel = Field(default=ImageModel.get_default(), description="使用的图像模型")
    num_images: Optional[int] = Field(default=1, ge=1, le=8, description="生成图像数量")
    resolution: Optional[ImageResolution] = Field(default=ImageResolution.RESOLUTION_1024x1024, description="图像分辨率")
    aspect_ratio: Optional[str] = Field(default="1:1", description="宽高比")
    style: Optional[str] = Field(default=None, description="艺术风格")
    negative_prompt: Optional[str] = Field(default=None, description="负面提示")
    seed: Optional[int] = Field(default=None, description="随机种子")
    guidance_scale: Optional[float] = Field(default=7.5, ge=1.0, le=20.0, description="引导尺度")
    output_format: ImageFormat = Field(default=ImageFormat.PNG, description="输出格式")
    quality: Optional[int] = Field(default=100, ge=1, le=100, description="图像质量")
    
    @field_validator('aspect_ratio')
    def validate_aspect_ratio(cls, v):
        if v and ':' not in v:
            raise ValueError('宽高比格式应为 "width:height"，例如 "16:9"')
        return v

class ImageEditRequest(BaseModel):
    """图像编辑请求"""
    image_data: str = Field(..., description="输入图像的base64数据")
    prompt: str = Field(..., description="编辑指令")
    model: ImageModel = Field(default=ImageModel.get_default(), description="使用的图像模型")
    edit_mode: ImageEditMode = Field(default=ImageEditMode.EDIT, description="编辑模式")
    mask_data: Optional[str] = Field(default=None, description="遮罩图像的base64数据")
    strength: Optional[float] = Field(default=0.8, ge=0.1, le=1.0, description="编辑强度")
    num_inference_steps: Optional[int] = Field(default=50, ge=10, le=100, description="推理步数")
    guidance_scale: Optional[float] = Field(default=7.5, ge=1.0, le=20.0, description="引导尺度")
    seed: Optional[int] = Field(default=None, description="随机种子")
    output_format: ImageFormat = Field(default=ImageFormat.PNG, description="输出格式")
    quality: Optional[int] = Field(default=100, ge=1, le=100, description="图像质量")

class ImageAnalysisRequest(BaseModel):
    """图像分析请求"""
    image_data: str = Field(..., description="输入图像的base64数据")
    model: GeminiModel = Field(default=GeminiModel.get_default(), description="使用的分析模型")
    analysis_type: str = Field(default="general", description="分析类型")
    prompt: Optional[str] = Field(default=None, description="分析提示")
    language: Optional[str] = Field(default="zh", description="输出语言")
    max_tokens: Optional[int] = Field(default=1000, ge=1, le=8192, description="最大令牌数")
    temperature: Optional[float] = Field(default=0.3, ge=0.0, le=2.0, description="生成温度")

class ImageData(BaseModel):
    """图像数据"""
    data: bytes = Field(..., description="图像二进制数据")
    format: ImageFormat = Field(..., description="图像格式")
    width: int = Field(..., description="图像宽度")
    height: int = Field(..., description="图像高度")
    size: int = Field(..., description="图像文件大小")
    checksum: str = Field(..., description="图像校验和")

class ImageGenerationResponse(BaseModel):
    """图像生成响应"""
    images: List[ImageData] = Field(..., description="生成的图像列表")
    model: str = Field(..., description="使用的模型")
    prompt: str = Field(..., description="生成提示")
    num_images: int = Field(..., description="生成的图像数量")
    resolution: str = Field(..., description="图像分辨率")
    seed: Optional[int] = Field(default=None, description="使用的随机种子")
    usage: Optional[Dict[str, int]] = Field(default=None, description="使用统计")

class ImageEditResponse(BaseModel):
    """图像编辑响应"""
    image: ImageData = Field(..., description="编辑后的图像")
    model: str = Field(..., description="使用的模型")
    prompt: str = Field(..., description="编辑提示")
    edit_mode: str = Field(..., description="编辑模式")
    strength: float = Field(..., description="编辑强度")
    usage: Optional[Dict[str, int]] = Field(default=None, description="使用统计")

class ImageAnalysisResponse(BaseModel):
    """图像分析响应"""
    analysis: str = Field(..., description="分析结果")
    model: str = Field(..., description="使用的模型")
    analysis_type: str = Field(..., description="分析类型")
    confidence: Optional[float] = Field(default=None, description="置信度")
    objects: Optional[List[Dict[str, Any]]] = Field(default=None, description="检测到的对象")
    text: Optional[str] = Field(default=None, description="图像中的文本")
    faces: Optional[List[Dict[str, Any]]] = Field(default=None, description="检测到的人脸")
    colors: Optional[List[str]] = Field(default=None, description="主要颜色")
    tags: Optional[List[str]] = Field(default=None, description="图像标签")
    usage: Optional[Dict[str, int]] = Field(default=None, description="令牌使用情况")

class ImageBatchRequest(BaseModel):
    """批量图像处理请求"""
    requests: List[Union[ImageGenerationRequest, ImageEditRequest, ImageAnalysisRequest]] = Field(
        ..., description="批量请求列表"
    )
    max_concurrent: Optional[int] = Field(default=3, ge=1, le=10, description="最大并发数")
    timeout: Optional[int] = Field(default=300, ge=30, le=600, description="超时时间（秒）")

class ImageBatchResponse(BaseModel):
    """批量图像处理响应"""
    results: List[Union[ImageGenerationResponse, ImageEditResponse, ImageAnalysisResponse]] = Field(
        ..., description="处理结果列表"
    )
    success_count: int = Field(..., description="成功处理的数量")
    error_count: int = Field(..., description="处理失败的数量")
    total_time: float = Field(..., description="总处理时间（秒）")
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="错误详情列表")

# 工具参数映射
GEMINI_MODELS = [model.value for model in GeminiModel]
IMAGE_MODELS = [model.value for model in ImageModel]
IMAGE_FORMATS = [format.value for format in ImageFormat]
IMAGE_RESOLUTIONS = [res.value for res in ImageResolution]

DEFAULT_SAFETY_SETTINGS = create_safety_settings()