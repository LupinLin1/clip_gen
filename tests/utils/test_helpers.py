"""
测试辅助工具

提供常用的测试辅助函数和装饰器。
"""

import os
import asyncio
import tempfile
import functools
from pathlib import Path
from typing import Any, Dict, List, Callable, Optional
from unittest.mock import AsyncMock, Mock
import json
import time


def async_test_timeout(timeout: float = 30.0):
    """异步测试超时装饰器"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
        return wrapper
    return decorator


def retry_on_failure(max_retries: int = 3, delay: float = 0.1):
    """失败重试装饰器"""
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        await asyncio.sleep(delay * (attempt + 1))
                        continue
                    raise last_exception
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        time.sleep(delay * (attempt + 1))
                        continue
                    raise last_exception
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    return decorator


class TestDataBuilder:
    """测试数据构建器"""
    
    @staticmethod
    def create_mock_response(success: bool = True, **data) -> Dict[str, Any]:
        """创建Mock响应"""
        response = {
            "success": success,
            "timestamp": time.time()
        }
        if success:
            response.update(data)
        else:
            response["error"] = data.get("error", "Test error")
        return response
    
    @staticmethod
    def create_workflow_context(**kwargs) -> Dict[str, Any]:
        """创建工作流上下文"""
        default_context = {
            "story_theme": "测试故事主题",
            "style": "cartoon",
            "duration": 10,
            "language": "zh"
        }
        default_context.update(kwargs)
        return default_context
    
    @staticmethod
    def create_image_response(
        num_images: int = 1,
        output_mode: str = "file"
    ) -> Dict[str, Any]:
        """创建图像响应数据"""
        if output_mode == "file":
            return {
                "success": True,
                "images": [
                    {
                        "file_path": f"/tmp/image_{i+1}.jpg",
                        "description": f"测试图像{i+1}",
                        "size": {"width": 1024, "height": 1024}
                    }
                    for i in range(num_images)
                ]
            }
        else:  # base64
            return {
                "success": True,
                "images": [
                    {
                        "base64_data": f"data:image/jpeg;base64,fake_base64_data_{i+1}",
                        "description": f"测试图像{i+1}",
                        "size": {"width": 1024, "height": 1024}
                    }
                    for i in range(num_images)
                ]
            }
    
    @staticmethod
    def create_video_response(task_id: str = None) -> Dict[str, Any]:
        """创建视频响应数据"""
        return {
            "success": True,
            "task_id": task_id or "test_video_task_123",
            "status": "completed",
            "video_url": "https://example.com/test_video.mp4",
            "thumbnail_url": "https://example.com/test_thumb.jpg",
            "metadata": {
                "duration": 10,
                "width": 1920,
                "height": 1080,
                "file_size": 1024000
            }
        }
    
    @staticmethod
    def create_story_script(num_scenes: int = 3) -> Dict[str, Any]:
        """创建故事脚本数据"""
        return {
            "title": "测试故事",
            "theme": "测试主题",
            "total_duration": 15,
            "scenes": [
                {
                    "scene_id": f"scene_{i+1}",
                    "description": f"场景{i+1}描述",
                    "dialogue": f"场景{i+1}对话",
                    "duration": 5,
                    "image_prompt": f"场景{i+1}图像提示"
                }
                for i in range(num_scenes)
            ]
        }


class MockServiceFactory:
    """Mock服务工厂"""
    
    @staticmethod
    def create_gemini_text_service(
        enable_errors: bool = False,
        error_rate: float = 0.0
    ) -> Mock:
        """创建Gemini文本服务Mock"""
        service = AsyncMock()
        
        async def mock_generate_text(*args, **kwargs):
            if enable_errors and error_rate > 0:
                import random
                if random.random() < error_rate:
                    raise Exception("Mock Gemini text generation error")
            
            return AsyncMock(
                text="模拟生成的文本内容",
                model="gemini-1.5-flash",
                finish_reason="stop"
            )
        
        async def mock_complete_chat(*args, **kwargs):
            if enable_errors and error_rate > 0:
                import random
                if random.random() < error_rate:
                    raise Exception("Mock chat completion error")
            
            return AsyncMock(
                message=AsyncMock(
                    role="model",
                    content="模拟的对话回复"
                )
            )
        
        service.generate_text = mock_generate_text
        service.complete_chat = mock_complete_chat
        service.close = AsyncMock()
        
        return service
    
    @staticmethod
    def create_gemini_image_service(
        enable_errors: bool = False,
        error_rate: float = 0.0
    ) -> Mock:
        """创建Gemini图像服务Mock"""
        service = AsyncMock()
        
        async def mock_generate_image(*args, **kwargs):
            if enable_errors and error_rate > 0:
                import random
                if random.random() < error_rate:
                    raise Exception("Mock image generation error")
            
            # 根据请求参数决定返回格式
            request = args[0] if args else kwargs
            output_mode = getattr(request, 'output_mode', 'file') if hasattr(request, 'output_mode') else request.get('output_mode', 'file')
            
            if output_mode == "base64":
                return AsyncMock(
                    images=[
                        {
                            "data": "data:image/jpeg;base64,fake_base64_data",
                            "size": {"width": 1024, "height": 1024}
                        }
                    ],
                    model="imagen-3.0-generate-001"
                )
            else:
                return AsyncMock(
                    file_paths=["/tmp/mock_image.jpg"],
                    model="imagen-3.0-generate-001"
                )
        
        service.generate_image = mock_generate_image
        service.close = AsyncMock()
        
        return service
    
    @staticmethod
    def create_kling_video_service(
        enable_errors: bool = False,
        error_rate: float = 0.0
    ) -> Mock:
        """创建Kling视频服务Mock"""
        service = AsyncMock()
        
        async def mock_text_to_video(*args, **kwargs):
            if enable_errors and error_rate > 0:
                import random
                if random.random() < error_rate:
                    raise Exception("Mock video generation error")
            
            return AsyncMock(
                task_id="mock_video_task_123",
                status=AsyncMock(value="completed"),
                result=AsyncMock(
                    video_url="https://example.com/mock_video.mp4",
                    thumbnail_url="https://example.com/mock_thumb.jpg",
                    duration=10,
                    width=1920,
                    height=1080
                )
            )
        
        async def mock_get_task_status(*args, **kwargs):
            return AsyncMock(
                task_id=args[0] if args else "mock_task_123",
                status=AsyncMock(value="completed"),
                result=AsyncMock(
                    video_url="https://example.com/completed_video.mp4"
                )
            )
        
        service.text_to_video = mock_text_to_video
        service.image_to_video = mock_text_to_video  # 复用逻辑
        service.get_task_status = mock_get_task_status
        service.cancel_task = AsyncMock(return_value=True)
        service.close = AsyncMock()
        
        return service


class FileTestHelper:
    """文件测试辅助工具"""
    
    @staticmethod
    def create_temp_file(
        content: str = "test content",
        suffix: str = ".txt",
        prefix: str = "test_",
        dir: Optional[str] = None
    ) -> Path:
        """创建临时测试文件"""
        import tempfile
        
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix=suffix,
            prefix=prefix,
            dir=dir,
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(content)
            return Path(f.name)
    
    @staticmethod
    def create_temp_dir(prefix: str = "test_dir_") -> Path:
        """创建临时测试目录"""
        return Path(tempfile.mkdtemp(prefix=prefix))
    
    @staticmethod
    def cleanup_temp_files(files: List[Path]) -> None:
        """清理临时文件"""
        for file_path in files:
            try:
                if file_path.exists():
                    if file_path.is_dir():
                        import shutil
                        shutil.rmtree(file_path)
                    else:
                        file_path.unlink()
            except Exception:
                pass  # 忽略清理错误
    
    @staticmethod
    def assert_file_exists(file_path: Path, message: str = None) -> None:
        """断言文件存在"""
        assert file_path.exists(), message or f"文件不存在: {file_path}"
    
    @staticmethod
    def assert_file_content(file_path: Path, expected_content: str) -> None:
        """断言文件内容"""
        assert file_path.exists(), f"文件不存在: {file_path}"
        actual_content = file_path.read_text(encoding='utf-8')
        assert actual_content == expected_content, f"文件内容不匹配: 期望 {expected_content}, 实际 {actual_content}"


class AsyncTestHelper:
    """异步测试辅助工具"""
    
    @staticmethod
    async def run_with_timeout(coro, timeout: float = 10.0):
        """运行协程并设置超时"""
        return await asyncio.wait_for(coro, timeout=timeout)
    
    @staticmethod
    async def gather_with_exceptions(*coros, return_exceptions: bool = True):
        """并发执行协程并处理异常"""
        return await asyncio.gather(*coros, return_exceptions=return_exceptions)
    
    @staticmethod
    def create_event_loop():
        """创建新的事件循环"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop
    
    @staticmethod
    async def wait_for_condition(
        condition_func: Callable[[], bool],
        timeout: float = 5.0,
        interval: float = 0.1
    ) -> bool:
        """等待条件满足"""
        end_time = time.time() + timeout
        
        while time.time() < end_time:
            if condition_func():
                return True
            await asyncio.sleep(interval)
        
        return False


