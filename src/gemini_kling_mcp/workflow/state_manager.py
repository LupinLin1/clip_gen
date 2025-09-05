"""
工作流状态管理器

负责工作流状态的持久化、恢复和管理。
"""

import json
import sqlite3
import asyncio
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass
import threading

from ..logger import get_logger
from ..exceptions import WorkflowError
from .dag import WorkflowDAG, DAGNode


@dataclass
class WorkflowState:
    """工作流状态数据类"""
    workflow_id: str
    name: str
    status: str
    dag: Dict[str, Any]
    context: Dict[str, Any]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "status": self.status,
            "dag": self.dag,
            "context": self.context,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowState":
        return cls(
            workflow_id=data["workflow_id"],
            name=data["name"],
            status=data["status"],
            dag=data["dag"],
            context=data["context"],
            metadata=data["metadata"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"])
        )


class StateBackend:
    """状态后端抽象基类"""
    
    async def save_state(self, state: WorkflowState) -> None:
        raise NotImplementedError
    
    async def load_state(self, workflow_id: str) -> Optional[WorkflowState]:
        raise NotImplementedError
    
    async def delete_state(self, workflow_id: str) -> None:
        raise NotImplementedError
    
    async def list_states(self) -> List[WorkflowState]:
        raise NotImplementedError
    
    async def cleanup_old_states(self, max_age_days: int = 30) -> int:
        raise NotImplementedError


class JSONFileBackend(StateBackend):
    """JSON文件状态后端"""
    
    def __init__(self, storage_dir: str = "/tmp/gemini_kling_mcp/workflows"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger("json_file_backend")
        self._lock = threading.Lock()
    
    def _get_state_file(self, workflow_id: str) -> Path:
        return self.storage_dir / f"{workflow_id}.json"
    
    async def save_state(self, state: WorkflowState) -> None:
        """保存状态到JSON文件"""
        state_file = self._get_state_file(state.workflow_id)
        
        # 更新时间戳
        state.updated_at = datetime.now(timezone.utc)
        
        try:
            with self._lock:
                with open(state_file, 'w', encoding='utf-8') as f:
                    json.dump(state.to_dict(), f, indent=2, ensure_ascii=False)
            
            self.logger.debug(f"已保存工作流状态: {state.workflow_id}")
            
        except Exception as e:
            self.logger.error(f"保存状态失败: {e}")
            raise WorkflowError(f"Failed to save workflow state: {e}")
    
    async def load_state(self, workflow_id: str) -> Optional[WorkflowState]:
        """从JSON文件加载状态"""
        state_file = self._get_state_file(workflow_id)
        
        if not state_file.exists():
            return None
        
        try:
            with self._lock:
                with open(state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            state = WorkflowState.from_dict(data)
            self.logger.debug(f"已加载工作流状态: {workflow_id}")
            return state
            
        except Exception as e:
            self.logger.error(f"加载状态失败: {e}")
            raise WorkflowError(f"Failed to load workflow state: {e}")
    
    async def delete_state(self, workflow_id: str) -> None:
        """删除状态文件"""
        state_file = self._get_state_file(workflow_id)
        
        try:
            with self._lock:
                if state_file.exists():
                    state_file.unlink()
            
            self.logger.debug(f"已删除工作流状态: {workflow_id}")
            
        except Exception as e:
            self.logger.error(f"删除状态失败: {e}")
            raise WorkflowError(f"Failed to delete workflow state: {e}")
    
    async def list_states(self) -> List[WorkflowState]:
        """列出所有状态"""
        states = []
        
        try:
            for state_file in self.storage_dir.glob("*.json"):
                with open(state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                states.append(WorkflowState.from_dict(data))
            
            return states
            
        except Exception as e:
            self.logger.error(f"列出状态失败: {e}")
            raise WorkflowError(f"Failed to list workflow states: {e}")
    
    async def cleanup_old_states(self, max_age_days: int = 30) -> int:
        """清理旧状态文件"""
        from datetime import timedelta
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        
        cleaned_count = 0
        
        try:
            for state_file in self.storage_dir.glob("*.json"):
                try:
                    with open(state_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    updated_at = datetime.fromisoformat(data.get("updated_at", ""))
                    
                    if updated_at < cutoff_date:
                        state_file.unlink()
                        cleaned_count += 1
                        
                except Exception:
                    # 如果文件损坏，也可以清理
                    state_file.unlink()
                    cleaned_count += 1
            
            self.logger.info(f"已清理 {cleaned_count} 个旧状态文件")
            return cleaned_count
            
        except Exception as e:
            self.logger.error(f"清理状态失败: {e}")
            return 0


class SQLiteBackend(StateBackend):
    """SQLite数据库状态后端"""
    
    def __init__(self, db_path: str = "/tmp/gemini_kling_mcp/workflows.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger("sqlite_backend")
        self._lock = threading.Lock()
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS workflow_states (
                        workflow_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        status TEXT NOT NULL,
                        dag TEXT NOT NULL,
                        context TEXT NOT NULL,
                        metadata TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                ''')
                conn.commit()
            finally:
                conn.close()
    
    async def save_state(self, state: WorkflowState) -> None:
        """保存状态到数据库"""
        state.updated_at = datetime.now(timezone.utc)
        
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    conn.execute('''
                        INSERT OR REPLACE INTO workflow_states 
                        (workflow_id, name, status, dag, context, metadata, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        state.workflow_id,
                        state.name,
                        state.status,
                        json.dumps(state.dag),
                        json.dumps(state.context),
                        json.dumps(state.metadata),
                        state.created_at.isoformat(),
                        state.updated_at.isoformat()
                    ))
                    conn.commit()
                finally:
                    conn.close()
            
            self.logger.debug(f"已保存工作流状态: {state.workflow_id}")
            
        except Exception as e:
            self.logger.error(f"保存状态失败: {e}")
            raise WorkflowError(f"Failed to save workflow state: {e}")
    
    async def load_state(self, workflow_id: str) -> Optional[WorkflowState]:
        """从数据库加载状态"""
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.execute('''
                        SELECT workflow_id, name, status, dag, context, metadata, created_at, updated_at
                        FROM workflow_states WHERE workflow_id = ?
                    ''', (workflow_id,))
                    
                    row = cursor.fetchone()
                    
                    if not row:
                        return None
                    
                    data = {
                        "workflow_id": row[0],
                        "name": row[1],
                        "status": row[2],
                        "dag": json.loads(row[3]),
                        "context": json.loads(row[4]),
                        "metadata": json.loads(row[5]),
                        "created_at": row[6],
                        "updated_at": row[7]
                    }
                    
                    state = WorkflowState.from_dict(data)
                    self.logger.debug(f"已加载工作流状态: {workflow_id}")
                    return state
                    
                finally:
                    conn.close()
                    
        except Exception as e:
            self.logger.error(f"加载状态失败: {e}")
            raise WorkflowError(f"Failed to load workflow state: {e}")
    
    async def delete_state(self, workflow_id: str) -> None:
        """从数据库删除状态"""
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    conn.execute('DELETE FROM workflow_states WHERE workflow_id = ?', (workflow_id,))
                    conn.commit()
                finally:
                    conn.close()
            
            self.logger.debug(f"已删除工作流状态: {workflow_id}")
            
        except Exception as e:
            self.logger.error(f"删除状态失败: {e}")
            raise WorkflowError(f"Failed to delete workflow state: {e}")
    
    async def list_states(self) -> List[WorkflowState]:
        """列出所有状态"""
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.execute('''
                        SELECT workflow_id, name, status, dag, context, metadata, created_at, updated_at
                        FROM workflow_states ORDER BY updated_at DESC
                    ''')
                    
                    states = []
                    for row in cursor.fetchall():
                        data = {
                            "workflow_id": row[0],
                            "name": row[1],
                            "status": row[2],
                            "dag": json.loads(row[3]),
                            "context": json.loads(row[4]),
                            "metadata": json.loads(row[5]),
                            "created_at": row[6],
                            "updated_at": row[7]
                        }
                        states.append(WorkflowState.from_dict(data))
                    
                    return states
                    
                finally:
                    conn.close()
                    
        except Exception as e:
            self.logger.error(f"列出状态失败: {e}")
            raise WorkflowError(f"Failed to list workflow states: {e}")
    
    async def cleanup_old_states(self, max_age_days: int = 30) -> int:
        """清理旧状态"""
        from datetime import timedelta
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        cutoff_str = cutoff_date.isoformat()
        
        try:
            with self._lock:
                conn = sqlite3.connect(str(self.db_path))
                try:
                    cursor = conn.execute(
                        'DELETE FROM workflow_states WHERE updated_at < ?', 
                        (cutoff_str,)
                    )
                    cleaned_count = cursor.rowcount
                    conn.commit()
                finally:
                    conn.close()
            
            self.logger.info(f"已清理 {cleaned_count} 个旧状态记录")
            return cleaned_count
            
        except Exception as e:
            self.logger.error(f"清理状态失败: {e}")
            return 0


class WorkflowStateManager:
    """工作流状态管理器"""
    
    def __init__(self, backend: Optional[StateBackend] = None):
        self.backend = backend or JSONFileBackend()
        self.logger = get_logger("workflow_state_manager")
    
    async def save_workflow(self, workflow_id: str, name: str, 
                          dag: WorkflowDAG, context: Dict[str, Any],
                          status: str = "running", 
                          metadata: Optional[Dict[str, Any]] = None) -> None:
        """保存工作流状态"""
        now = datetime.now(timezone.utc)
        
        # 检查是否已存在
        existing_state = await self.backend.load_state(workflow_id)
        created_at = existing_state.created_at if existing_state else now
        
        state = WorkflowState(
            workflow_id=workflow_id,
            name=name,
            status=status,
            dag=dag.to_dict(),
            context=context,
            metadata=metadata or {},
            created_at=created_at,
            updated_at=now
        )
        
        await self.backend.save_state(state)
        self.logger.debug(f"已保存工作流: {workflow_id}")
    
    async def load_workflow(self, workflow_id: str) -> Optional[Tuple[WorkflowDAG, Dict[str, Any], str, Dict[str, Any]]]:
        """加载工作流状态"""
        state = await self.backend.load_state(workflow_id)
        if not state:
            return None
        
        dag = WorkflowDAG.from_dict(state.dag)
        
        self.logger.debug(f"已加载工作流: {workflow_id}")
        return dag, state.context, state.status, state.metadata
    
    async def update_workflow_status(self, workflow_id: str, status: str, 
                                   metadata: Optional[Dict[str, Any]] = None) -> None:
        """更新工作流状态"""
        state = await self.backend.load_state(workflow_id)
        if not state:
            raise WorkflowError(f"工作流 {workflow_id} 不存在")
        
        state.status = status
        if metadata:
            state.metadata.update(metadata)
        
        await self.backend.save_state(state)
        self.logger.debug(f"已更新工作流状态: {workflow_id} -> {status}")
    
    async def delete_workflow(self, workflow_id: str) -> None:
        """删除工作流"""
        await self.backend.delete_state(workflow_id)
        self.logger.debug(f"已删除工作流: {workflow_id}")
    
    async def list_workflows(self) -> List[Dict[str, Any]]:
        """列出所有工作流"""
        states = await self.backend.list_states()
        
        return [{
            "workflow_id": state.workflow_id,
            "name": state.name,
            "status": state.status,
            "created_at": state.created_at.isoformat(),
            "updated_at": state.updated_at.isoformat(),
            "progress": state.dag.get("progress", {}) if state.dag else {}
        } for state in states]
    
    async def get_workflow_progress(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """获取工作流进度"""
        state = await self.backend.load_state(workflow_id)
        if not state:
            return None
        
        dag = WorkflowDAG.from_dict(state.dag)
        progress = dag.get_progress()
        
        return {
            "workflow_id": workflow_id,
            "name": state.name,
            "status": state.status,
            "progress": progress,
            "updated_at": state.updated_at.isoformat()
        }
    
    async def cleanup_old_workflows(self, max_age_days: int = 30) -> int:
        """清理旧工作流"""
        return await self.backend.cleanup_old_states(max_age_days)
    
    async def export_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """导出工作流配置"""
        state = await self.backend.load_state(workflow_id)
        if not state:
            return None
        
        return {
            "name": state.name,
            "dag": state.dag,
            "metadata": state.metadata
        }
    
    async def import_workflow(self, workflow_id: str, workflow_config: Dict[str, Any]) -> None:
        """导入工作流配置"""
        dag = WorkflowDAG.from_dict(workflow_config["dag"])
        
        await self.save_workflow(
            workflow_id=workflow_id,
            name=workflow_config["name"],
            dag=dag,
            context={},
            status="imported",
            metadata=workflow_config.get("metadata", {})
        )
        
        self.logger.info(f"已导入工作流: {workflow_id}")