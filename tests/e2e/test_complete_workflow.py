"""
完整工作流端到端测试

测试从MCP工具调用到最终输出的完整流程。
"""

import pytest
import asyncio
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, AsyncMock
from typing import Dict, Any

from src.gemini_kling_mcp.tools.workflow.story_video_generator import (
    generate_story_video, generate_story_video_batch
)
from src.gemini_kling_mcp.tools.image_generation import generate_image
from src.gemini_kling_mcp.tools.kling_video import generate_video
from src.gemini_kling_mcp.workflow.engine import WorkflowEngine
from src.gemini_kling_mcp.workflow.state_manager import WorkflowStateManager, JSONFileBackend
from src.gemini_kling_mcp.workflow.templates import template_library
from src.gemini_kling_mcp.services.gemini.text_service import GeminiTextService
from src.gemini_kling_mcp.services.gemini.image_service import GeminiImageService
from src.gemini_kling_mcp.services.kling.video_service import KlingVideoService
from src.gemini_kling_mcp.file_manager.core import TempFileManager
from src.gemini_kling_mcp.exceptions import ToolExecutionError
from tests.mocks import (
    create_mock_gemini_service,
    create_mock_gemini_image_service,
    create_mock_kling_service
)


@pytest.mark.e2e
class TestCompleteStoryVideoWorkflow:
    """完整故事视频生成工作流端到端测试"""
    
    @pytest.fixture
    def e2e_temp_dir(self):
        """端到端测试临时目录"""
        temp_dir = tempfile.mkdtemp(prefix="e2e_test_")
        yield temp_dir
        # 清理在测试后进行
    
    @pytest.fixture
    def mock_services_e2e(self):
        """端到端测试Mock服务"""
        return {
            'gemini': create_mock_gemini_service(enable_errors=False),
            'gemini_image': create_mock_gemini_image_service(enable_errors=False),
            'kling': create_mock_kling_service(enable_errors=False)
        }
    
    @pytest.fixture
    def real_file_manager(self, e2e_temp_dir):
        """真实文件管理器（用于端到端测试）"""
        with patch('src.gemini_kling_mcp.file_manager.core.get_config') as mock_config:
            mock_config.return_value.file.temp_dir = e2e_temp_dir
            mock_config.return_value.file.max_file_size = 50 * 1024 * 1024  # 50MB
            mock_config.return_value.file.cleanup_interval = 3600
            mock_config.return_value.file.allowed_formats = ["jpg", "png", "mp4", "txt", "json"]
            
            file_manager = TempFileManager(e2e_temp_dir)
            yield file_manager
            file_manager.stop_cleanup()
    
    @pytest.mark.asyncio
    async def test_single_story_video_generation_e2e(
        self, 
        e2e_temp_dir, 
        mock_services_e2e,
        real_file_manager
    ):
        """测试单个故事视频生成端到端流程"""
        story_theme = "勇敢的小兔子在魔法森林中寻找宝藏的冒险故事"
        
        with patch('src.gemini_kling_mcp.workflow.steps.GeminiTextService') as mock_text_svc, \
             patch('src.gemini_kling_mcp.workflow.steps.GeminiImageService') as mock_image_svc, \
             patch('src.gemini_kling_mcp.workflow.steps.KlingVideoService') as mock_video_svc, \
             patch('src.gemini_kling_mcp.workflow.state_manager.JSONFileBackend') as mock_backend:
            
            # 配置Mock服务
            mock_text_svc.return_value = mock_services_e2e['gemini']
            mock_image_svc.return_value = mock_services_e2e['gemini_image']
            mock_video_svc.return_value = mock_services_e2e['kling']
            
            # 配置状态后端
            mock_backend.return_value.storage_dir = e2e_temp_dir
            mock_backend.return_value.save_state = AsyncMock()
            mock_backend.return_value.load_state = AsyncMock(return_value={})
            mock_backend.return_value.list_workflows = AsyncMock(return_value=[])
            mock_backend.return_value.delete_state = AsyncMock()
            
            # 执行故事视频生成
            result = await generate_story_video(
                story_theme=story_theme,
                style="fantasy",
                duration=15,
                language="zh",
                output_mode="file"
            )
            
            # 验证结果结构
            assert result["success"] is True, f"生成失败: {result.get('error', '未知错误')}"
            assert "workflow_id" in result
            assert "story_script" in result
            assert "scene_images" in result
            assert "video_url" in result
            assert "file_paths" in result
            assert "metadata" in result
            
            # 验证元数据
            metadata = result["metadata"]
            assert metadata["theme"] == story_theme
            assert metadata["style"] == "fantasy"
            assert metadata["duration"] == 15
            assert metadata["language"] == "zh"
            assert "execution_time" in metadata
            assert "steps_completed" in metadata
            assert metadata["steps_completed"] > 0
            
            # 验证故事脚本结构
            story_script = result["story_script"]
            assert isinstance(story_script, dict)
            assert "title" in story_script
            assert "scenes" in story_script
            assert len(story_script["scenes"]) > 0
            
            # 验证场景图像
            scene_images = result["scene_images"]
            assert isinstance(scene_images, list)
            assert len(scene_images) > 0
            
            for image in scene_images:
                assert "scene_id" in image
                assert "description" in image
                assert "image_url" in image or "file_path" in image
            
            # 验证文件路径
            file_paths = result["file_paths"]
            assert isinstance(file_paths, dict)
            
            # 验证服务调用
            assert mock_services_e2e['gemini'].call_count > 0
            assert mock_services_e2e['gemini_image'].call_count > 0
            assert mock_services_e2e['kling'].call_count > 0
    
    @pytest.mark.asyncio
    async def test_batch_story_video_generation_e2e(
        self, 
        e2e_temp_dir, 
        mock_services_e2e
    ):
        """测试批量故事视频生成端到端流程"""
        story_themes = [
            "小猫咪的太空冒险",
            "海底世界的神秘宝藏",
            "山林中的友谊故事"
        ]
        
        with patch('src.gemini_kling_mcp.workflow.steps.GeminiTextService') as mock_text_svc, \
             patch('src.gemini_kling_mcp.workflow.steps.GeminiImageService') as mock_image_svc, \
             patch('src.gemini_kling_mcp.workflow.steps.KlingVideoService') as mock_video_svc, \
             patch('src.gemini_kling_mcp.workflow.state_manager.JSONFileBackend') as mock_backend:
            
            # 配置Mock服务
            mock_text_svc.return_value = mock_services_e2e['gemini']
            mock_image_svc.return_value = mock_services_e2e['gemini_image']
            mock_video_svc.return_value = mock_services_e2e['kling']
            
            # 配置状态后端
            mock_backend.return_value.storage_dir = e2e_temp_dir
            mock_backend.return_value.save_state = AsyncMock()
            mock_backend.return_value.load_state = AsyncMock(return_value={})
            mock_backend.return_value.list_workflows = AsyncMock(return_value=[])
            mock_backend.return_value.delete_state = AsyncMock()
            
            # 执行批量生成
            result = await generate_story_video_batch(
                story_themes=story_themes,
                style="cartoon",
                duration=10,
                concurrent_limit=2,
                output_mode="base64"
            )
            
            # 验证批量结果
            assert result["success"] is True
            assert "summary" in result
            assert "results" in result
            assert "successful_videos" in result
            
            # 验证摘要
            summary = result["summary"]
            assert summary["total"] == 3
            assert summary["successful"] >= 0
            assert summary["failed"] >= 0
            assert summary["total"] == summary["successful"] + summary["failed"]
            
            # 验证每个结果
            results = result["results"]
            assert len(results) == 3
            
            for i, res in enumerate(results):
                assert res["index"] == i
                assert res["theme"] == story_themes[i]
                assert "success" in res
                assert "execution_time" in res
                
                if res["success"]:
                    assert "workflow_id" in res
                    assert "story_script" in res
                    assert "scene_images" in res
                    assert "video_url" in res
                else:
                    assert "error" in res
    
    @pytest.mark.asyncio
    async def test_individual_tool_integration_e2e(
        self, 
        e2e_temp_dir,
        mock_services_e2e
    ):
        """测试单独工具集成端到端"""
        with patch('src.gemini_kling_mcp.tools.image_generation.GeminiImageService') as mock_image_svc, \
             patch('src.gemini_kling_mcp.tools.kling_video.KlingVideoService') as mock_video_svc:
            
            mock_image_svc.return_value = mock_services_e2e['gemini_image']
            mock_video_svc.return_value = mock_services_e2e['kling']
            
            # 测试图像生成工具
            image_result = await generate_image(
                prompt="一只可爱的小猫坐在彩虹上",
                num_images=2,
                aspect_ratio="1:1",
                output_mode="file"
            )
            
            assert image_result["success"] is True
            assert "images" in image_result
            assert len(image_result["images"]) == 2
            
            # 测试视频生成工具
            video_result = await generate_video(
                prompt="小猫在彩虹上跳舞",
                mode="standard",
                duration=5,
                aspect_ratio="16:9",
                wait_for_completion=False
            )
            
            assert video_result["success"] is True
            assert "task_id" in video_result
            assert "status" in video_result
    
    @pytest.mark.asyncio
    async def test_workflow_state_persistence_e2e(self, e2e_temp_dir):
        """测试工作流状态持久化端到端"""
        # 创建真实的状态管理器
        backend = JSONFileBackend(e2e_temp_dir)
        state_manager = WorkflowStateManager(backend)
        engine = WorkflowEngine(state_manager)
        
        # 获取故事视频生成模板
        template = template_library.get_template("story_video_generation")
        
        # 创建工作流
        workflow_id = await engine.create_workflow(
            config=template.config,
            steps_config=template.steps,
            initial_context={
                "story_theme": "测试持久化工作流",
                "style": "realistic"
            }
        )
        
        assert workflow_id is not None
        
        # 验证工作流状态
        status = await engine.get_workflow_status(workflow_id)
        assert status is not None
        assert status["workflow_id"] == workflow_id
        assert status["status"] == "created"
        assert status["context"]["story_theme"] == "测试持久化工作流"
        
        # 创建新的引擎实例（模拟重启）
        new_engine = WorkflowEngine(WorkflowStateManager(backend))
        
        # 验证可以加载之前的工作流
        loaded_status = await new_engine.get_workflow_status(workflow_id)
        assert loaded_status is not None
        assert loaded_status["workflow_id"] == workflow_id
        assert loaded_status["context"]["story_theme"] == "测试持久化工作流"
        
        # 导出工作流定义
        definition = await new_engine.export_workflow_definition(workflow_id)
        assert definition is not None
        assert "config" in definition
        assert "steps" in definition
        assert "initial_context" in definition
        
        # 导入工作流定义（创建新的工作流）
        imported_id = await new_engine.import_workflow_definition(definition)
        assert imported_id != workflow_id
        
        # 验证导入的工作流
        imported_status = await new_engine.get_workflow_status(imported_id)
        assert imported_status["status"] == "imported"
        assert imported_status["context"]["story_theme"] == "测试持久化工作流"


