"""
工作流引擎单元测试

测试工作流引擎的核心功能，包括创建、执行、状态管理等。
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from src.gemini_kling_mcp.workflow import (
    WorkflowEngine, WorkflowConfig, WorkflowStatus,
    WorkflowDAG, DAGNode, NodeStatus
)
from src.gemini_kling_mcp.exceptions import WorkflowError
from tests.test_data_generator import test_data_generator


@pytest.mark.unit
class TestWorkflowEngine:
    """工作流引擎测试类"""
    
    @pytest.mark.asyncio
    async def test_create_workflow(self, workflow_engine):
        """测试创建工作流"""
        config = WorkflowConfig(name="测试工作流", description="测试描述")
        steps_config = test_data_generator.generate_workflow_steps(3)
        
        workflow_id = await workflow_engine.create_workflow(
            config=config,
            steps_config=steps_config
        )
        
        assert workflow_id is not None
        assert isinstance(workflow_id, str)
        assert len(workflow_id) > 0
        
        # 验证工作流状态
        status = await workflow_engine.get_workflow_status(workflow_id)
        assert status is not None
        assert status["status"] == "created"
        assert status["name"] == config.name
    
    @pytest.mark.asyncio
    async def test_create_workflow_invalid_steps(self, workflow_engine):
        """测试创建工作流时步骤配置无效"""
        config = WorkflowConfig(name="测试工作流")
        
        # 缺少必需字段的步骤
        invalid_steps = [
            {"name": "步骤1"},  # 缺少id和type
            {"id": "step2"}     # 缺少type
        ]
        
        with pytest.raises(WorkflowError):
            await workflow_engine.create_workflow(
                config=config,
                steps_config=invalid_steps
            )
    
    @pytest.mark.asyncio
    async def test_create_workflow_circular_dependency(self, workflow_engine):
        """测试创建具有循环依赖的工作流"""
        config = WorkflowConfig(name="循环依赖工作流")
        
        # 创建循环依赖的步骤
        circular_steps = [
            {"id": "step1", "type": "text_generation", "dependencies": ["step2"]},
            {"id": "step2", "type": "text_generation", "dependencies": ["step1"]}
        ]
        
        with pytest.raises(WorkflowError):
            await workflow_engine.create_workflow(
                config=config,
                steps_config=circular_steps
            )
    
    @pytest.mark.asyncio
    async def test_list_workflows(self, workflow_engine):
        """测试列出工作流"""
        # 创建几个工作流
        config1 = WorkflowConfig(name="工作流1")
        config2 = WorkflowConfig(name="工作流2")
        steps = test_data_generator.generate_workflow_steps(2)
        
        workflow_id1 = await workflow_engine.create_workflow(config1, steps)
        workflow_id2 = await workflow_engine.create_workflow(config2, steps)
        
        # 列出所有工作流
        workflows = await workflow_engine.list_workflows()
        
        assert len(workflows) >= 2
        workflow_ids = [w["workflow_id"] for w in workflows]
        assert workflow_id1 in workflow_ids
        assert workflow_id2 in workflow_ids
    
    @pytest.mark.asyncio
    async def test_get_workflow_status_nonexistent(self, workflow_engine):
        """测试获取不存在工作流的状态"""
        status = await workflow_engine.get_workflow_status("nonexistent-id")
        assert status is None
    
    @pytest.mark.asyncio
    async def test_start_workflow_nonexistent(self, workflow_engine):
        """测试启动不存在的工作流"""
        with pytest.raises(WorkflowError, match="工作流 nonexistent-id 不存在"):
            await workflow_engine.start_workflow("nonexistent-id")
    
    @pytest.mark.asyncio 
    async def test_workflow_execution_simple(self, workflow_engine, mock_gemini_service):
        """测试简单工作流执行"""
        with patch('src.gemini_kling_mcp.workflow.steps.GeminiTextService', return_value=mock_gemini_service):
            config = WorkflowConfig(name="简单工作流", max_concurrent_steps=1)
            steps_config = [
                {
                    "id": "step1",
                    "name": "文本生成",
                    "type": "text_generation",
                    "config": {
                        "prompt": "生成测试文本",
                        "model": "gemini-1.5-flash-002",
                        "max_tokens": 100
                    }
                }
            ]
            
            workflow_id = await workflow_engine.create_workflow(config, steps_config)
            await workflow_engine.start_workflow(workflow_id)
            
            # 等待完成
            success = await workflow_engine.wait_for_completion(workflow_id, timeout=10)
            assert success is True
            
            # 检查最终状态
            status = await workflow_engine.get_workflow_status(workflow_id)
            assert status["status"] == "completed"
    
    @pytest.mark.asyncio
    async def test_workflow_execution_with_dependencies(self, workflow_engine, mock_gemini_service):
        """测试带依赖关系的工作流执行"""
        with patch('src.gemini_kling_mcp.workflow.steps.GeminiTextService', return_value=mock_gemini_service):
            config = WorkflowConfig(name="依赖工作流")
            steps_config = [
                {
                    "id": "step1",
                    "name": "第一步",
                    "type": "text_generation",
                    "config": {"prompt": "步骤1", "model": "gemini-1.5-flash-002"},
                    "dependencies": []
                },
                {
                    "id": "step2", 
                    "name": "第二步",
                    "type": "text_generation",
                    "config": {"prompt": "步骤2", "model": "gemini-1.5-flash-002"},
                    "dependencies": ["step1"]
                }
            ]
            
            workflow_id = await workflow_engine.create_workflow(config, steps_config)
            await workflow_engine.start_workflow(workflow_id)
            
            success = await workflow_engine.wait_for_completion(workflow_id, timeout=15)
            assert success is True
            
            # 验证执行顺序正确
            logs = await workflow_engine.get_workflow_logs(workflow_id)
            step1_log = next(log for log in logs if log["step_id"] == "step1")
            step2_log = next(log for log in logs if log["step_id"] == "step2")
            
            assert step1_log["status"] == "completed"
            assert step2_log["status"] == "completed"
            assert step1_log["end_time"] <= step2_log["start_time"]  # step1先完成
    
    @pytest.mark.asyncio
    async def test_workflow_cancellation(self, workflow_engine):
        """测试取消工作流"""
        config = WorkflowConfig(name="可取消工作流")
        steps_config = test_data_generator.generate_workflow_steps(3)
        
        workflow_id = await workflow_engine.create_workflow(config, steps_config)
        await workflow_engine.start_workflow(workflow_id)
        
        # 立即取消
        await workflow_engine.cancel_workflow(workflow_id)
        
        status = await workflow_engine.get_workflow_status(workflow_id)
        assert status["status"] == "cancelled"
    
    @pytest.mark.asyncio
    async def test_workflow_pause_resume(self, workflow_engine):
        """测试暂停和恢复工作流"""
        config = WorkflowConfig(name="可暂停工作流")
        steps_config = test_data_generator.generate_workflow_steps(2)
        
        workflow_id = await workflow_engine.create_workflow(config, steps_config)
        await workflow_engine.start_workflow(workflow_id)
        
        # 暂停工作流
        await workflow_engine.pause_workflow(workflow_id)
        status = await workflow_engine.get_workflow_status(workflow_id)
        assert status["status"] == "paused"
        
        # 恢复工作流
        await workflow_engine.resume_workflow(workflow_id)
        # 注意：恢复后状态可能是running或其他，取决于实际执行情况
    
    @pytest.mark.asyncio
    async def test_workflow_with_errors(self, workflow_engine, mock_gemini_service_with_errors):
        """测试工作流执行中的错误处理"""
        with patch('src.gemini_kling_mcp.workflow.steps.GeminiTextService', return_value=mock_gemini_service_with_errors):
            config = WorkflowConfig(name="错误工作流", retry_failed_steps=False)
            steps_config = [
                {
                    "id": "error_step",
                    "name": "容易出错的步骤", 
                    "type": "text_generation",
                    "config": {"prompt": "测试错误", "model": "gemini-1.5-flash-002"}
                }
            ]
            
            workflow_id = await workflow_engine.create_workflow(config, steps_config)
            await workflow_engine.start_workflow(workflow_id)
            
            success = await workflow_engine.wait_for_completion(workflow_id, timeout=10)
            
            # 可能成功也可能失败，取决于Mock服务的随机性
            status = await workflow_engine.get_workflow_status(workflow_id)
            assert status["status"] in ["completed", "failed"]
    
    @pytest.mark.asyncio
    async def test_workflow_timeout(self, workflow_engine):
        """测试工作流超时"""
        config = WorkflowConfig(name="超时工作流", timeout_seconds=1)
        
        # 创建会耗时很长的步骤
        steps_config = [
            {
                "id": "slow_step",
                "name": "慢步骤",
                "type": "custom",
                "config": {"delay": 5}  # 5秒延迟，但工作流超时1秒
            }
        ]
        
        workflow_id = await workflow_engine.create_workflow(config, steps_config)
        
        # 由于配置了超时，应该不会等太久
        with pytest.raises(WorkflowError):
            await workflow_engine.start_workflow(workflow_id)
            await workflow_engine.wait_for_completion(workflow_id, timeout=2)


@pytest.mark.unit
class TestWorkflowConfig:
    """工作流配置测试类"""
    
    def test_workflow_config_defaults(self):
        """测试工作流配置默认值"""
        config = WorkflowConfig(name="测试配置")
        
        assert config.name == "测试配置"
        assert config.description == ""
        assert config.max_concurrent_steps == 3
        assert config.retry_failed_steps is True
        assert config.timeout_seconds is None
        assert config.cleanup_on_completion is False
        assert config.save_intermediate_results is True
    
    def test_workflow_config_to_dict(self):
        """测试工作流配置序列化"""
        config = WorkflowConfig(
            name="测试配置",
            description="测试描述",
            max_concurrent_steps=5,
            timeout_seconds=3600
        )
        
        config_dict = config.to_dict()
        
        assert config_dict["name"] == "测试配置"
        assert config_dict["description"] == "测试描述"
        assert config_dict["max_concurrent_steps"] == 5
        assert config_dict["timeout_seconds"] == 3600
    
    def test_workflow_config_from_dict(self):
        """测试工作流配置反序列化"""
        config_dict = {
            "name": "从字典创建",
            "description": "测试描述",
            "max_concurrent_steps": 2,
            "retry_failed_steps": False,
            "timeout_seconds": 1800,
            "cleanup_on_completion": True,
            "save_intermediate_results": False
        }
        
        config = WorkflowConfig.from_dict(config_dict)
        
        assert config.name == "从字典创建"
        assert config.description == "测试描述"
        assert config.max_concurrent_steps == 2
        assert config.retry_failed_steps is False
        assert config.timeout_seconds == 1800
        assert config.cleanup_on_completion is True
        assert config.save_intermediate_results is False


@pytest.mark.unit 
class TestWorkflowCallbacks:
    """工作流回调测试类"""
    
    @pytest.mark.asyncio
    async def test_workflow_callbacks(self, workflow_engine, mock_gemini_service):
        """测试工作流回调功能"""
        callback_events = []
        
        def callback(workflow_id, event, data):
            callback_events.append({
                "workflow_id": workflow_id,
                "event": event,
                "data": data
            })
        
        with patch('src.gemini_kling_mcp.workflow.steps.GeminiTextService', return_value=mock_gemini_service):
            config = WorkflowConfig(name="回调测试工作流")
            steps_config = [
                {
                    "id": "callback_step",
                    "name": "回调测试步骤",
                    "type": "text_generation",
                    "config": {"prompt": "测试", "model": "gemini-1.5-flash-002"}
                }
            ]
            
            workflow_id = await workflow_engine.create_workflow(config, steps_config)
            
            # 添加回调
            workflow_engine.add_callback(workflow_id, callback)
            
            # 执行工作流
            await workflow_engine.start_workflow(workflow_id)
            await workflow_engine.wait_for_completion(workflow_id, timeout=10)
            
            # 验证回调被调用
            assert len(callback_events) > 0
            
            # 验证有完成事件
            completion_events = [e for e in callback_events if e["event"] == "workflow_completed"]
            assert len(completion_events) > 0
            
            completion_event = completion_events[0]
            assert completion_event["workflow_id"] == workflow_id
            assert "status" in completion_event["data"]


@pytest.mark.unit
class TestWorkflowLogs:
    """工作流日志测试类"""
    
    @pytest.mark.asyncio
    async def test_get_workflow_logs(self, workflow_engine, mock_gemini_service):
        """测试获取工作流日志"""
        with patch('src.gemini_kling_mcp.workflow.steps.GeminiTextService', return_value=mock_gemini_service):
            config = WorkflowConfig(name="日志测试工作流")
            steps_config = [
                {
                    "id": "log_step1",
                    "name": "日志步骤1",
                    "type": "text_generation",
                    "config": {"prompt": "测试1", "model": "gemini-1.5-flash-002"}
                },
                {
                    "id": "log_step2",
                    "name": "日志步骤2", 
                    "type": "text_generation",
                    "config": {"prompt": "测试2", "model": "gemini-1.5-flash-002"},
                    "dependencies": ["log_step1"]
                }
            ]
            
            workflow_id = await workflow_engine.create_workflow(config, steps_config)
            await workflow_engine.start_workflow(workflow_id)
            await workflow_engine.wait_for_completion(workflow_id, timeout=15)
            
            # 获取所有日志
            logs = await workflow_engine.get_workflow_logs(workflow_id)
            
            assert len(logs) == 2
            
            # 验证日志内容
            for log in logs:
                assert "step_id" in log
                assert "step_name" in log
                assert "status" in log
                assert log["step_id"] in ["log_step1", "log_step2"]
            
            # 获取特定步骤的日志
            step1_logs = await workflow_engine.get_workflow_logs(workflow_id, "log_step1")
            assert len(step1_logs) == 1
            assert step1_logs[0]["step_id"] == "log_step1"


@pytest.mark.unit
class TestWorkflowExportImport:
    """工作流导出导入测试类"""
    
    @pytest.mark.asyncio
    async def test_export_workflow_definition(self, workflow_engine):
        """测试导出工作流定义"""
        config = WorkflowConfig(name="导出测试工作流", description="用于测试导出功能")
        steps_config = test_data_generator.generate_workflow_steps(3)
        
        workflow_id = await workflow_engine.create_workflow(config, steps_config)
        
        # 导出工作流定义
        definition = await workflow_engine.export_workflow_definition(workflow_id)
        
        assert definition is not None
        assert "name" in definition
        assert "dag" in definition
        assert definition["name"] == config.name
    
    @pytest.mark.asyncio
    async def test_import_workflow_definition(self, workflow_engine):
        """测试导入工作流定义"""
        # 先创建一个工作流并导出
        config = WorkflowConfig(name="原始工作流")
        steps_config = test_data_generator.generate_workflow_steps(2)
        
        original_id = await workflow_engine.create_workflow(config, steps_config)
        definition = await workflow_engine.export_workflow_definition(original_id)
        
        # 导入工作流定义
        imported_id = await workflow_engine.import_workflow_definition(definition)
        
        assert imported_id != original_id
        
        # 验证导入的工作流
        imported_status = await workflow_engine.get_workflow_status(imported_id)
        assert imported_status is not None
        assert imported_status["name"] == config.name
        assert imported_status["status"] == "imported"
    
    @pytest.mark.asyncio
    async def test_export_nonexistent_workflow(self, workflow_engine):
        """测试导出不存在的工作流"""
        definition = await workflow_engine.export_workflow_definition("nonexistent-id")
        assert definition is None