"""
工作流引擎核心

提供工作流的执行、管理和监控功能。
"""

import asyncio
import time
import uuid
from typing import Dict, List, Any, Optional, Callable, Set, Union
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timezone

from ..logger import get_logger
from ..exceptions import WorkflowError
from .dag import WorkflowDAG, DAGNode, NodeStatus
from .steps import WorkflowStep, StepFactory, StepResult, StepType
from .state_manager import WorkflowStateManager
from ..config import get_config


class WorkflowStatus(Enum):
    """工作流状态枚举"""
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowConfig:
    """工作流配置"""
    name: str
    description: str = ""
    max_concurrent_steps: int = 3
    retry_failed_steps: bool = True
    timeout_seconds: Optional[int] = None
    cleanup_on_completion: bool = False
    save_intermediate_results: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "max_concurrent_steps": self.max_concurrent_steps,
            "retry_failed_steps": self.retry_failed_steps,
            "timeout_seconds": self.timeout_seconds,
            "cleanup_on_completion": self.cleanup_on_completion,
            "save_intermediate_results": self.save_intermediate_results
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowConfig":
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            max_concurrent_steps=data.get("max_concurrent_steps", 3),
            retry_failed_steps=data.get("retry_failed_steps", True),
            timeout_seconds=data.get("timeout_seconds"),
            cleanup_on_completion=data.get("cleanup_on_completion", False),
            save_intermediate_results=data.get("save_intermediate_results", True)
        )


