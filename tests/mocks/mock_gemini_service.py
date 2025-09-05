"""
Gemini服务Mock实现

提供Gemini API的Mock服务，用于测试时替代真实API调用。
"""

import asyncio
import random
import time
from typing import Dict, Any, Optional, List
from unittest.mock import AsyncMock, Mock
import json
import base64

from src.gemini_kling_mcp.services.gemini.models import (
    TextGenerationRequest, ChatCompletionRequest, TextAnalysisRequest,
    ImageGenerationRequest, TextGenerationResponse, ChatCompletionResponse,
    TextAnalysisResponse, ImageGenerationResponse, GeminiMessage, MessageRole
)
from src.gemini_kling_mcp.exceptions import GeminiAPIError
from tests.test_data_generator import test_data_generator


class MockGeminiService:
    """Mock Gemini服务"""
    
    def __init__(self, enable_errors: bool = False, delay_range: tuple = (0.1, 0.5)):
        self.enable_errors = enable_errors
        self.delay_range = delay_range
        self.call_count = 0
        self.last_request = None
        
    async def _simulate_delay(self):
        """模拟网络延迟"""
        delay = random.uniform(*self.delay_range)
        await asyncio.sleep(delay)
    
    def _should_fail(self) -> bool:
        """决定是否模拟失败"""
        return self.enable_errors and random.random() < 0.1  # 10% 失败率
    
    async def generate_text(self, request: TextGenerationRequest) -> TextGenerationResponse:
        """生成文本Mock"""
        self.call_count += 1
        self.last_request = request
        
        await self._simulate_delay()
        
        if self._should_fail():
            raise GeminiAPIError("Mock API error: Rate limit exceeded")
        
        # 根据prompt生成相关的Mock响应
        if "故事" in request.prompt or "story" in request.prompt.lower():
            text = self._generate_story_text(request.prompt)
        elif "代码" in request.prompt or "code" in request.prompt.lower():
            text = self._generate_code_text()
        else:
            text = test_data_generator.generate_text_content(100, 500)
        
        return TextGenerationResponse(
            text=text,
            model=request.model.value,
            finish_reason="stop",
            usage={
                "prompt_tokens": len(request.prompt.split()),
                "completion_tokens": len(text.split()),
                "total_tokens": len(request.prompt.split()) + len(text.split())
            }
        )
    
    async def complete_chat(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """对话完成Mock"""
        self.call_count += 1
        self.last_request = request
        
        await self._simulate_delay()
        
        if self._should_fail():
            raise GeminiAPIError("Mock API error: Service unavailable")
        
        # 基于对话历史生成响应
        last_message = request.messages[-1] if request.messages else None
        if last_message and "你好" in last_message.content:
            response_content = "你好！我是AI助手，很高兴为您服务！"
        elif last_message and "帮助" in last_message.content:
            response_content = "当然，我很乐意帮助您！请告诉我您需要什么帮助。"
        else:
            response_content = test_data_generator.generate_text_content(50, 200)
        
        message = GeminiMessage(role=MessageRole.MODEL, content=response_content)
        
        return ChatCompletionResponse(
            message=message,
            model=request.model.value,
            finish_reason="stop",
            usage={
                "prompt_tokens": sum(len(msg.content.split()) for msg in request.messages),
                "completion_tokens": len(response_content.split()),
                "total_tokens": sum(len(msg.content.split()) for msg in request.messages) + len(response_content.split())
            }
        )
    
    async def analyze_text(self, request: TextAnalysisRequest) -> TextAnalysisResponse:
        """文本分析Mock"""
        self.call_count += 1
        self.last_request = request
        
        await self._simulate_delay()
        
        if self._should_fail():
            raise GeminiAPIError("Mock API error: Invalid request")
        
        # 根据分析类型生成不同的Mock响应
        if request.analysis_type == "sentiment":
            analysis = json.dumps({
                "sentiment": random.choice(["positive", "negative", "neutral"]),
                "confidence": round(random.uniform(0.6, 0.95), 2)
            }, ensure_ascii=False)
            sentiment = {"sentiment": "positive", "confidence": 0.85}
        elif request.analysis_type == "keywords":
            keywords = ["关键词1", "关键词2", "关键词3", "重要概念", "主题"]
            analysis = ", ".join(random.sample(keywords, 3))
        elif request.analysis_type == "summarize":
            analysis = "这是文本内容的简要总结，包含了主要要点和核心信息。"
        else:
            analysis = test_data_generator.generate_text_content(100, 300)
        
        return TextAnalysisResponse(
            analysis=analysis,
            model=request.model.value,
            confidence=round(random.uniform(0.7, 0.95), 2),
            sentiment=sentiment if request.analysis_type == "sentiment" else None,
            usage={
                "prompt_tokens": len(request.text.split()),
                "completion_tokens": len(analysis.split()),
                "total_tokens": len(request.text.split()) + len(analysis.split())
            }
        )
    
    def _generate_story_text(self, prompt: str) -> str:
        """生成故事文本"""
        stories = [
            "从前有一只勇敢的小猫，它住在一个美丽的小村庄里。有一天，小猫决定去探险...",
            "在遥远的未来，机器人和人类和谐相处。有一个特别的机器人叫做阿尔法...",
            "魔法森林深处有一本神秘的书，据说它能实现任何愿望。一个年轻的冒险者...",
            "太空站上的科学家们发现了一个新的星球，那里有着奇特的生物..."
        ]
        return random.choice(stories) + test_data_generator.generate_text_content(200, 400)
    
    def _generate_code_text(self) -> str:
        """生成代码文本"""
        code_examples = [
            '''```python
def hello_world():
    print("Hello, World!")
    return "Success"

if __name__ == "__main__":
    hello_world()
```''',
            '''```javascript
function calculateSum(a, b) {
    return a + b;
}

console.log(calculateSum(5, 3));
```''',
            '''```python
import asyncio

async def main():
    print("异步函数执行中...")
    await asyncio.sleep(1)
    print("完成！")

asyncio.run(main())
```'''
        ]
        return random.choice(code_examples)
    
    def reset_stats(self):
        """重置统计信息"""
        self.call_count = 0
        self.last_request = None


class MockGeminiImageService:
    """Mock Gemini图像服务"""
    
    def __init__(self, enable_errors: bool = False, delay_range: tuple = (1.0, 3.0)):
        self.enable_errors = enable_errors
        self.delay_range = delay_range
        self.call_count = 0
        self.last_request = None
    
    async def _simulate_delay(self):
        """模拟图像生成延迟"""
        delay = random.uniform(*self.delay_range)
        await asyncio.sleep(delay)
    
    def _should_fail(self) -> bool:
        """决定是否模拟失败"""
        return self.enable_errors and random.random() < 0.05  # 5% 失败率
    
    async def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        """生成图像Mock"""
        self.call_count += 1
        self.last_request = request
        
        await self._simulate_delay()
        
        if self._should_fail():
            raise GeminiAPIError("Mock API error: Content policy violation")
        
        # 生成Mock图像数据
        images = []
        file_paths = []
        
        for i in range(request.num_images):
            if request.output_mode == "base64":
                # 生成假的base64图像数据
                fake_image_data = self._generate_fake_base64_image()
                images.append({
                    "data": fake_image_data,
                    "format": "png"
                })
            else:
                # 生成假的文件路径
                file_path = f"/tmp/gemini_kling_mcp/image_{time.time()}_{i}.png"
                file_paths.append(file_path)
        
        return ImageGenerationResponse(
            images=images if request.output_mode == "base64" else [],
            file_paths=file_paths,
            model=request.model,
            usage={"prompt_tokens": len(request.prompt.split())}
        )
    
    def _generate_fake_base64_image(self) -> str:
        """生成假的base64图像数据"""
        # 模拟PNG文件头的base64编码
        fake_png_header = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
        fake_data = fake_png_header + b'x' * 100  # 添加一些假数据
        return base64.b64encode(fake_data).decode()
    
    def reset_stats(self):
        """重置统计信息"""
        self.call_count = 0
        self.last_request = None


class MockGeminiClient:
    """Mock Gemini HTTP客户端"""
    
    def __init__(self, config, enable_errors: bool = False):
        self.config = config
        self.enable_errors = enable_errors
        self.request_history = []
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
        
    async def generate_content(self, model, request_data):
        """Mock内容生成"""
        self.request_history.append(("generate_content", model, request_data))
        
        if self.enable_errors and random.random() < 0.1:
            raise Exception("Mock network error")
        
        # 模拟延迟
        await asyncio.sleep(random.uniform(0.1, 0.5))
        
        return test_data_generator.generate_api_response("text")
    
    async def generate_image(self, model, request_data):
        """Mock图像生成"""
        self.request_history.append(("generate_image", model, request_data))
        
        if self.enable_errors and random.random() < 0.05:
            raise Exception("Mock image generation error")
        
        await asyncio.sleep(random.uniform(1.0, 2.0))
        
        return test_data_generator.generate_api_response("image")
    
    def extract_generated_text(self, response):
        """提取生成文本Mock"""
        if "choices" in response:
            return response["choices"][0]["message"]["content"]
        return "Mock generated text"
    
    def extract_usage_info(self, response):
        """提取使用信息Mock"""
        return response.get("usage", {
            "prompt_tokens": 10,
            "completion_tokens": 50,
            "total_tokens": 60
        })
    
    def extract_image_data(self, response):
        """提取图像数据Mock"""
        return response.get("images", [])


def create_mock_gemini_service(enable_errors: bool = False) -> MockGeminiService:
    """创建Mock Gemini服务"""
    return MockGeminiService(enable_errors=enable_errors)


def create_mock_gemini_image_service(enable_errors: bool = False) -> MockGeminiImageService:
    """创建Mock Gemini图像服务"""
    return MockGeminiImageService(enable_errors=enable_errors)


def create_mock_gemini_client(config, enable_errors: bool = False) -> MockGeminiClient:
    """创建Mock Gemini客户端"""
    return MockGeminiClient(config, enable_errors=enable_errors)