class PerformanceTestHelper:
    """性能测试辅助工具"""
    
    @staticmethod
    def measure_execution_time(func):
        """测量执行时间装饰器"""
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result, time.time() - start_time
            except Exception as e:
                return e, time.time() - start_time
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result, time.time() - start_time
            except Exception as e:
                return e, time.time() - start_time
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    @staticmethod
    def assert_performance_within_bounds(
        execution_time: float,
        max_time: float,
        operation_name: str = "操作"
    ):
        """断言性能在预期范围内"""
        assert execution_time <= max_time, (
            f"{operation_name}执行时间过长: {execution_time:.3f}s > {max_time:.3f}s"
        )
    
    @staticmethod
    def calculate_throughput(
        successful_operations: int,
        execution_time: float
    ) -> float:
        """计算吞吐量"""
        return successful_operations / execution_time if execution_time > 0 else 0.0


class ValidationHelper:
    """验证辅助工具"""
    
    @staticmethod
    def validate_response_structure(response: Dict[str, Any], required_keys: List[str]):
        """验证响应结构"""
        assert isinstance(response, dict), "响应必须是字典类型"
        
        for key in required_keys:
            assert key in response, f"响应缺少必需字段: {key}"
    
    @staticmethod
    def validate_success_response(response: Dict[str, Any]):
        """验证成功响应"""
        ValidationHelper.validate_response_structure(response, ["success"])
        assert response["success"] is True, f"操作失败: {response}"
    
    @staticmethod
    def validate_error_response(response: Dict[str, Any]):
        """验证错误响应"""
        ValidationHelper.validate_response_structure(response, ["success"])
        assert response["success"] is False, "期望失败但操作成功"
        assert "error" in response, "错误响应缺少错误信息"
    
    @staticmethod
    def validate_workflow_result(result: Dict[str, Any]):
        """验证工作流结果"""
        required_keys = [
            "success", "workflow_id", "story_script", 
            "scene_images", "video_url", "file_paths", "metadata"
        ]
        ValidationHelper.validate_response_structure(result, required_keys)
        ValidationHelper.validate_success_response(result)
        
        # 验证故事脚本结构
        story_script = result["story_script"]
        assert isinstance(story_script, dict), "故事脚本必须是字典"
        assert "scenes" in story_script, "故事脚本缺少场景信息"
        assert len(story_script["scenes"]) > 0, "故事脚本场景列表为空"
        
        # 验证场景图像
        scene_images = result["scene_images"]
        assert isinstance(scene_images, list), "场景图像必须是列表"
        assert len(scene_images) > 0, "场景图像列表为空"
        
        # 验证元数据
        metadata = result["metadata"]
        assert isinstance(metadata, dict), "元数据必须是字典"
        assert "execution_time" in metadata, "元数据缺少执行时间"


class EnvironmentHelper:
    """环境辅助工具"""
    
    @staticmethod
    def set_test_env_vars(env_vars: Dict[str, str]):
        """设置测试环境变量"""
        for key, value in env_vars.items():
            os.environ[key] = value
    
    @staticmethod
    def cleanup_test_env_vars(env_vars: List[str]):
        """清理测试环境变量"""
        for key in env_vars:
            os.environ.pop(key, None)
    
    @staticmethod
    def get_test_data_dir() -> Path:
        """获取测试数据目录"""
        return Path(__file__).parent.parent / "data"
    
    @staticmethod
    def ensure_test_dirs(*dirs: str) -> List[Path]:
        """确保测试目录存在"""
        paths = []
        for dir_name in dirs:
            dir_path = Path(dir_name)
            dir_path.mkdir(parents=True, exist_ok=True)
            paths.append(dir_path)
        return paths