class WorkflowEngine:
    """工作流引擎"""
    
    def __init__(self, state_manager: Optional[WorkflowStateManager] = None):
        self.state_manager = state_manager or WorkflowStateManager()
        self.logger = get_logger("workflow_engine")
        self.running_workflows: Dict[str, asyncio.Task] = {}
        self.workflow_callbacks: Dict[str, List[Callable]] = {}
    
    async def create_workflow(self, config: WorkflowConfig, 
                            steps_config: List[Dict[str, Any]],
                            initial_context: Optional[Dict[str, Any]] = None) -> str:
        """创建新工作流"""
        workflow_id = str(uuid.uuid4())
        
        try:
            # 创建DAG
            dag = WorkflowDAG()
            
            # 添加步骤节点
            for step_config in steps_config:
                node = DAGNode(
                    id=step_config["id"],
                    name=step_config.get("name", step_config["id"]),
                    type=step_config["type"],
                    config=step_config.get("config", {}),
                    dependencies=step_config.get("dependencies", []),
                    max_retries=step_config.get("max_retries", 3)
                )
                dag.add_node(node)
            
            # 保存工作流状态
            await self.state_manager.save_workflow(
                workflow_id=workflow_id,
                name=config.name,
                dag=dag,
                context=initial_context or {},
                status=WorkflowStatus.CREATED.value,
                metadata=config.to_dict()
            )
            
            self.logger.info(f"已创建工作流: {workflow_id} ({config.name})")
            return workflow_id
            
        except Exception as e:
            self.logger.error(f"创建工作流失败: {e}")
            raise WorkflowError(f"Failed to create workflow: {e}")
    
    async def start_workflow(self, workflow_id: str) -> None:
        """启动工作流执行"""
        if workflow_id in self.running_workflows:
            raise WorkflowError(f"工作流 {workflow_id} 已在运行中")
        
        # 加载工作流状态
        workflow_data = await self.state_manager.load_workflow(workflow_id)
        if not workflow_data:
            raise WorkflowError(f"工作流 {workflow_id} 不存在")
        
        dag, context, status, metadata = workflow_data
        config = WorkflowConfig.from_dict(metadata)
        
        # 创建执行任务
        task = asyncio.create_task(
            self._execute_workflow(workflow_id, config, dag, context)
        )
        self.running_workflows[workflow_id] = task
        
        # 更新状态为运行中
        await self.state_manager.update_workflow_status(
            workflow_id, WorkflowStatus.RUNNING.value
        )
        
        self.logger.info(f"已启动工作流执行: {workflow_id}")
    
    async def pause_workflow(self, workflow_id: str) -> None:
        """暂停工作流执行"""
        if workflow_id not in self.running_workflows:
            raise WorkflowError(f"工作流 {workflow_id} 未在运行")
        
        task = self.running_workflows[workflow_id]
        task.cancel()
        
        await self.state_manager.update_workflow_status(
            workflow_id, WorkflowStatus.PAUSED.value
        )
        
        self.logger.info(f"已暂停工作流: {workflow_id}")
    
    async def resume_workflow(self, workflow_id: str) -> None:
        """恢复工作流执行"""
        await self.start_workflow(workflow_id)
        self.logger.info(f"已恢复工作流: {workflow_id}")
    
    async def cancel_workflow(self, workflow_id: str) -> None:
        """取消工作流执行"""
        if workflow_id in self.running_workflows:
            task = self.running_workflows[workflow_id]
            task.cancel()
            del self.running_workflows[workflow_id]
        
        await self.state_manager.update_workflow_status(
            workflow_id, WorkflowStatus.CANCELLED.value
        )
        
        self.logger.info(f"已取消工作流: {workflow_id}")
    
    async def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """获取工作流状态"""
        return await self.state_manager.get_workflow_progress(workflow_id)
    
    async def list_workflows(self) -> List[Dict[str, Any]]:
        """列出所有工作流"""
        return await self.state_manager.list_workflows()
    
    async def wait_for_completion(self, workflow_id: str, timeout: Optional[float] = None) -> bool:
        """等待工作流完成"""
        if workflow_id not in self.running_workflows:
            return True
        
        try:
            task = self.running_workflows[workflow_id]
            await asyncio.wait_for(task, timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False
        except asyncio.CancelledError:
            return False
    
    def add_callback(self, workflow_id: str, callback: Callable[[str, str, Dict[str, Any]], None]) -> None:
        """添加工作流状态变化回调"""
        if workflow_id not in self.workflow_callbacks:
            self.workflow_callbacks[workflow_id] = []
        self.workflow_callbacks[workflow_id].append(callback)
    
    async def _execute_workflow(self, workflow_id: str, config: WorkflowConfig, 
                              dag: WorkflowDAG, context: Dict[str, Any]) -> None:
        """执行工作流"""
        start_time = time.time()
        
        try:
            self.logger.info(f"开始执行工作流: {workflow_id}")
            
            # 执行主循环
            while not dag.is_completed() and not dag.has_failures():
                # 获取准备就绪的节点
                ready_nodes = dag.get_ready_nodes()
                
                if not ready_nodes:
                    # 如果没有准备就绪的节点，检查是否还有运行中的节点
                    running_nodes = dag.get_running_nodes()
                    if not running_nodes:
                        # 没有运行中的节点，可能存在死锁或者所有节点都完成了
                        break
                    
                    # 等待一些运行中的节点完成
                    await asyncio.sleep(0.1)
                    continue
                
                # 限制并发执行的步骤数量
                concurrent_limit = min(config.max_concurrent_steps, len(ready_nodes))
                selected_nodes = ready_nodes[:concurrent_limit]
                
                # 并发执行选中的步骤
                tasks = []
                for node in selected_nodes:
                    dag.mark_node_running(node.id)
                    task = self._execute_step(workflow_id, node, context, config)
                    tasks.append(task)
                
                # 等待这批步骤完成
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 处理执行结果
                for i, result in enumerate(results):
                    node = selected_nodes[i]
                    
                    if isinstance(result, Exception):
                        error_msg = str(result)
                        dag.mark_node_failed(node.id, error_msg)
                        self.logger.error(f"步骤 {node.id} 执行失败: {error_msg}")
                        
                        # 检查是否需要重试
                        if config.retry_failed_steps and dag.can_retry(node.id):
                            dag.retry_node(node.id)
                            self.logger.info(f"将重试步骤 {node.id}")
                    
                    elif isinstance(result, StepResult):
                        if result.success:
                            dag.mark_node_completed(node.id, result.data)
                            
                            # 更新上下文
                            if result.data and config.save_intermediate_results:
                                context.update(result.data)
                            
                            self.logger.info(f"步骤 {node.id} 执行完成")
                        else:
                            dag.mark_node_failed(node.id, result.error or "Unknown error")
                            
                            # 检查是否需要重试
                            if config.retry_failed_steps and dag.can_retry(node.id):
                                dag.retry_node(node.id)
                    
                    # 保存中间状态
                    await self.state_manager.save_workflow(
                        workflow_id, config.name, dag, context, 
                        WorkflowStatus.RUNNING.value, config.to_dict()
                    )
                
                # 触发回调
                await self._trigger_callbacks(workflow_id, "step_completed", {
                    "completed_steps": [node.id for node in selected_nodes],
                    "progress": dag.get_progress()
                })
            
            # 确定最终状态
            if dag.is_completed():
                final_status = WorkflowStatus.COMPLETED.value
                self.logger.info(f"工作流 {workflow_id} 执行完成")
            elif dag.has_failures():
                final_status = WorkflowStatus.FAILED.value
                failed_nodes = dag.get_failed_nodes()
                self.logger.error(f"工作流 {workflow_id} 执行失败，失败节点: {[n.id for n in failed_nodes]}")
            else:
                final_status = WorkflowStatus.FAILED.value
                self.logger.error(f"工作流 {workflow_id} 执行异常终止")
            
            # 更新最终状态
            execution_time = time.time() - start_time
            await self.state_manager.update_workflow_status(
                workflow_id, final_status, {
                    "execution_time": execution_time,
                    "completed_at": datetime.now(timezone.utc).isoformat()
                }
            )
            
            # 触发完成回调
            await self._trigger_callbacks(workflow_id, "workflow_completed", {
                "status": final_status,
                "execution_time": execution_time,
                "progress": dag.get_progress()
            })
            
            # 清理
            if workflow_id in self.running_workflows:
                del self.running_workflows[workflow_id]
            
            if config.cleanup_on_completion:
                await self.state_manager.delete_workflow(workflow_id)
        
        except asyncio.CancelledError:
            self.logger.info(f"工作流 {workflow_id} 执行被取消")
            if workflow_id in self.running_workflows:
                del self.running_workflows[workflow_id]
            raise
        
        except Exception as e:
            self.logger.error(f"工作流 {workflow_id} 执行异常: {e}")
            
            await self.state_manager.update_workflow_status(
                workflow_id, WorkflowStatus.FAILED.value, {
                    "error": str(e),
                    "failed_at": datetime.now(timezone.utc).isoformat()
                }
            )
            
            if workflow_id in self.running_workflows:
                del self.running_workflows[workflow_id]
            
            raise WorkflowError(f"工作流执行失败: {e}", workflow_id=workflow_id)
    
    async def _execute_step(self, workflow_id: str, node: DAGNode, 
                          context: Dict[str, Any], config: WorkflowConfig) -> StepResult:
        """执行单个步骤"""
        try:
            # 创建步骤实例
            step = StepFactory.create_step(
                step_type=node.type,
                step_id=node.id,
                name=node.name,
                config=node.config
            )
            
            # 验证配置
            if not step.validate_config():
                raise WorkflowError(f"步骤 {node.id} 配置无效", 
                                  workflow_id=workflow_id, step_id=node.id)
            
            # 执行步骤
            self.logger.debug(f"开始执行步骤: {node.id}")
            result = await step.execute(context)
            
            self.logger.debug(f"步骤 {node.id} 执行完成，耗时: {result.execution_time:.2f}s")
            return result
            
        except Exception as e:
            self.logger.error(f"步骤 {node.id} 执行异常: {e}")
            return StepResult(
                success=False,
                error=str(e),
                execution_time=time.time()
            )
    
    async def _trigger_callbacks(self, workflow_id: str, event: str, data: Dict[str, Any]) -> None:
        """触发工作流回调"""
        callbacks = self.workflow_callbacks.get(workflow_id, [])
        
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(workflow_id, event, data)
                else:
                    callback(workflow_id, event, data)
            except Exception as e:
                self.logger.error(f"回调执行失败: {e}")
    
    async def get_workflow_logs(self, workflow_id: str, 
                              step_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取工作流执行日志"""
        # 这里可以实现更详细的日志记录和检索
        # 目前返回基本的状态信息
        workflow_data = await self.state_manager.load_workflow(workflow_id)
        if not workflow_data:
            return []
        
        dag, context, status, metadata = workflow_data
        
        logs = []
        for node in dag.get_all_nodes():
            if step_id and node.id != step_id:
                continue
            
            log_entry = {
                "step_id": node.id,
                "step_name": node.name,
                "status": node.status.value,
                "start_time": node.start_time,
                "end_time": node.end_time,
                "execution_time": (node.end_time - node.start_time) if node.start_time and node.end_time else None,
                "retry_count": node.retry_count,
                "error": node.error,
                "result_summary": self._summarize_result(node.result) if node.result else None
            }
            logs.append(log_entry)
        
        return logs
    
    def _summarize_result(self, result: Any) -> Dict[str, Any]:
        """总结步骤执行结果"""
        if isinstance(result, dict):
            summary = {}
            for key, value in result.items():
                if isinstance(value, str):
                    summary[key] = f"{len(value)} characters" if len(value) > 100 else value
                elif isinstance(value, (list, tuple)):
                    summary[key] = f"{len(value)} items"
                elif isinstance(value, dict):
                    summary[key] = f"dict with {len(value)} keys"
                else:
                    summary[key] = str(type(value).__name__)
            return summary
        else:
            return {"type": str(type(result).__name__)}
    
    async def export_workflow_definition(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """导出工作流定义"""
        return await self.state_manager.export_workflow(workflow_id)
    
    async def import_workflow_definition(self, workflow_definition: Dict[str, Any]) -> str:
        """导入工作流定义"""
        workflow_id = str(uuid.uuid4())
        await self.state_manager.import_workflow(workflow_id, workflow_definition)
        return workflow_id