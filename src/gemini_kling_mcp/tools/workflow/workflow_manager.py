"""
工作流管理工具

提供工作流的创建、执行、监控和管理功能。
"""

import asyncio
from typing import Dict, Any, Optional, List

from ...logger import get_logger
from ...exceptions import ToolExecutionError
from ...workflow import WorkflowEngine, WorkflowConfig, template_library
from ...tools.registry import tool


@tool(
    name="create_custom_workflow",
    description="Create a custom workflow from step definitions"
)
async def create_custom_workflow(
    name: str,
    description: str,
    steps: List[Dict[str, Any]],
    initial_context: Optional[Dict[str, Any]] = None,
    config_options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    创建自定义工作流
    
    Args:
        name: 工作流名称
        description: 工作流描述
        steps: 步骤定义列表
        initial_context: 初始上下文
        config_options: 配置选项
    
    Returns:
        创建的工作流信息
    """
    logger = get_logger("workflow_manager")
    
    try:
        # 创建工作流引擎
        engine = WorkflowEngine()
        
        # 创建配置
        config = WorkflowConfig(
            name=name,
            description=description,
            **config_options or {}
        )
        
        # 验证步骤定义
        _validate_steps(steps)
        
        # 创建工作流
        workflow_id = await engine.create_workflow(
            config=config,
            steps_config=steps,
            initial_context=initial_context or {}
        )
        
        result = {
            "success": True,
            "workflow_id": workflow_id,
            "name": name,
            "description": description,
            "steps_count": len(steps),
            "status": "created"
        }
        
        logger.info(f"已创建自定义工作流: {workflow_id} ({name})")
        return result
        
    except Exception as e:
        logger.error(f"创建自定义工作流失败: {e}")
        raise ToolExecutionError(
            f"创建自定义工作流失败: {str(e)}",
            tool_name="create_custom_workflow",
            details={"error": str(e)}
        )


@tool(
    name="execute_workflow",
    description="Execute a workflow by ID"
)
async def execute_workflow(
    workflow_id: str,
    timeout_minutes: Optional[int] = 30
) -> Dict[str, Any]:
    """
    执行工作流
    
    Args:
        workflow_id: 工作流ID
        timeout_minutes: 超时时间（分钟）
    
    Returns:
        执行结果
    """
    logger = get_logger("workflow_manager")
    
    try:
        # 创建工作流引擎
        engine = WorkflowEngine()
        
        # 启动工作流
        await engine.start_workflow(workflow_id)
        
        logger.info(f"已启动工作流执行: {workflow_id}")
        
        # 等待完成
        timeout_seconds = timeout_minutes * 60 if timeout_minutes else None
        success = await engine.wait_for_completion(workflow_id, timeout=timeout_seconds)
        
        if not success:
            raise ToolExecutionError(
                f"工作流执行超时（{timeout_minutes}分钟）",
                tool_name="execute_workflow",
                details={"workflow_id": workflow_id}
            )
        
        # 获取最终状态
        status = await engine.get_workflow_status(workflow_id)
        
        if status["status"] != "completed":
            logs = await engine.get_workflow_logs(workflow_id)
            raise ToolExecutionError(
                f"工作流执行失败: {status.get('error', 'Unknown error')}",
                tool_name="execute_workflow",
                details={"workflow_id": workflow_id, "logs": logs}
            )
        
        # 加载结果
        workflow_data = await engine.state_manager.load_workflow(workflow_id)
        if not workflow_data:
            raise ToolExecutionError(
                "无法加载工作流结果",
                tool_name="execute_workflow"
            )
        
        dag, context, _, metadata = workflow_data
        
        result = {
            "success": True,
            "workflow_id": workflow_id,
            "status": "completed",
            "context": context,
            "metadata": metadata,
            "execution_summary": {
                "total_steps": len(dag.get_all_nodes()),
                "completed_steps": len(dag.get_completed_nodes()),
                "failed_steps": len(dag.get_failed_nodes()),
                "execution_time": metadata.get("execution_time", 0)
            }
        }
        
        logger.info(f"工作流执行完成: {workflow_id}")
        return result
        
    except ToolExecutionError:
        raise
    except Exception as e:
        logger.error(f"执行工作流异常: {e}")
        raise ToolExecutionError(
            f"执行工作流失败: {str(e)}",
            tool_name="execute_workflow",
            details={"workflow_id": workflow_id, "error": str(e)}
        )


@tool(
    name="get_workflow_status",
    description="Get the current status of a workflow"
)
async def get_workflow_status(workflow_id: str) -> Dict[str, Any]:
    """
    获取工作流状态
    
    Args:
        workflow_id: 工作流ID
    
    Returns:
        工作流状态信息
    """
    logger = get_logger("workflow_manager")
    
    try:
        # 创建工作流引擎
        engine = WorkflowEngine()
        
        # 获取状态
        status = await engine.get_workflow_status(workflow_id)
        
        if not status:
            raise ToolExecutionError(
                f"工作流 {workflow_id} 不存在",
                tool_name="get_workflow_status"
            )
        
        # 获取详细日志
        logs = await engine.get_workflow_logs(workflow_id)
        
        result = {
            "success": True,
            "workflow_id": workflow_id,
            **status,
            "step_logs": logs,
            "is_running": workflow_id in engine.running_workflows
        }
        
        return result
        
    except ToolExecutionError:
        raise
    except Exception as e:
        logger.error(f"获取工作流状态异常: {e}")
        raise ToolExecutionError(
            f"获取工作流状态失败: {str(e)}",
            tool_name="get_workflow_status",
            details={"workflow_id": workflow_id, "error": str(e)}
        )


@tool(
    name="list_workflows",
    description="List all workflows with their current status"
)
async def list_workflows() -> Dict[str, Any]:
    """
    列出所有工作流
    
    Returns:
        工作流列表
    """
    logger = get_logger("workflow_manager")
    
    try:
        # 创建工作流引擎
        engine = WorkflowEngine()
        
        # 获取工作流列表
        workflows = await engine.list_workflows()
        
        result = {
            "success": True,
            "total_count": len(workflows),
            "workflows": workflows,
            "running_count": len(engine.running_workflows),
            "running_workflows": list(engine.running_workflows.keys())
        }
        
        return result
        
    except Exception as e:
        logger.error(f"列出工作流异常: {e}")
        raise ToolExecutionError(
            f"列出工作流失败: {str(e)}",
            tool_name="list_workflows",
            details={"error": str(e)}
        )


@tool(
    name="cancel_workflow",
    description="Cancel a running workflow"
)
async def cancel_workflow(workflow_id: str) -> Dict[str, Any]:
    """
    取消工作流执行
    
    Args:
        workflow_id: 工作流ID
    
    Returns:
        取消结果
    """
    logger = get_logger("workflow_manager")
    
    try:
        # 创建工作流引擎
        engine = WorkflowEngine()
        
        # 取消工作流
        await engine.cancel_workflow(workflow_id)
        
        result = {
            "success": True,
            "workflow_id": workflow_id,
            "status": "cancelled",
            "message": "工作流已成功取消"
        }
        
        logger.info(f"已取消工作流: {workflow_id}")
        return result
        
    except Exception as e:
        logger.error(f"取消工作流异常: {e}")
        raise ToolExecutionError(
            f"取消工作流失败: {str(e)}",
            tool_name="cancel_workflow",
            details={"workflow_id": workflow_id, "error": str(e)}
        )


@tool(
    name="list_workflow_templates",
    description="List available workflow templates"
)
async def list_workflow_templates(tag: Optional[str] = None) -> Dict[str, Any]:
    """
    列出工作流模板
    
    Args:
        tag: 可选的标签过滤
    
    Returns:
        模板列表
    """
    logger = get_logger("workflow_manager")
    
    try:
        # 获取模板列表
        templates = template_library.list_templates(tag=tag)
        
        template_list = []
        for template in templates:
            template_list.append({
                "id": template.id,
                "name": template.name,
                "description": template.description,
                "steps_count": len(template.steps),
                "expected_outputs": template.expected_outputs,
                "tags": template.tags or [],
                "example_inputs": template.example_inputs
            })
        
        result = {
            "success": True,
            "total_count": len(template_list),
            "templates": template_list,
            "filter_tag": tag
        }
        
        return result
        
    except Exception as e:
        logger.error(f"列出工作流模板异常: {e}")
        raise ToolExecutionError(
            f"列出工作流模板失败: {str(e)}",
            tool_name="list_workflow_templates",
            details={"error": str(e)}
        )


@tool(
    name="create_workflow_from_template",
    description="Create a workflow from a template"
)
async def create_workflow_from_template(
    template_id: str,
    name: Optional[str] = None,
    initial_context: Optional[Dict[str, Any]] = None,
    config_overrides: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    从模板创建工作流
    
    Args:
        template_id: 模板ID
        name: 自定义工作流名称
        initial_context: 初始上下文
        config_overrides: 配置覆盖
    
    Returns:
        创建的工作流信息
    """
    logger = get_logger("workflow_manager")
    
    try:
        # 获取模板
        template = template_library.get_template(template_id)
        
        # 创建工作流引擎
        engine = WorkflowEngine()
        
        # 准备配置
        config = template.config
        if name:
            config.name = name
        if config_overrides:
            for key, value in config_overrides.items():
                if hasattr(config, key):
                    setattr(config, key, value)
        
        # 创建工作流
        workflow_id = await engine.create_workflow(
            config=config,
            steps_config=template.steps,
            initial_context=initial_context or {}
        )
        
        result = {
            "success": True,
            "workflow_id": workflow_id,
            "template_id": template_id,
            "name": config.name,
            "description": template.description,
            "steps_count": len(template.steps),
            "expected_outputs": template.expected_outputs,
            "status": "created"
        }
        
        logger.info(f"已从模板 {template_id} 创建工作流: {workflow_id}")
        return result
        
    except Exception as e:
        logger.error(f"从模板创建工作流异常: {e}")
        raise ToolExecutionError(
            f"从模板创建工作流失败: {str(e)}",
            tool_name="create_workflow_from_template",
            details={"template_id": template_id, "error": str(e)}
        )


def _validate_steps(steps: List[Dict[str, Any]]) -> None:
    """验证步骤定义"""
    required_fields = ["id", "type"]
    
    for i, step in enumerate(steps):
        for field in required_fields:
            if field not in step:
                raise ValueError(f"步骤 {i} 缺少必需字段: {field}")
        
        # 检查步骤ID唯一性
        step_ids = [s["id"] for s in steps]
        if len(set(step_ids)) != len(step_ids):
            raise ValueError("步骤ID必须唯一")
        
        # 检查依赖关系
        dependencies = step.get("dependencies", [])
        for dep in dependencies:
            if dep not in step_ids:
                raise ValueError(f"步骤 {step['id']} 的依赖 {dep} 不存在")