@pytest.mark.e2e
class TestErrorRecoveryE2E:
    """错误恢复端到端测试"""
    
    @pytest.mark.asyncio
    async def test_partial_failure_recovery(self, temp_dir):
        """测试部分失败时的错误恢复"""
        # Mock一个部分失败的Gemini服务
        mock_gemini = create_mock_gemini_service(enable_errors=True)
        mock_gemini_image = create_mock_gemini_image_service(enable_errors=False)
        mock_kling = create_mock_kling_service(enable_errors=False)
        
        with patch('src.gemini_kling_mcp.workflow.steps.GeminiTextService', return_value=mock_gemini), \
             patch('src.gemini_kling_mcp.workflow.steps.GeminiImageService', return_value=mock_gemini_image), \
             patch('src.gemini_kling_mcp.workflow.steps.KlingVideoService', return_value=mock_kling), \
             patch('src.gemini_kling_mcp.workflow.state_manager.JSONFileBackend') as mock_backend:
            
            mock_backend.return_value.storage_dir = temp_dir
            mock_backend.return_value.save_state = AsyncMock()
            mock_backend.return_value.load_state = AsyncMock(return_value={})
            mock_backend.return_value.list_workflows = AsyncMock(return_value=[])
            mock_backend.return_value.delete_state = AsyncMock()
            
            # 尝试生成故事视频（应该失败）
            with pytest.raises(ToolExecutionError, match="故事视频生成失败"):
                await generate_story_video(
                    story_theme="错误恢复测试",
                    style="realistic",
                    duration=5
                )
    
    @pytest.mark.asyncio
    async def test_timeout_handling_e2e(self, temp_dir):
        """测试超时处理端到端"""
        # 创建会超时的服务
        slow_gemini = AsyncMock()
        slow_gemini.generate_text.side_effect = lambda *args: asyncio.sleep(10)
        
        with patch('src.gemini_kling_mcp.workflow.steps.GeminiTextService', return_value=slow_gemini), \
             patch('src.gemini_kling_mcp.workflow.state_manager.JSONFileBackend') as mock_backend:
            
            mock_backend.return_value.storage_dir = temp_dir
            mock_backend.return_value.save_state = AsyncMock()
            mock_backend.return_value.load_state = AsyncMock(return_value={})
            mock_backend.return_value.list_workflows = AsyncMock(return_value=[])
            mock_backend.return_value.delete_state = AsyncMock()
            
            # 测试超时处理
            with pytest.raises(ToolExecutionError):
                await asyncio.wait_for(
                    generate_story_video(
                        story_theme="超时测试",
                        style="realistic"
                    ),
                    timeout=3  # 3秒超时
                )
    
    @pytest.mark.asyncio
    async def test_batch_partial_failure_e2e(self, temp_dir):
        """测试批量处理部分失败端到端"""
        # 创建有时失败的服务
        inconsistent_gemini = create_mock_gemini_service(enable_errors=True)
        mock_gemini_image = create_mock_gemini_image_service(enable_errors=False)
        mock_kling = create_mock_kling_service(enable_errors=False)
        
        with patch('src.gemini_kling_mcp.workflow.steps.GeminiTextService', return_value=inconsistent_gemini), \
             patch('src.gemini_kling_mcp.workflow.steps.GeminiImageService', return_value=mock_gemini_image), \
             patch('src.gemini_kling_mcp.workflow.steps.KlingVideoService', return_value=mock_kling), \
             patch('src.gemini_kling_mcp.workflow.state_manager.JSONFileBackend') as mock_backend:
            
            mock_backend.return_value.storage_dir = temp_dir
            mock_backend.return_value.save_state = AsyncMock()
            mock_backend.return_value.load_state = AsyncMock(return_value={})
            mock_backend.return_value.list_workflows = AsyncMock(return_value=[])
            mock_backend.return_value.delete_state = AsyncMock()
            
            # 批量处理（某些会失败）
            result = await generate_story_video_batch(
                story_themes=[
                    "成功主题1",
                    "失败主题",
                    "成功主题2",
                    "另一个失败主题",
                    "最终成功主题"
                ],
                concurrent_limit=2
            )
            
            # 即使有部分失败，整体操作仍应成功
            assert result["success"] is True
            assert result["summary"]["total"] == 5
            
            # 应该有成功和失败的记录
            successful = result["summary"]["successful"]
            failed = result["summary"]["failed"]
            
            assert successful + failed == 5
            assert successful >= 0
            assert failed >= 0


