"""
系统性能测试

测试各组件和工作流在不同负载下的性能表现。
"""

import pytest
import asyncio
import time
import statistics
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any
from unittest.mock import patch, AsyncMock

from src.gemini_kling_mcp.tools.workflow.story_video_generator import (
    generate_story_video, generate_story_video_batch
)
from src.gemini_kling_mcp.tools.image_generation import generate_image
from src.gemini_kling_mcp.tools.kling_video import generate_video
from src.gemini_kling_mcp.workflow.engine import WorkflowEngine
from src.gemini_kling_mcp.workflow.state_manager import WorkflowStateManager, JSONFileBackend
from src.gemini_kling_mcp.workflow.templates import template_library
from src.gemini_kling_mcp.file_manager.core import TempFileManager
from tests.mocks import (
    create_mock_gemini_service,
    create_mock_gemini_image_service,
    create_mock_kling_service
)


class PerformanceTimer:
    """性能计时器"""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
    
    @property
    def elapsed(self) -> float:
        """获取执行时间"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0


@pytest.mark.performance
class TestSingleOperationPerformance:
    """单操作性能测试"""
    
    @pytest.fixture
    def performance_mock_services(self):
        """性能测试Mock服务"""
        # 创建响应较快的Mock服务
        gemini = create_mock_gemini_service(enable_errors=False)
        gemini_image = create_mock_gemini_image_service(enable_errors=False)
        kling = create_mock_kling_service(enable_errors=False)
        
        # 减少模拟延迟以专注于系统开销测试
        def fast_async_mock():
            async def mock_func(*args, **kwargs):
                await asyncio.sleep(0.001)  # 1ms模拟延迟
                return AsyncMock()()
            return mock_func
        
        gemini.generate_text = fast_async_mock()
        gemini_image.generate_image = fast_async_mock()
        kling.text_to_video = fast_async_mock()
        
        return {'gemini': gemini, 'gemini_image': gemini_image, 'kling': kling}
    
    @pytest.mark.asyncio
    async def test_story_video_generation_performance(
        self, 
        temp_dir, 
        performance_mock_services
    ):
        """测试故事视频生成性能"""
        with patch('src.gemini_kling_mcp.workflow.steps.GeminiTextService', return_value=performance_mock_services['gemini']), \
             patch('src.gemini_kling_mcp.workflow.steps.GeminiImageService', return_value=performance_mock_services['gemini_image']), \
             patch('src.gemini_kling_mcp.workflow.steps.KlingVideoService', return_value=performance_mock_services['kling']), \
             patch('src.gemini_kling_mcp.workflow.state_manager.JSONFileBackend') as mock_backend:
            
            mock_backend.return_value.storage_dir = temp_dir
            mock_backend.return_value.save_state = AsyncMock()
            mock_backend.return_value.load_state = AsyncMock(return_value={})
            mock_backend.return_value.list_workflows = AsyncMock(return_value=[])
            mock_backend.return_value.delete_state = AsyncMock()
            
            execution_times = []
            
            # 执行多次测试获取平均性能
            for i in range(5):
                with PerformanceTimer() as timer:
                    result = await generate_story_video(
                        story_theme=f"性能测试主题{i+1}",
                        style="cartoon",
                        duration=5,
                        output_mode="base64"
                    )
                
                assert result["success"] is True
                execution_times.append(timer.elapsed)
            
            # 性能分析
            avg_time = statistics.mean(execution_times)
            min_time = min(execution_times)
            max_time = max(execution_times)
            std_dev = statistics.stdev(execution_times) if len(execution_times) > 1 else 0
            
            print(f"\n故事视频生成性能统计:")
            print(f"平均执行时间: {avg_time:.3f}s")
            print(f"最短执行时间: {min_time:.3f}s") 
            print(f"最长执行时间: {max_time:.3f}s")
            print(f"标准差: {std_dev:.3f}s")
            
            # 性能断言（根据实际情况调整阈值）
            assert avg_time < 5.0, f"平均执行时间过长: {avg_time:.3f}s"
            assert max_time < 10.0, f"最长执行时间过长: {max_time:.3f}s"
    
    @pytest.mark.asyncio
    async def test_image_generation_performance(self, performance_mock_services):
        """测试图像生成性能"""
        with patch('src.gemini_kling_mcp.tools.image_generation.GeminiImageService', return_value=performance_mock_services['gemini_image']):
            
            execution_times = []
            
            for i in range(10):
                with PerformanceTimer() as timer:
                    result = await generate_image(
                        prompt=f"性能测试图像{i+1}",
                        num_images=1,
                        output_mode="base64"
                    )
                
                assert result["success"] is True
                execution_times.append(timer.elapsed)
            
            avg_time = statistics.mean(execution_times)
            max_time = max(execution_times)
            
            print(f"\n图像生成性能统计:")
            print(f"平均执行时间: {avg_time:.3f}s")
            print(f"最长执行时间: {max_time:.3f}s")
            
            # 图像生成应该更快
            assert avg_time < 1.0, f"图像生成平均时间过长: {avg_time:.3f}s"
            assert max_time < 2.0, f"图像生成最长时间过长: {max_time:.3f}s"
    
    @pytest.mark.asyncio
    async def test_video_generation_performance(self, performance_mock_services):
        """测试视频生成性能"""
        with patch('src.gemini_kling_mcp.tools.kling_video.KlingVideoService', return_value=performance_mock_services['kling']):
            
            execution_times = []
            
            for i in range(5):
                with PerformanceTimer() as timer:
                    result = await generate_video(
                        prompt=f"性能测试视频{i+1}",
                        mode="standard",
                        duration=5,
                        wait_for_completion=False
                    )
                
                assert result["success"] is True
                execution_times.append(timer.elapsed)
            
            avg_time = statistics.mean(execution_times)
            max_time = max(execution_times)
            
            print(f"\n视频生成性能统计:")
            print(f"平均执行时间: {avg_time:.3f}s")
            print(f"最长执行时间: {max_time:.3f}s")
            
            # 视频生成请求提交应该很快
            assert avg_time < 2.0, f"视频生成平均时间过长: {avg_time:.3f}s"


@pytest.mark.performance
class TestConcurrencyPerformance:
    """并发性能测试"""
    
    @pytest.fixture
    def concurrent_mock_services(self):
        """并发测试Mock服务"""
        return {
            'gemini': create_mock_gemini_service(enable_errors=False),
            'gemini_image': create_mock_gemini_image_service(enable_errors=False),
            'kling': create_mock_kling_service(enable_errors=False)
        }
    
    @pytest.mark.asyncio
    async def test_concurrent_story_video_generation(
        self, 
        temp_dir, 
        concurrent_mock_services
    ):
        """测试并发故事视频生成性能"""
        with patch('src.gemini_kling_mcp.workflow.steps.GeminiTextService', return_value=concurrent_mock_services['gemini']), \
             patch('src.gemini_kling_mcp.workflow.steps.GeminiImageService', return_value=concurrent_mock_services['gemini_image']), \
             patch('src.gemini_kling_mcp.workflow.steps.KlingVideoService', return_value=concurrent_mock_services['kling']), \
             patch('src.gemini_kling_mcp.workflow.state_manager.JSONFileBackend') as mock_backend:
            
            mock_backend.return_value.storage_dir = temp_dir
            mock_backend.return_value.save_state = AsyncMock()
            mock_backend.return_value.load_state = AsyncMock(return_value={})
            mock_backend.return_value.list_workflows = AsyncMock(return_value=[])
            mock_backend.return_value.delete_state = AsyncMock()
            
            # 测试不同并发级别
            concurrency_levels = [1, 2, 4, 8]
            
            for concurrent_count in concurrency_levels:
                print(f"\n测试 {concurrent_count} 个并发任务:")
                
                tasks = []
                for i in range(concurrent_count):
                    task = generate_story_video(
                        story_theme=f"并发测试{concurrent_count}_{i+1}",
                        style="cartoon",
                        duration=5,
                        output_mode="base64"
                    )
                    tasks.append(task)
                
                with PerformanceTimer() as timer:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 验证所有任务成功
                success_count = 0
                for result in results:
                    if not isinstance(result, Exception) and result.get("success"):
                        success_count += 1
                
                throughput = success_count / timer.elapsed if timer.elapsed > 0 else 0
                
                print(f"总执行时间: {timer.elapsed:.3f}s")
                print(f"成功任务数: {success_count}/{concurrent_count}")
                print(f"吞吐量: {throughput:.2f} 任务/秒")
                
                # 性能断言
                assert success_count == concurrent_count, f"并发任务失败: {success_count}/{concurrent_count}"
                assert timer.elapsed < 20.0, f"并发执行时间过长: {timer.elapsed:.3f}s"
    
    @pytest.mark.asyncio
    async def test_batch_processing_performance(
        self, 
        temp_dir, 
        concurrent_mock_services
    ):
        """测试批量处理性能"""
        with patch('src.gemini_kling_mcp.workflow.steps.GeminiTextService', return_value=concurrent_mock_services['gemini']), \
             patch('src.gemini_kling_mcp.workflow.steps.GeminiImageService', return_value=concurrent_mock_services['gemini_image']), \
             patch('src.gemini_kling_mcp.workflow.steps.KlingVideoService', return_value=concurrent_mock_services['kling']), \
             patch('src.gemini_kling_mcp.workflow.state_manager.JSONFileBackend') as mock_backend:
            
            mock_backend.return_value.storage_dir = temp_dir
            mock_backend.return_value.save_state = AsyncMock()
            mock_backend.return_value.load_state = AsyncMock(return_value={})
            mock_backend.return_value.list_workflows = AsyncMock(return_value=[])
            mock_backend.return_value.delete_state = AsyncMock()
            
            # 测试不同批量大小
            batch_sizes = [5, 10, 15]
            
            for batch_size in batch_sizes:
                print(f"\n测试批量大小: {batch_size}")
                
                story_themes = [f"批量性能测试{i+1}" for i in range(batch_size)]
                
                with PerformanceTimer() as timer:
                    result = await generate_story_video_batch(
                        story_themes=story_themes,
                        concurrent_limit=3,
                        style="cartoon",
                        duration=5
                    )
                
                assert result["success"] is True
                
                successful = result["summary"]["successful"]
                throughput = successful / timer.elapsed if timer.elapsed > 0 else 0
                
                print(f"执行时间: {timer.elapsed:.3f}s")
                print(f"成功任务数: {successful}/{batch_size}")
                print(f"吞吐量: {throughput:.2f} 任务/秒")
                
                # 性能断言
                assert successful >= batch_size * 0.8, f"成功率过低: {successful}/{batch_size}"
                assert timer.elapsed < batch_size * 2.0, f"批量处理时间过长: {timer.elapsed:.3f}s"
    
    @pytest.mark.asyncio
    async def test_mixed_workload_performance(
        self, 
        temp_dir,
        concurrent_mock_services
    ):
        """测试混合工作负载性能"""
        with patch('src.gemini_kling_mcp.tools.image_generation.GeminiImageService', return_value=concurrent_mock_services['gemini_image']), \
             patch('src.gemini_kling_mcp.tools.kling_video.KlingVideoService', return_value=concurrent_mock_services['kling']), \
             patch('src.gemini_kling_mcp.workflow.steps.GeminiTextService', return_value=concurrent_mock_services['gemini']), \
             patch('src.gemini_kling_mcp.workflow.steps.GeminiImageService', return_value=concurrent_mock_services['gemini_image']), \
             patch('src.gemini_kling_mcp.workflow.steps.KlingVideoService', return_value=concurrent_mock_services['kling']), \
             patch('src.gemini_kling_mcp.workflow.state_manager.JSONFileBackend') as mock_backend:
            
            mock_backend.return_value.storage_dir = temp_dir
            mock_backend.return_value.save_state = AsyncMock()
            mock_backend.return_value.load_state = AsyncMock(return_value={})
            mock_backend.return_value.list_workflows = AsyncMock(return_value=[])
            mock_backend.return_value.delete_state = AsyncMock()
            
            print("\n测试混合工作负载性能:")
            
            # 创建混合任务
            tasks = []
            
            # 图像生成任务
            for i in range(3):
                task = generate_image(
                    prompt=f"混合测试图像{i+1}",
                    num_images=1,
                    output_mode="base64"
                )
                tasks.append(("image", task))
            
            # 视频生成任务
            for i in range(2):
                task = generate_video(
                    prompt=f"混合测试视频{i+1}",
                    mode="standard",
                    duration=5,
                    wait_for_completion=False
                )
                tasks.append(("video", task))
            
            # 故事视频生成任务
            for i in range(2):
                task = generate_story_video(
                    story_theme=f"混合测试故事{i+1}",
                    style="cartoon",
                    duration=5,
                    output_mode="base64"
                )
                tasks.append(("story", task))
            
            with PerformanceTimer() as timer:
                # 并发执行所有任务
                task_results = await asyncio.gather(
                    *[task for _, task in tasks], 
                    return_exceptions=True
                )
            
            # 统计结果
            task_stats = {"image": 0, "video": 0, "story": 0}
            success_count = 0
            
            for i, (task_type, result) in enumerate(zip([t[0] for t in tasks], task_results)):
                if not isinstance(result, Exception) and result.get("success"):
                    task_stats[task_type] += 1
                    success_count += 1
            
            total_tasks = len(tasks)
            throughput = success_count / timer.elapsed if timer.elapsed > 0 else 0
            
            print(f"总执行时间: {timer.elapsed:.3f}s")
            print(f"总任务数: {total_tasks}")
            print(f"成功任务数: {success_count}")
            print(f"图像任务成功: {task_stats['image']}/3")
            print(f"视频任务成功: {task_stats['video']}/2") 
            print(f"故事任务成功: {task_stats['story']}/2")
            print(f"整体吞吐量: {throughput:.2f} 任务/秒")
            
            # 性能断言
            assert success_count >= total_tasks * 0.8, f"混合工作负载成功率过低: {success_count}/{total_tasks}"
            assert timer.elapsed < 30.0, f"混合工作负载执行时间过长: {timer.elapsed:.3f}s"


@pytest.mark.performance
class TestMemoryAndResourcePerformance:
    """内存和资源性能测试"""
    
    @pytest.mark.asyncio
    async def test_workflow_state_management_performance(self, temp_dir):
        """测试工作流状态管理性能"""
        backend = JSONFileBackend(temp_dir)
        state_manager = WorkflowStateManager(backend)
        engine = WorkflowEngine(state_manager)
        
        template = template_library.get_template("story_video_generation")
        workflow_operations = []
        
        print("\n测试工作流状态管理性能:")
        
        # 创建多个工作流
        with PerformanceTimer() as create_timer:
            workflow_ids = []
            for i in range(20):
                workflow_id = await engine.create_workflow(
                    config=template.config,
                    steps_config=template.steps[:2],  # 只使用前2个步骤
                    initial_context={"story_theme": f"性能测试工作流{i+1}"}
                )
                workflow_ids.append(workflow_id)
        
        print(f"创建 20 个工作流耗时: {create_timer.elapsed:.3f}s")
        
        # 批量查询状态
        with PerformanceTimer() as query_timer:
            for workflow_id in workflow_ids:
                status = await engine.get_workflow_status(workflow_id)
                assert status is not None
        
        print(f"查询 20 个工作流状态耗时: {query_timer.elapsed:.3f}s")
        
        # 批量导出定义
        with PerformanceTimer() as export_timer:
            definitions = []
            for workflow_id in workflow_ids:
                definition = await engine.export_workflow_definition(workflow_id)
                definitions.append(definition)
        
        print(f"导出 20 个工作流定义耗时: {export_timer.elapsed:.3f}s")
        
        # 批量导入定义
        with PerformanceTimer() as import_timer:
            imported_ids = []
            for definition in definitions:
                imported_id = await engine.import_workflow_definition(definition)
                imported_ids.append(imported_id)
        
        print(f"导入 20 个工作流定义耗时: {import_timer.elapsed:.3f}s")
        
        # 清理
        with PerformanceTimer() as cleanup_timer:
            for workflow_id in workflow_ids + imported_ids:
                await engine.delete_workflow(workflow_id)
        
        print(f"清理 40 个工作流耗时: {cleanup_timer.elapsed:.3f}s")
        
        # 性能断言
        assert create_timer.elapsed < 5.0, f"创建工作流过慢: {create_timer.elapsed:.3f}s"
        assert query_timer.elapsed < 2.0, f"查询工作流状态过慢: {query_timer.elapsed:.3f}s"
        assert export_timer.elapsed < 3.0, f"导出工作流定义过慢: {export_timer.elapsed:.3f}s"
        assert import_timer.elapsed < 3.0, f"导入工作流定义过慢: {import_timer.elapsed:.3f}s"
        assert cleanup_timer.elapsed < 2.0, f"清理工作流过慢: {cleanup_timer.elapsed:.3f}s"
    
    @pytest.mark.asyncio
    async def test_file_manager_performance(self, temp_dir):
        """测试文件管理器性能"""
        with patch('src.gemini_kling_mcp.file_manager.core.get_config') as mock_config:
            mock_config.return_value.file.temp_dir = temp_dir
            mock_config.return_value.file.max_file_size = 10 * 1024 * 1024  # 10MB
            mock_config.return_value.file.cleanup_interval = 3600
            mock_config.return_value.file.allowed_formats = ["txt", "json", "jpg", "mp4"]
            
            file_manager = TempFileManager(temp_dir, cleanup_interval=3600)
            
            try:
                print("\n测试文件管理器性能:")
                
                # 批量创建临时文件
                with PerformanceTimer() as create_timer:
                    temp_files = []
                    for i in range(100):
                        temp_file = file_manager.create_temp_file(
                            suffix='.txt',
                            content=f"测试内容{i+1}".encode()
                        )
                        temp_files.append(temp_file)
                
                print(f"创建 100 个临时文件耗时: {create_timer.elapsed:.3f}s")
                
                # 批量获取文件信息
                with PerformanceTimer() as info_timer:
                    info_list = file_manager.get_temp_files_info()
                    assert len(info_list) == 100
                
                print(f"获取 100 个文件信息耗时: {info_timer.elapsed:.3f}s")
                
                # 批量验证文件
                with PerformanceTimer() as validate_timer:
                    for temp_file in temp_files[:50]:  # 验证前50个
                        is_valid = file_manager.validate_file(temp_file)
                        assert is_valid
                
                print(f"验证 50 个文件耗时: {validate_timer.elapsed:.3f}s")
                
                # 批量清理文件
                with PerformanceTimer() as cleanup_timer:
                    cleaned_count = file_manager.cleanup_temp_files(force=True)
                    assert cleaned_count == 100
                
                print(f"清理 100 个文件耗时: {cleanup_timer.elapsed:.3f}s")
                
                # 性能断言
                assert create_timer.elapsed < 3.0, f"创建文件过慢: {create_timer.elapsed:.3f}s"
                assert info_timer.elapsed < 1.0, f"获取文件信息过慢: {info_timer.elapsed:.3f}s"
                assert validate_timer.elapsed < 1.0, f"验证文件过慢: {validate_timer.elapsed:.3f}s"
                assert cleanup_timer.elapsed < 2.0, f"清理文件过慢: {cleanup_timer.elapsed:.3f}s"
                
            finally:
                file_manager.stop_cleanup()


@pytest.mark.performance
class TestScalabilityPerformance:
    """可扩展性性能测试"""
    
    @pytest.mark.asyncio
    async def test_large_scale_batch_processing(
        self, 
        temp_dir
    ):
        """测试大规模批量处理性能"""
        mock_services = {
            'gemini': create_mock_gemini_service(enable_errors=False),
            'gemini_image': create_mock_gemini_image_service(enable_errors=False),  
            'kling': create_mock_kling_service(enable_errors=False)
        }
        
        with patch('src.gemini_kling_mcp.workflow.steps.GeminiTextService', return_value=mock_services['gemini']), \
             patch('src.gemini_kling_mcp.workflow.steps.GeminiImageService', return_value=mock_services['gemini_image']), \
             patch('src.gemini_kling_mcp.workflow.steps.KlingVideoService', return_value=mock_services['kling']), \
             patch('src.gemini_kling_mcp.workflow.state_manager.JSONFileBackend') as mock_backend:
            
            mock_backend.return_value.storage_dir = temp_dir
            mock_backend.return_value.save_state = AsyncMock()
            mock_backend.return_value.load_state = AsyncMock(return_value={})
            mock_backend.return_value.list_workflows = AsyncMock(return_value=[])
            mock_backend.return_value.delete_state = AsyncMock()
            
            # 测试不同规模的批量处理
            scales = [25, 50, 100]
            
            for scale in scales:
                print(f"\n测试大规模批量处理 - 规模: {scale}")
                
                story_themes = [f"大规模测试主题{i+1}" for i in range(scale)]
                
                with PerformanceTimer() as timer:
                    result = await generate_story_video_batch(
                        story_themes=story_themes,
                        concurrent_limit=5,  # 限制并发数以模拟资源约束
                        style="cartoon",
                        duration=5
                    )
                
                assert result["success"] is True
                
                successful = result["summary"]["successful"] 
                failed = result["summary"]["failed"]
                success_rate = successful / scale * 100
                throughput = successful / timer.elapsed if timer.elapsed > 0 else 0
                
                print(f"执行时间: {timer.elapsed:.3f}s")
                print(f"成功任务: {successful}")
                print(f"失败任务: {failed}")  
                print(f"成功率: {success_rate:.1f}%")
                print(f"吞吐量: {throughput:.2f} 任务/秒")
                
                # 可扩展性断言
                assert success_rate >= 80.0, f"大规模处理成功率过低: {success_rate:.1f}%"
                assert throughput > 0.5, f"大规模处理吞吐量过低: {throughput:.2f} 任务/秒"
                
                # 执行时间应该随规模线性增长（考虑并发限制）
                expected_max_time = scale / 2.0  # 假设每秒能处理2个任务
                assert timer.elapsed < expected_max_time, f"大规模处理时间超出预期: {timer.elapsed:.3f}s > {expected_max_time:.3f}s"
    
    @pytest.mark.asyncio
    async def test_system_stress_test(
        self, 
        temp_dir
    ):
        """系统压力测试"""
        mock_services = {
            'gemini': create_mock_gemini_service(enable_errors=False),
            'gemini_image': create_mock_gemini_image_service(enable_errors=False),
            'kling': create_mock_kling_service(enable_errors=False)
        }
        
        with patch('src.gemini_kling_mcp.tools.image_generation.GeminiImageService', return_value=mock_services['gemini_image']), \
             patch('src.gemini_kling_mcp.tools.kling_video.KlingVideoService', return_value=mock_services['kling']), \
             patch('src.gemini_kling_mcp.workflow.steps.GeminiTextService', return_value=mock_services['gemini']), \
             patch('src.gemini_kling_mcp.workflow.steps.GeminiImageService', return_value=mock_services['gemini_image']), \
             patch('src.gemini_kling_mcp.workflow.steps.KlingVideoService', return_value=mock_services['kling']), \
             patch('src.gemini_kling_mcp.workflow.state_manager.JSONFileBackend') as mock_backend:
            
            mock_backend.return_value.storage_dir = temp_dir
            mock_backend.return_value.save_state = AsyncMock()
            mock_backend.return_value.load_state = AsyncMock(return_value={})
            mock_backend.return_value.list_workflows = AsyncMock(return_value=[])
            mock_backend.return_value.delete_state = AsyncMock()
            
            print("\n系统压力测试 - 混合高负载:")
            
            # 创建高负载混合任务
            tasks = []
            
            # 大量图像生成任务
            for i in range(20):
                task = generate_image(
                    prompt=f"压力测试图像{i+1}",
                    num_images=1,
                    output_mode="base64"
                )
                tasks.append(("image", task))
            
            # 视频生成任务
            for i in range(10):
                task = generate_video(
                    prompt=f"压力测试视频{i+1}",
                    mode="standard",
                    duration=5,
                    wait_for_completion=False
                )
                tasks.append(("video", task))
            
            # 故事视频生成任务
            for i in range(5):
                task = generate_story_video(
                    story_theme=f"压力测试故事{i+1}",
                    style="cartoon", 
                    duration=5,
                    output_mode="base64"
                )
                tasks.append(("story", task))
            
            total_tasks = len(tasks)
            print(f"总任务数: {total_tasks} (图像: 20, 视频: 10, 故事: 5)")
            
            with PerformanceTimer() as timer:
                # 高并发执行
                task_results = await asyncio.gather(
                    *[task for _, task in tasks],
                    return_exceptions=True
                )
            
            # 统计结果
            success_count = 0
            error_count = 0
            task_stats = {"image": 0, "video": 0, "story": 0}
            
            for i, (task_type, result) in enumerate(zip([t[0] for t in tasks], task_results)):
                if isinstance(result, Exception):
                    error_count += 1
                    print(f"任务 {i+1} ({task_type}) 异常: {result}")
                elif result.get("success"):
                    success_count += 1
                    task_stats[task_type] += 1
                else:
                    error_count += 1
            
            success_rate = success_count / total_tasks * 100
            throughput = success_count / timer.elapsed if timer.elapsed > 0 else 0
            
            print(f"压力测试结果:")
            print(f"执行时间: {timer.elapsed:.3f}s")
            print(f"成功任务: {success_count}/{total_tasks}")
            print(f"失败任务: {error_count}")
            print(f"成功率: {success_rate:.1f}%") 
            print(f"图像成功: {task_stats['image']}/20")
            print(f"视频成功: {task_stats['video']}/10")
            print(f"故事成功: {task_stats['story']}/5")
            print(f"系统吞吐量: {throughput:.2f} 任务/秒")
            
            # 压力测试断言 - 要求相对宽松，关注系统稳定性
            assert success_rate >= 70.0, f"系统压力测试成功率过低: {success_rate:.1f}%"
            assert timer.elapsed < 60.0, f"系统压力测试执行时间过长: {timer.elapsed:.3f}s"
            assert throughput > 0.3, f"系统压力测试吞吐量过低: {throughput:.2f} 任务/秒"