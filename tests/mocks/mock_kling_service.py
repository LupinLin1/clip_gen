"""
Kling服务Mock实现

提供Kling视频生成API的Mock服务，用于测试时替代真实API调用。
"""

import asyncio
import random
import time
import uuid
from typing import Dict, Any, Optional
from unittest.mock import AsyncMock, Mock

from src.gemini_kling_mcp.services.kling.models import (
    VideoGenerationRequest, VideoGenerationResponse, KlingModel
)
from src.gemini_kling_mcp.exceptions import KlingAPIError
from tests.test_data_generator import test_data_generator


class MockKlingService:
    """Mock Kling视频生成服务"""
    
    def __init__(self, enable_errors: bool = False, delay_range: tuple = (5.0, 15.0)):
        self.enable_errors = enable_errors
        self.delay_range = delay_range
        self.call_count = 0
        self.last_request = None
        self.active_tasks = {}
        
    async def _simulate_delay(self):
        """模拟视频生成延迟"""
        delay = random.uniform(*self.delay_range)
        await asyncio.sleep(delay)
    
    def _should_fail(self) -> bool:
        """决定是否模拟失败"""
        return self.enable_errors and random.random() < 0.08  # 8% 失败率
    
    async def generate_video(self, request: VideoGenerationRequest) -> VideoGenerationResponse:
        """生成视频Mock"""
        self.call_count += 1
        self.last_request = request
        
        task_id = str(uuid.uuid4())
        self.active_tasks[task_id] = {
            "request": request,
            "status": "processing",
            "start_time": time.time()
        }
        
        # 模拟视频生成时间
        await self._simulate_delay()
        
        if self._should_fail():
            self.active_tasks[task_id]["status"] = "failed"
            raise KlingAPIError("Mock API error: Video generation failed")
        
        # 生成Mock视频响应
        if request.output_mode == "base64":
            # 生成假的base64视频数据
            video_data = self._generate_fake_base64_video()
            file_path = None
        else:
            video_data = None
            file_path = f"/tmp/gemini_kling_mcp/video_{task_id[:8]}.mp4"
        
        self.active_tasks[task_id]["status"] = "completed"
        
        return VideoGenerationResponse(
            video_url=f"https://mock-kling.com/video/{task_id}" if not request.output_mode == "base64" else None,
            video_data=video_data,
            file_path=file_path,
            task_id=task_id,
            status="completed",
            duration=request.duration,
            model=request.model.value
        )
    
    async def get_video_status(self, task_id: str) -> Dict[str, Any]:
        """获取视频生成状态Mock"""
        if task_id not in self.active_tasks:
            raise KlingAPIError(f"Task {task_id} not found")
        
        task = self.active_tasks[task_id]
        elapsed = time.time() - task["start_time"]
        
        # 模拟进度更新
        if task["status"] == "processing":
            progress = min(90, int(elapsed / 10 * 100))  # 每10秒增加100%进度
            if elapsed > 10:  # 10秒后完成
                task["status"] = "completed"
                progress = 100
        else:
            progress = 100
        
        return {
            "task_id": task_id,
            "status": task["status"],
            "progress": progress,
            "estimated_time": max(0, 10 - elapsed) if task["status"] == "processing" else 0
        }
    
    def _generate_fake_base64_video(self) -> str:
        """生成假的base64视频数据"""
        # 模拟MP4文件头
        fake_mp4_header = b'\x00\x00\x00\x20ftypmp41'
        fake_data = fake_mp4_header + b'x' * 200  # 添加一些假数据
        import base64
        return base64.b64encode(fake_data).decode()
    
    def reset_stats(self):
        """重置统计信息"""
        self.call_count = 0
        self.last_request = None
        self.active_tasks.clear()


class MockKlingClient:
    """Mock Kling HTTP客户端"""
    
    def __init__(self, config, enable_errors: bool = False):
        self.config = config
        self.enable_errors = enable_errors
        self.request_history = []
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
        
    async def generate_video(self, request_data):
        """Mock视频生成"""
        self.request_history.append(("generate_video", request_data))
        
        if self.enable_errors and random.random() < 0.1:
            raise Exception("Mock Kling network error")
        
        # 模拟较长的视频生成延迟
        await asyncio.sleep(random.uniform(5.0, 10.0))
        
        return test_data_generator.generate_api_response("video")
    
    async def get_task_status(self, task_id):
        """Mock任务状态查询"""
        self.request_history.append(("get_task_status", task_id))
        
        return {
            "task_id": task_id,
            "status": "completed",
            "progress": 100,
            "video_url": f"https://mock-kling.com/video/{task_id}"
        }


def create_mock_kling_service(enable_errors: bool = False) -> MockKlingService:
    """创建Mock Kling服务"""
    return MockKlingService(enable_errors=enable_errors)


def create_mock_kling_client(config, enable_errors: bool = False) -> MockKlingClient:
    """创建Mock Kling客户端"""
    return MockKlingClient(config, enable_errors=enable_errors)