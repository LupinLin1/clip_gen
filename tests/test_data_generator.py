"""
测试数据生成器

生成用于测试的各种数据结构和Mock数据。
"""

import random
import string
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from faker import Faker

from src.gemini_kling_mcp.services.gemini.models import (
    GeminiModel, MessageRole, GeminiMessage,
    TextGenerationRequest, ChatCompletionRequest, TextAnalysisRequest,
    ImageGenerationRequest
)
from src.gemini_kling_mcp.services.kling.models import (
    VideoGenerationRequest, KlingModel
)
from src.gemini_kling_mcp.workflow import DAGNode, NodeStatus


class TestDataGenerator:
    """测试数据生成器"""
    
    def __init__(self, locale: str = 'zh_CN'):
        self.fake = Faker(locale)
        random.seed(42)  # 确保结果可重现
        Faker.seed(42)
    
    def generate_text_content(self, min_length: int = 50, max_length: int = 500) -> str:
        """生成随机文本内容"""
        length = random.randint(min_length, max_length)
        words = self.fake.words(nb=length // 5)
        return ' '.join(words)
    
    def generate_story_theme(self) -> str:
        """生成故事主题"""
        themes = [
            "勇敢的小猫冒险记",
            "未来城市的机器人朋友",
            "神秘森林里的魔法书",
            "太空探险与外星朋友",
            "时间旅行者的奇遇",
            "海底世界的珍宝寻找",
            "雪山上的友谊故事",
            "古代宫殿的秘密",
            "彩虹桥上的约定",
            "星空下的许愿故事"
        ]
        return random.choice(themes)
    
    def generate_gemini_text_request(self, **kwargs) -> TextGenerationRequest:
        """生成Gemini文本请求"""
        defaults = {
            "prompt": self.generate_text_content(20, 100),
            "model": random.choice(list(GeminiModel)),
            "max_tokens": random.randint(100, 2000),
            "temperature": round(random.uniform(0.1, 1.0), 1),
            "top_p": round(random.uniform(0.1, 1.0), 1),
            "top_k": random.randint(1, 100),
            "stop_sequences": []
        }
        defaults.update(kwargs)
        return TextGenerationRequest(**defaults)
    
    def generate_gemini_chat_request(self, num_messages: int = 3, **kwargs) -> ChatCompletionRequest:
        """生成Gemini对话请求"""
        messages = []
        for i in range(num_messages):
            role = MessageRole.USER if i % 2 == 0 else MessageRole.MODEL
            content = self.generate_text_content(10, 100)
            messages.append(GeminiMessage(role=role, content=content))
        
        defaults = {
            "messages": messages,
            "model": random.choice(list(GeminiModel)),
            "max_tokens": random.randint(100, 1000),
            "temperature": round(random.uniform(0.1, 1.0), 1),
            "system_instruction": "You are a helpful assistant."
        }
        defaults.update(kwargs)
        return ChatCompletionRequest(**defaults)
    
    def generate_text_analysis_request(self, **kwargs) -> TextAnalysisRequest:
        """生成文本分析请求"""
        analysis_types = ["general", "sentiment", "summarize", "keywords", "entities", "classify"]
        
        defaults = {
            "text": self.generate_text_content(100, 500),
            "model": random.choice(list(GeminiModel)),
            "analysis_type": random.choice(analysis_types),
            "language": random.choice(["zh", "en", "auto"]),
            "max_tokens": random.randint(200, 800),
            "temperature": round(random.uniform(0.1, 0.5), 1)
        }
        defaults.update(kwargs)
        return TextAnalysisRequest(**defaults)
    
    def generate_image_request(self, **kwargs) -> ImageGenerationRequest:
        """生成图像生成请求"""
        prompts = [
            "一只可爱的小猫在花园里玩耍",
            "未来城市的天际线，科技感十足",
            "宁静的湖泊，倒映着夕阳",
            "古典风格的建筑，细节精美",
            "抽象艺术，色彩丰富"
        ]
        
        defaults = {
            "prompt": random.choice(prompts),
            "model": "imagen-3.0-generate-001",
            "num_images": random.randint(1, 4),
            "aspect_ratio": random.choice(["1:1", "4:3", "16:9", "9:16"]),
            "output_mode": random.choice(["file", "base64"])
        }
        defaults.update(kwargs)
        return ImageGenerationRequest(**defaults)
    
    def generate_video_request(self, **kwargs) -> VideoGenerationRequest:
        """生成视频生成请求"""
        prompts = [
            "一个美丽的自然风景，微风轻拂",
            "城市街道上车辆来往，生活气息浓厚",
            "海浪轻抚沙滩，阳光洒向大海",
            "森林中动物自由奔跑，充满活力",
            "夜空中星星闪烁，宁静祥和"
        ]
        
        defaults = {
            "prompt": random.choice(prompts),
            "model": KlingModel.KLING_PRO,
            "duration": random.choice([5, 10, 15, 30]),
            "aspect_ratio": random.choice(["16:9", "9:16", "1:1"]),
            "output_mode": random.choice(["file", "base64"])
        }
        defaults.update(kwargs)
        return VideoGenerationRequest(**defaults)
    
    def generate_api_response(self, response_type: str = "text") -> Dict[str, Any]:
        """生成API响应数据"""
        if response_type == "text":
            return {
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": self.generate_text_content(50, 200)
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": random.randint(10, 100),
                    "completion_tokens": random.randint(50, 300),
                    "total_tokens": random.randint(60, 400)
                }
            }
        
        elif response_type == "image":
            return {
                "images": [{
                    "data": self._generate_base64_data(),
                    "format": "png"
                } for _ in range(random.randint(1, 3))],
                "usage": {
                    "prompt_tokens": random.randint(10, 50)
                }
            }
        
        elif response_type == "video":
            return {
                "video_url": f"https://example.com/video_{uuid.uuid4().hex}.mp4",
                "task_id": str(uuid.uuid4()),
                "status": "completed",
                "duration": random.randint(5, 30)
            }
        
        return {}
    
    def generate_dag_node(self, **kwargs) -> DAGNode:
        """生成DAG节点"""
        defaults = {
            "id": f"step_{uuid.uuid4().hex[:8]}",
            "name": f"测试步骤 {random.randint(1, 100)}",
            "type": random.choice(["text_generation", "image_generation", "video_generation"]),
            "config": {"param": random.randint(1, 10)},
            "dependencies": [],
            "status": random.choice(list(NodeStatus)),
            "max_retries": 3
        }
        defaults.update(kwargs)
        return DAGNode(**defaults)
    
    def generate_workflow_context(self) -> Dict[str, Any]:
        """生成工作流上下文"""
        return {
            "user_input": self.generate_text_content(20, 100),
            "theme": self.generate_story_theme(),
            "style": random.choice(["realistic", "cartoon", "abstract", "modern"]),
            "language": random.choice(["zh", "en"]),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def generate_workflow_steps(self, num_steps: int = 5) -> List[Dict[str, Any]]:
        """生成工作流步骤配置"""
        step_types = ["text_generation", "image_generation", "video_generation", "condition", "parallel"]
        steps = []
        
        for i in range(num_steps):
            step_id = f"step_{i+1}"
            step_type = random.choice(step_types)
            
            step = {
                "id": step_id,
                "name": f"步骤 {i+1}",
                "type": step_type,
                "config": self._generate_step_config(step_type),
                "dependencies": [f"step_{j+1}" for j in range(max(0, i-2), i) if random.random() < 0.3]
            }
            steps.append(step)
        
        return steps
    
    def _generate_step_config(self, step_type: str) -> Dict[str, Any]:
        """为特定步骤类型生成配置"""
        if step_type == "text_generation":
            return {
                "prompt": "{{user_input}}",
                "model": "gemini-1.5-flash-002",
                "max_tokens": random.randint(200, 1000),
                "temperature": round(random.uniform(0.3, 0.9), 1)
            }
        elif step_type == "image_generation":
            return {
                "prompt": "基于主题 {{theme}} 创建图像",
                "num_images": random.randint(1, 3),
                "aspect_ratio": random.choice(["1:1", "16:9", "4:3"])
            }
        elif step_type == "video_generation":
            return {
                "prompt": "为主题 {{theme}} 创建视频",
                "duration": random.choice([5, 10, 15]),
                "aspect_ratio": "16:9"
            }
        elif step_type == "condition":
            return {
                "condition": "{{user_input}} != ''",
                "true_branch": "continue",
                "false_branch": "skip"
            }
        elif step_type == "parallel":
            return {
                "steps": [
                    {
                        "type": "text_generation",
                        "config": {"prompt": "并行步骤1", "max_tokens": 100}
                    },
                    {
                        "type": "image_generation", 
                        "config": {"prompt": "并行步骤2", "num_images": 1}
                    }
                ]
            }
        
        return {}
    
    def _generate_base64_data(self) -> str:
        """生成假的base64数据"""
        # 生成假的图像数据（实际项目中会是真实的图像base64）
        fake_data = ''.join(random.choices(string.ascii_letters + string.digits, k=100))
        import base64
        return base64.b64encode(fake_data.encode()).decode()
    
    def generate_error_response(self, status_code: int = 400) -> Dict[str, Any]:
        """生成错误响应"""
        error_messages = {
            400: "Bad Request - 请求参数无效",
            401: "Unauthorized - 认证失败",
            403: "Forbidden - 无权限访问",
            404: "Not Found - 资源未找到",
            429: "Too Many Requests - 请求过于频繁",
            500: "Internal Server Error - 服务器内部错误",
            503: "Service Unavailable - 服务暂时不可用"
        }
        
        return {
            "error": {
                "code": status_code,
                "message": error_messages.get(status_code, "Unknown Error"),
                "details": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "request_id": str(uuid.uuid4())
                }
            }
        }
    
    def generate_file_paths(self, count: int = 3) -> List[str]:
        """生成文件路径"""
        extensions = ['.png', '.jpg', '.mp4', '.txt', '.json']
        paths = []
        for _ in range(count):
            filename = f"{uuid.uuid4().hex[:8]}{random.choice(extensions)}"
            path = f"/tmp/gemini_kling_mcp/{filename}"
            paths.append(path)
        return paths
    
    def generate_performance_metrics(self) -> Dict[str, float]:
        """生成性能指标"""
        return {
            "response_time": round(random.uniform(0.1, 5.0), 3),
            "throughput": round(random.uniform(1.0, 100.0), 2),
            "error_rate": round(random.uniform(0.0, 0.1), 4),
            "cpu_usage": round(random.uniform(0.1, 0.9), 3),
            "memory_usage": round(random.uniform(0.2, 0.8), 3)
        }
    
    def generate_batch_test_data(self, batch_size: int = 10) -> List[Dict[str, Any]]:
        """生成批量测试数据"""
        batch_data = []
        for i in range(batch_size):
            data = {
                "id": f"test_{i+1}",
                "input": {
                    "prompt": self.generate_text_content(20, 100),
                    "theme": self.generate_story_theme()
                },
                "expected_output_type": random.choice(["text", "image", "video"]),
                "priority": random.randint(1, 5),
                "timeout": random.randint(30, 300)
            }
            batch_data.append(data)
        return batch_data


# 全局测试数据生成器实例
test_data_generator = TestDataGenerator()