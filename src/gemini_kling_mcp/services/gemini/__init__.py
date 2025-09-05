"""
Google Gemini AI 服务模块

提供 Gemini 文本生成、对话完成和文本分析功能。
"""

from .client import GeminiClient
from .text_service import GeminiTextService
from .image_service import GeminiImageService
from .models import (
    TextGenerationRequest,
    TextGenerationResponse,
    ChatCompletionRequest,
    ChatCompletionResponse,
    TextAnalysisRequest,
    TextAnalysisResponse,
    GeminiMessage,
    MessageRole,
    GeminiModel,
    ImageModel,
    ImageFormat,
    ImageResolution,
    ImageEditMode,
    ImageGenerationRequest,
    ImageGenerationResponse,
    ImageEditRequest,
    ImageEditResponse,
    ImageAnalysisRequest,
    ImageAnalysisResponse,
    ImageBatchRequest,
    ImageBatchResponse,
    ImageData
)

# 主要服务类
GeminiService = GeminiTextService

__all__ = [
    "GeminiClient",
    "GeminiTextService", 
    "GeminiImageService",
    "GeminiService",
    "TextGenerationRequest",
    "TextGenerationResponse", 
    "ChatCompletionRequest",
    "ChatCompletionResponse",
    "TextAnalysisRequest",
    "TextAnalysisResponse",
    "GeminiMessage",
    "MessageRole",
    "GeminiModel",
    "ImageModel",
    "ImageFormat",
    "ImageResolution",
    "ImageEditMode",
    "ImageGenerationRequest",
    "ImageGenerationResponse",
    "ImageEditRequest",
    "ImageEditResponse",
    "ImageAnalysisRequest",
    "ImageAnalysisResponse",
    "ImageBatchRequest",
    "ImageBatchResponse",
    "ImageData"
]