@pytest.mark.e2e
class TestPerformanceE2E:
    """性能相关端到端测试"""
    
    @pytest.mark.asyncio
    async def test_concurrent_requests_e2e(self, temp_dir):
        """测试并发请求处理端到端"""
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
            
            # 创建多个并发任务
            tasks = []
            for i in range(3):
                task = generate_story_video(
                    story_theme=f"并发测试主题{i+1}",
                    style="cartoon",
                    duration=5,
                    output_mode="base64"
                )
                tasks.append(task)
            
            # 并发执行
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 验证所有任务都成功完成
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    pytest.fail(f"任务 {i+1} 失败: {result}")
                
                assert result["success"] is True, f"任务 {i+1} 未成功: {result}"
                assert f"并发测试主题{i+1}" in result["metadata"]["theme"]
    
    @pytest.mark.asyncio
    async def test_large_batch_processing_e2e(self, temp_dir):
        """测试大批量处理端到端"""
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
            
            # 创建大批量主题
            story_themes = [f"批量主题{i+1}" for i in range(8)]
            
            # 执行大批量处理
            result = await generate_story_video_batch(
                story_themes=story_themes,
                concurrent_limit=3,
                style="realistic",
                duration=5
            )
            
            assert result["success"] is True
            assert result["summary"]["total"] == 8
            assert len(result["results"]) == 8
            
            # 验证所有主题都被处理
            processed_themes = {res["theme"] for res in result["results"]}
            expected_themes = set(story_themes)
            assert processed_themes == expected_themes


