"""
Mock服务模块

提供用于测试的Mock服务实现，替代真实的外部API调用。
"""

from .mock_gemini_service import (
    MockGeminiService,
    MockGeminiImageService,
    MockGeminiClient,
    create_mock_gemini_service,
    create_mock_gemini_image_service,
    create_mock_gemini_client
)
from .mock_kling_service import (
    MockKlingService,
    MockKlingClient,
    create_mock_kling_service,
    create_mock_kling_client
)

__all__ = [
    # Gemini Mock服务
    "MockGeminiService",
    "MockGeminiImageService", 
    "MockGeminiClient",
    "create_mock_gemini_service",
    "create_mock_gemini_image_service",
    "create_mock_gemini_client",
    
    # Kling Mock服务
    "MockKlingService",
    "MockKlingClient",
    "create_mock_kling_service",
    "create_mock_kling_client"
]