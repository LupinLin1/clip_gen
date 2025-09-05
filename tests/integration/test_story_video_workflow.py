"""
故事视频生成工作流集成测试

测试完整的故事视频生成流程，包括文本、图像和视频生成的协调工作。
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from typing import Dict, Any

from src.gemini_kling_mcp.tools.workflow.story_video_generator import (
    generate_story_video, generate_story_video_batch
)
from src.gemini_kling_mcp.workflow import WorkflowEngine, template_library
from src.gemini_kling_mcp.exceptions import ToolExecutionError
from tests.test_data_generator import test_data_generator


@pytest.mark.integration
class TestStoryVideoWorkflow:
    """故事视频生成工作流集成测试"""
    
    @pytest.mark.asyncio
    async def test_generate_story_video_success(
        self, 
        temp_dir,
        mock_gemini_service, 
        mock_gemini_image_service,
        mock_kling_service
    ):
        """测试成功生成故事视频"""
        story_theme = "勇敢的小猫在森林中的冒险"
        
        with patch('src.gemini_kling_mcp.workflow.steps.GeminiTextService', return_value=mock_gemini_service), \
             patch('src.gemini_kling_mcp.workflow.steps.GeminiImageService', return_value=mock_gemini_image_service), \
             patch('src.gemini_kling_mcp.workflow.steps.KlingVideoService', return_value=mock_kling_service), \
             patch('src.gemini_kling_mcp.workflow.state_manager.JSONFileBackend') as mock_backend:
            
            # 配置Mock状态后端
            mock_backend.return_value.storage_dir = temp_dir
            
            result = await generate_story_video(
                story_theme=story_theme,
                style="cartoon",
                duration=10,
                output_mode="file"
            )
            
            # 验证结果结构
            assert result["success"] is True
            assert "workflow_id" in result
            assert "story_script" in result
            assert "scene_images" in result
            assert "video_url" in result
            assert "file_paths" in result
            assert "metadata" in result
            
            # 验证元数据
            metadata = result["metadata"]
            assert metadata["theme"] == story_theme
            assert metadata["style"] == "cartoon"
            assert metadata["duration"] == 10
            assert "execution_time" in metadata
            assert "steps_completed" in metadata
            
            # 验证服务调用次数
            assert mock_gemini_service.call_count > 0
            assert mock_gemini_image_service.call_count > 0
            assert mock_kling_service.call_count > 0
    
    @pytest.mark.asyncio
    async def test_generate_story_video_custom_style(
        self, 
        temp_dir,
        mock_gemini_service,
        mock_gemini_image_service, 
        mock_kling_service
    ):
        """测试自定义风格的故事视频生成"""
        story_theme = "未来城市中的机器人朋友"
        
        with patch('src.gemini_kling_mcp.workflow.steps.GeminiTextService', return_value=mock_gemini_service), \
             patch('src.gemini_kling_mcp.workflow.steps.GeminiImageService', return_value=mock_gemini_image_service), \
             patch('src.gemini_kling_mcp.workflow.steps.KlingVideoService', return_value=mock_kling_service), \
             patch('src.gemini_kling_mcp.workflow.state_manager.JSONFileBackend') as mock_backend:
            
            mock_backend.return_value.storage_dir = temp_dir
            
            result = await generate_story_video(
                story_theme=story_theme,
                style="sci-fi",
                duration=15,
                language="zh",
                output_mode="base64"
            )
            
            assert result["success"] is True
            assert result["metadata"]["style"] == "sci-fi"
            assert result["metadata"]["duration"] == 15
            assert result["metadata"]["language"] == "zh"
    
    @pytest.mark.asyncio
    async def test_generate_story_video_workflow_error(
        self, 
        temp_dir,
        mock_gemini_service_with_errors
    ):
        """测试工作流执行错误处理"""
        story_theme = "测试错误处理"
        
        with patch('src.gemini_kling_mcp.workflow.steps.GeminiTextService', return_value=mock_gemini_service_with_errors), \
             patch('src.gemini_kling_mcp.workflow.state_manager.JSONFileBackend') as mock_backend:
            
            mock_backend.return_value.storage_dir = temp_dir
            
            with pytest.raises(ToolExecutionError, match="故事视频生成失败"):
                await generate_story_video(
                    story_theme=story_theme,
                    style="realistic",
                    duration=5
                )
    
    @pytest.mark.asyncio
    async def test_generate_story_video_timeout(self, temp_dir):
        """测试工作流超时处理"""
        story_theme = "超时测试"
        
        # Mock一个会超时的服务
        slow_service = AsyncMock()
        slow_service.generate_text.side_effect = lambda *args: asyncio.sleep(10)
        
        with patch('src.gemini_kling_mcp.workflow.steps.GeminiTextService', return_value=slow_service), \
             patch('src.gemini_kling_mcp.workflow.state_manager.JSONFileBackend') as mock_backend:
            
            mock_backend.return_value.storage_dir = temp_dir
            
            with pytest.raises(ToolExecutionError, match="故事视频生成超时"):
                await asyncio.wait_for(
                    generate_story_video(
                        story_theme=story_theme,
                        style="realistic"
                    ),
                    timeout=5  # 5秒超时
                )


@pytest.mark.integration
class TestStoryVideoBatchGeneration:
    """批量故事视频生成集成测试"""
    
    @pytest.mark.asyncio
    async def test_generate_story_video_batch_success(
        self,
        temp_dir,
        mock_gemini_service,
        mock_gemini_image_service,
        mock_kling_service
    ):
        """测试批量生成故事视频成功"""
        story_themes = [
            "小兔子的森林冒险",
            "太空探险记",
            "海底世界奇遇"
        ]
        
        with patch('src.gemini_kling_mcp.workflow.steps.GeminiTextService', return_value=mock_gemini_service), \
             patch('src.gemini_kling_mcp.workflow.steps.GeminiImageService', return_value=mock_gemini_image_service), \
             patch('src.gemini_kling_mcp.workflow.steps.KlingVideoService', return_value=mock_kling_service), \
             patch('src.gemini_kling_mcp.workflow.state_manager.JSONFileBackend') as mock_backend:
            
            mock_backend.return_value.storage_dir = temp_dir
            
            result = await generate_story_video_batch(
                story_themes=story_themes,
                style="cartoon",
                duration=8,
                concurrent_limit=2
            )
            
            # 验证批量结果
            assert result["success"] is True
            assert "summary" in result
            assert "results" in result
            assert "successful_videos" in result
            
            summary = result["summary"]
            assert summary["total"] == 3
            assert summary["successful"] >= 0
            assert summary["failed"] >= 0
            assert summary["total"] == summary["successful"] + summary["failed"]
            
            # 验证每个结果
            assert len(result["results"]) == 3
            for i, res in enumerate(result["results"]):
                assert res["index"] == i
                assert res["theme"] == story_themes[i]
                assert "success" in res
    
    @pytest.mark.asyncio
    async def test_generate_story_video_batch_partial_failure(
        self,
        temp_dir,
        mock_gemini_service_with_errors
    ):
        """测试批量生成部分失败"""
        story_themes = [
            "主题1", "主题2", "主题3", "主题4", "主题5"
        ]
        
        with patch('src.gemini_kling_mcp.workflow.steps.GeminiTextService', return_value=mock_gemini_service_with_errors), \
             patch('src.gemini_kling_mcp.workflow.state_manager.JSONFileBackend') as mock_backend:
            
            mock_backend.return_value.storage_dir = temp_dir
            
            result = await generate_story_video_batch(
                story_themes=story_themes,
                concurrent_limit=3
            )
            
            # 即使有部分失败，整体操作仍应成功
            assert result["success"] is True
            assert result["summary"]["total"] == 5
            
            # 应该有成功和失败的记录
            assert len(result["results"]) == 5
            successful_count = len([r for r in result["results"] if r["success"]])
            failed_count = len([r for r in result["results"] if not r["success"]])
            
            assert successful_count + failed_count == 5
            assert result["summary"]["successful"] == successful_count
            assert result["summary"]["failed"] == failed_count
    
    @pytest.mark.asyncio
    async def test_generate_story_video_batch_concurrency_limit(
        self,
        temp_dir,
        mock_gemini_service
    ):
        """测试批量生成的并发限制"""
        story_themes = ["主题1", "主题2", "主题3", "主题4"]
        
        # 记录并发执行情况
        execution_times = []
        original_generate = mock_gemini_service.generate_text
        
        async def tracking_generate(*args, **kwargs):
            import time
            start_time = time.time()
            result = await original_generate(*args, **kwargs)
            execution_times.append(time.time() - start_time)
            return result
        
        mock_gemini_service.generate_text = tracking_generate
        
        with patch('src.gemini_kling_mcp.workflow.steps.GeminiTextService', return_value=mock_gemini_service), \
             patch('src.gemini_kling_mcp.workflow.state_manager.JSONFileBackend') as mock_backend:
            
            mock_backend.return_value.storage_dir = temp_dir
            
            result = await generate_story_video_batch(
                story_themes=story_themes,
                concurrent_limit=2  # 限制并发数为2
            )
            
            assert result["success"] is True
            assert len(result["results"]) == 4


@pytest.mark.integration
class TestWorkflowTemplate:
    """工作流模板集成测试"""
    
    def test_story_video_template_structure(self):
        """测试故事视频模板结构"""
        template = template_library.get_template("story_video_generation")
        
        assert template is not None
        assert template.name == "故事视频生成"
        assert len(template.steps) > 0
        assert "story_theme" in template.example_inputs
        
        # 验证步骤结构
        step_ids = [step["id"] for step in template.steps]
        assert "generate_script" in step_ids
        assert "extract_scenes" in step_ids
        assert "generate_scene_images" in step_ids
        assert "create_story_video" in step_ids
        
        # 验证依赖关系
        for step in template.steps:
            for dep in step.get("dependencies", []):
                assert dep in step_ids, f"依赖 {dep} 在步骤列表中不存在"
    
    @pytest.mark.asyncio
    async def test_create_workflow_from_template(self, workflow_engine):
        """测试从模板创建工作流"""
        template_id = "story_video_generation"
        custom_name = "我的故事视频工作流"
        initial_context = {
            "story_theme": "测试主题",
            "style": "cartoon"
        }
        
        # 使用工作流引擎从模板创建工作流
        template = template_library.get_template(template_id)
        
        workflow_id = await workflow_engine.create_workflow(
            config=template.config,
            steps_config=template.steps,
            initial_context=initial_context
        )
        
        assert workflow_id is not None
        
        # 验证创建的工作流
        status = await workflow_engine.get_workflow_status(workflow_id)
        assert status is not None
        assert status["name"] == template.config.name
        assert status["status"] == "created"


@pytest.mark.integration 
class TestWorkflowStateManagement:
    """工作流状态管理集成测试"""
    
    @pytest.mark.asyncio
    async def test_workflow_state_persistence(
        self,
        temp_dir,
        mock_gemini_service
    ):
        """测试工作流状态持久化"""
        from src.gemini_kling_mcp.workflow.state_manager import JSONFileBackend, WorkflowStateManager
        
        backend = JSONFileBackend(temp_dir)
        state_manager = WorkflowStateManager(backend)
        engine = WorkflowEngine(state_manager)
        
        # 创建工作流
        config = template_library.get_template("story_video_generation").config
        steps = template_library.get_template("story_video_generation").steps
        
        workflow_id = await engine.create_workflow(
            config=config,
            steps_config=steps[:2],  # 只取前两个步骤以加快测试
            initial_context={"story_theme": "测试持久化"}
        )
        
        # 验证状态已保存
        saved_status = await engine.get_workflow_status(workflow_id)
        assert saved_status is not None
        assert saved_status["workflow_id"] == workflow_id
        
        # 创建新的引擎实例，验证可以加载状态
        new_engine = WorkflowEngine(WorkflowStateManager(backend))
        loaded_status = await new_engine.get_workflow_status(workflow_id)
        
        assert loaded_status is not None
        assert loaded_status["workflow_id"] == workflow_id
        assert loaded_status["name"] == saved_status["name"]
    
    @pytest.mark.asyncio
    async def test_workflow_export_import(self, workflow_engine):
        """测试工作流导出导入"""
        # 创建原始工作流
        template = template_library.get_template("story_video_generation")
        
        original_id = await workflow_engine.create_workflow(
            config=template.config,
            steps_config=template.steps,
            initial_context={"story_theme": "导出导入测试"}
        )
        
        # 导出工作流定义
        definition = await workflow_engine.export_workflow_definition(original_id)
        assert definition is not None
        
        # 导入工作流定义
        imported_id = await workflow_engine.import_workflow_definition(definition)
        assert imported_id != original_id
        
        # 验证导入的工作流
        imported_status = await workflow_engine.get_workflow_status(imported_id)
        original_status = await workflow_engine.get_workflow_status(original_id)
        
        assert imported_status["name"] == original_status["name"]
        assert imported_status["status"] == "imported"