@pytest.mark.e2e
class TestFileHandlingE2E:
    """文件处理端到端测试"""
    
    @pytest.mark.asyncio
    async def test_file_output_modes_e2e(self, temp_dir):
        """测试不同文件输出模式端到端"""
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
            
            # 测试文件输出模式
            file_result = await generate_story_video(
                story_theme="文件输出测试",
                output_mode="file",
                style="cartoon",
                duration=5
            )
            
            assert file_result["success"] is True
            assert "file_paths" in file_result
            file_paths = file_result["file_paths"]
            assert isinstance(file_paths, dict)
            assert len(file_paths) > 0
            
            # 测试base64输出模式
            base64_result = await generate_story_video(
                story_theme="Base64输出测试",
                output_mode="base64",
                style="cartoon",
                duration=5
            )
            
            assert base64_result["success"] is True
            # 验证base64格式的数据
            scene_images = base64_result["scene_images"]
            for image in scene_images:
                if "base64_data" in image:
                    assert len(image["base64_data"]) > 0
                    assert image["base64_data"].startswith("data:")
    
    @pytest.mark.asyncio
    async def test_file_cleanup_e2e(self, temp_dir):
        """测试文件清理端到端"""
        from src.gemini_kling_mcp.file_manager.core import TempFileManager
        
        with patch('src.gemini_kling_mcp.file_manager.core.get_config') as mock_config:
            mock_config.return_value.file.temp_dir = temp_dir
            mock_config.return_value.file.max_file_size = 50 * 1024 * 1024
            mock_config.return_value.file.cleanup_interval = 1  # 1秒清理间隔
            mock_config.return_value.file.allowed_formats = ["jpg", "png", "mp4", "txt", "json"]
            
            file_manager = TempFileManager(temp_dir, cleanup_interval=1)
            
            try:
                # 创建临时文件
                temp_file1 = file_manager.create_temp_file(suffix='.txt', content=b"test1")
                temp_file2 = file_manager.create_temp_file(suffix='.jpg', content=b"test2")
                
                assert temp_file1.exists()
                assert temp_file2.exists()
                assert len(file_manager._temp_files) == 2
                
                # 手动清理旧文件
                cleaned_count = file_manager.cleanup_temp_files(max_age=0)
                
                assert cleaned_count == 2
                assert not temp_file1.exists()
                assert not temp_file2.exists()
                assert len(file_manager._temp_files) == 0
                
            finally:
                file_manager.stop_cleanup()