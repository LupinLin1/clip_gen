"""
有向无环图（DAG）实现

用于工作流执行顺序的管理和依赖关系解析。
"""

from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import networkx as nx
from collections import defaultdict, deque

from ..logger import get_logger
from ..exceptions import WorkflowError


class NodeStatus(Enum):
    """节点状态枚举"""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class DAGNode:
    """DAG节点定义"""
    id: str
    name: str
    type: str
    config: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    status: NodeStatus = NodeStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "config": self.config,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DAGNode":
        """从字典创建节点"""
        return cls(
            id=data["id"],
            name=data["name"],
            type=data["type"],
            config=data.get("config", {}),
            dependencies=data.get("dependencies", []),
            status=NodeStatus(data.get("status", "pending")),
            result=data.get("result"),
            error=data.get("error"),
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3)
        )


class WorkflowDAG:
    """工作流有向无环图管理器"""
    
    def __init__(self):
        self.nodes: Dict[str, DAGNode] = {}
        self.graph: nx.DiGraph = nx.DiGraph()
        self.logger = get_logger("workflow_dag")
        
    def add_node(self, node: DAGNode) -> None:
        """添加节点"""
        if node.id in self.nodes:
            raise WorkflowError(f"节点 {node.id} 已存在")
        
        self.nodes[node.id] = node
        self.graph.add_node(node.id)
        
        # 添加依赖边
        for dep_id in node.dependencies:
            if dep_id not in self.nodes:
                raise WorkflowError(f"依赖节点 {dep_id} 不存在")
            self.graph.add_edge(dep_id, node.id)
        
        # 检查是否存在循环
        if not nx.is_directed_acyclic_graph(self.graph):
            # 回滚更改
            self.graph.remove_node(node.id)
            del self.nodes[node.id]
            raise WorkflowError(f"添加节点 {node.id} 会创建循环依赖")
        
        self.logger.debug(f"已添加节点: {node.id}")
    
    def remove_node(self, node_id: str) -> None:
        """移除节点"""
        if node_id not in self.nodes:
            raise WorkflowError(f"节点 {node_id} 不存在")
        
        # 检查是否有其他节点依赖此节点
        dependents = list(self.graph.successors(node_id))
        if dependents:
            raise WorkflowError(f"无法移除节点 {node_id}，存在依赖节点: {dependents}")
        
        self.graph.remove_node(node_id)
        del self.nodes[node_id]
        self.logger.debug(f"已移除节点: {node_id}")
    
    def get_node(self, node_id: str) -> Optional[DAGNode]:
        """获取节点"""
        return self.nodes.get(node_id)
    
    def get_all_nodes(self) -> List[DAGNode]:
        """获取所有节点"""
        return list(self.nodes.values())
    
    def get_ready_nodes(self) -> List[DAGNode]:
        """获取所有准备就绪的节点（依赖已完成且状态为PENDING或READY）"""
        ready_nodes = []
        
        for node in self.nodes.values():
            if node.status not in [NodeStatus.PENDING, NodeStatus.READY]:
                continue
            
            # 检查所有依赖是否已完成
            all_deps_completed = True
            for dep_id in node.dependencies:
                dep_node = self.nodes[dep_id]
                if dep_node.status != NodeStatus.COMPLETED:
                    all_deps_completed = False
                    break
            
            if all_deps_completed:
                node.status = NodeStatus.READY
                ready_nodes.append(node)
        
        return ready_nodes
    
    def get_running_nodes(self) -> List[DAGNode]:
        """获取所有正在运行的节点"""
        return [node for node in self.nodes.values() if node.status == NodeStatus.RUNNING]
    
    def get_failed_nodes(self) -> List[DAGNode]:
        """获取所有失败的节点"""
        return [node for node in self.nodes.values() if node.status == NodeStatus.FAILED]
    
    def get_completed_nodes(self) -> List[DAGNode]:
        """获取所有已完成的节点"""
        return [node for node in self.nodes.values() if node.status == NodeStatus.COMPLETED]
    
    def get_topological_order(self) -> List[str]:
        """获取拓扑排序顺序"""
        try:
            return list(nx.topological_sort(self.graph))
        except nx.NetworkXError as e:
            raise WorkflowError(f"无法获取拓扑排序: {e}")
    
    def get_execution_levels(self) -> List[List[str]]:
        """获取可并行执行的层级"""
        levels = []
        remaining_nodes = set(self.nodes.keys())
        
        while remaining_nodes:
            # 找到当前层级中没有未满足依赖的节点
            current_level = []
            for node_id in list(remaining_nodes):
                node = self.nodes[node_id]
                deps_in_remaining = set(node.dependencies) & remaining_nodes
                if not deps_in_remaining:
                    current_level.append(node_id)
            
            if not current_level:
                # 如果没有找到可执行的节点，说明有循环依赖
                raise WorkflowError("检测到循环依赖")
            
            levels.append(current_level)
            remaining_nodes -= set(current_level)
        
        return levels
    
    def can_execute(self, node_id: str) -> bool:
        """检查节点是否可以执行"""
        node = self.nodes.get(node_id)
        if not node:
            return False
        
        if node.status != NodeStatus.READY:
            return False
        
        # 检查所有依赖是否已完成
        for dep_id in node.dependencies:
            dep_node = self.nodes[dep_id]
            if dep_node.status != NodeStatus.COMPLETED:
                return False
        
        return True
    
    def mark_node_running(self, node_id: str) -> None:
        """标记节点为运行中"""
        node = self.nodes.get(node_id)
        if not node:
            raise WorkflowError(f"节点 {node_id} 不存在")
        
        node.status = NodeStatus.RUNNING
        import time
        node.start_time = time.time()
        self.logger.debug(f"节点 {node_id} 开始执行")
    
    def mark_node_completed(self, node_id: str, result: Any = None) -> None:
        """标记节点为已完成"""
        node = self.nodes.get(node_id)
        if not node:
            raise WorkflowError(f"节点 {node_id} 不存在")
        
        node.status = NodeStatus.COMPLETED
        node.result = result
        node.error = None
        import time
        node.end_time = time.time()
        self.logger.debug(f"节点 {node_id} 执行完成")
    
    def mark_node_failed(self, node_id: str, error: str) -> None:
        """标记节点为失败"""
        node = self.nodes.get(node_id)
        if not node:
            raise WorkflowError(f"节点 {node_id} 不存在")
        
        node.status = NodeStatus.FAILED
        node.error = error
        import time
        node.end_time = time.time()
        self.logger.error(f"节点 {node_id} 执行失败: {error}")
    
    def can_retry(self, node_id: str) -> bool:
        """检查节点是否可以重试"""
        node = self.nodes.get(node_id)
        if not node:
            return False
        
        return (node.status == NodeStatus.FAILED and 
                node.retry_count < node.max_retries)
    
    def retry_node(self, node_id: str) -> None:
        """重试失败的节点"""
        node = self.nodes.get(node_id)
        if not node:
            raise WorkflowError(f"节点 {node_id} 不存在")
        
        if not self.can_retry(node_id):
            raise WorkflowError(f"节点 {node_id} 不能重试")
        
        node.status = NodeStatus.PENDING
        node.error = None
        node.result = None
        node.retry_count += 1
        node.start_time = None
        node.end_time = None
        self.logger.info(f"重试节点 {node_id}，第 {node.retry_count} 次重试")
    
    def reset_all_nodes(self) -> None:
        """重置所有节点状态"""
        for node in self.nodes.values():
            node.status = NodeStatus.PENDING
            node.result = None
            node.error = None
            node.start_time = None
            node.end_time = None
            node.retry_count = 0
        self.logger.info("已重置所有节点状态")
    
    def is_completed(self) -> bool:
        """检查整个DAG是否已完成"""
        return all(node.status in [NodeStatus.COMPLETED, NodeStatus.SKIPPED] 
                  for node in self.nodes.values())
    
    def has_failures(self) -> bool:
        """检查是否有失败的节点"""
        return any(node.status == NodeStatus.FAILED for node in self.nodes.values())
    
    def get_progress(self) -> Dict[str, int]:
        """获取执行进度统计"""
        status_counts = defaultdict(int)
        for node in self.nodes.values():
            status_counts[node.status.value] += 1
        
        total = len(self.nodes)
        completed = status_counts[NodeStatus.COMPLETED.value]
        
        return {
            "total": total,
            "completed": completed,
            "failed": status_counts[NodeStatus.FAILED.value],
            "running": status_counts[NodeStatus.RUNNING.value],
            "pending": status_counts[NodeStatus.PENDING.value],
            "ready": status_counts[NodeStatus.READY.value],
            "skipped": status_counts[NodeStatus.SKIPPED.value],
            "progress_percent": (completed / total * 100) if total > 0 else 0
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "nodes": {node_id: node.to_dict() for node_id, node in self.nodes.items()},
            "edges": list(self.graph.edges()),
            "progress": self.get_progress()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowDAG":
        """从字典创建DAG"""
        dag = cls()
        
        # 先添加所有节点（不包含依赖）
        for node_id, node_data in data["nodes"].items():
            node = DAGNode.from_dict(node_data)
            node.dependencies = []  # 暂时清空依赖
            dag.nodes[node_id] = node
            dag.graph.add_node(node_id)
        
        # 然后添加依赖关系
        for node_id, node_data in data["nodes"].items():
            node = dag.nodes[node_id]
            node.dependencies = node_data.get("dependencies", [])
            for dep_id in node.dependencies:
                dag.graph.add_edge(dep_id, node_id)
        
        return dag