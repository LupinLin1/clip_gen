"""
文件缓存优化

提供文件缓存、智能预加载和缓存生命周期管理功能。
"""

import time
import threading
import weakref
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, Set, List, Union, Callable
import hashlib
import pickle
import json
from concurrent.futures import ThreadPoolExecutor, Future

from ..logger import get_logger
from .core import FileMetadata

logger = get_logger(__name__)

@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    data: Any
    metadata: FileMetadata
    created_at: datetime
    accessed_at: datetime
    access_count: int = 0
    size: int = 0
    tags: Set[str] = field(default_factory=set)
    
    def update_access(self) -> None:
        """更新访问信息"""
        self.accessed_at = datetime.now()
        self.access_count += 1
    
    def age(self) -> float:
        """获取缓存项年龄（秒）"""
        return (datetime.now() - self.created_at).total_seconds()
    
    def idle_time(self) -> float:
        """获取空闲时间（秒）"""
        return (datetime.now() - self.accessed_at).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "key": self.key,
            "created_at": self.created_at.isoformat(),
            "accessed_at": self.accessed_at.isoformat(),
            "access_count": self.access_count,
            "size": self.size,
            "tags": list(self.tags),
            "metadata": self.metadata.to_dict() if self.metadata else None
        }

class FileCache:
    """文件缓存
    
    提供基于LRU策略的文件数据缓存。
    """
    
    def __init__(self, max_size: int = 1000, max_memory: int = 100 * 1024 * 1024,
                 ttl: int = 3600):
        """初始化文件缓存
        
        Args:
            max_size: 最大缓存项数量
            max_memory: 最大内存使用量（字节）
            ttl: 缓存生存时间（秒）
        """
        self.max_size = max_size
        self.max_memory = max_memory
        self.ttl = ttl
        
        # 缓存存储
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        
        # 统计信息
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._current_memory = 0
        
        logger.info("文件缓存初始化完成", 
                   max_size=max_size, max_memory=max_memory, ttl=ttl)
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存项
        
        Args:
            key: 缓存键
            
        Returns:
            缓存的数据，如果不存在则返回None
        """
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._misses += 1
                logger.debug("缓存未命中", key=key)
                return None
            
            # 检查TTL
            if entry.age() > self.ttl:
                self._remove_entry(key)
                self._misses += 1
                logger.debug("缓存过期", key=key, age=entry.age())
                return None
            
            # 更新访问信息并移到末尾（LRU）
            entry.update_access()
            self._cache.move_to_end(key)
            
            self._hits += 1
            logger.debug("缓存命中", key=key, access_count=entry.access_count)
            
            return entry.data
    
    def put(self, key: str, data: Any, metadata: Optional[FileMetadata] = None,
            tags: Optional[Set[str]] = None, size: Optional[int] = None) -> bool:
        """添加缓存项
        
        Args:
            key: 缓存键
            data: 缓存数据
            metadata: 文件元数据
            tags: 标签集合
            size: 数据大小（字节），如果不提供则自动计算
            
        Returns:
            是否成功添加
        """
        if size is None:
            size = self._calculate_size(data)
        
        # 检查单个项是否超过内存限制
        if size > self.max_memory:
            logger.warning("缓存项过大", key=key, size=size, max_memory=self.max_memory)
            return False
        
        with self._lock:
            now = datetime.now()
            
            # 如果键已存在，先删除旧的
            if key in self._cache:
                self._remove_entry(key)
            
            # 创建缓存项
            entry = CacheEntry(
                key=key,
                data=data,
                metadata=metadata,
                created_at=now,
                accessed_at=now,
                size=size,
                tags=tags or set()
            )
            
            # 确保有足够的空间
            self._make_space_for(size)
            
            # 添加到缓存
            self._cache[key] = entry
            self._current_memory += size
            
            logger.debug("缓存项已添加", key=key, size=size, 
                        total_items=len(self._cache), total_memory=self._current_memory)
            
            return True
    
    def remove(self, key: str) -> bool:
        """删除缓存项
        
        Args:
            key: 缓存键
            
        Returns:
            是否成功删除
        """
        with self._lock:
            return self._remove_entry(key)
    
    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._current_memory = 0
            logger.info("缓存已清空")
    
    def cleanup(self) -> int:
        """清理过期缓存项
        
        Returns:
            清理的项数
        """
        with self._lock:
            keys_to_remove = []
            now = datetime.now()
            
            for key, entry in self._cache.items():
                if entry.age() > self.ttl:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                self._remove_entry(key)
            
            if keys_to_remove:
                logger.info("缓存清理完成", cleaned_count=len(keys_to_remove))
            
            return len(keys_to_remove)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息
        
        Returns:
            统计信息字典
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0
            
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "memory_usage": self._current_memory,
                "max_memory": self.max_memory,
                "memory_usage_percent": (self._current_memory / self.max_memory * 100) if self.max_memory > 0 else 0,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
                "evictions": self._evictions,
                "ttl": self.ttl
            }
    
    def get_entries(self) -> List[Dict[str, Any]]:
        """获取所有缓存项信息
        
        Returns:
            缓存项信息列表
        """
        with self._lock:
            return [entry.to_dict() for entry in self._cache.values()]
    
    def find_by_tag(self, tag: str) -> List[str]:
        """根据标签查找缓存项
        
        Args:
            tag: 标签
            
        Returns:
            匹配的缓存键列表
        """
        with self._lock:
            return [key for key, entry in self._cache.items() if tag in entry.tags]
    
    def _remove_entry(self, key: str) -> bool:
        """删除缓存项（内部方法）
        
        Args:
            key: 缓存键
            
        Returns:
            是否成功删除
        """
        entry = self._cache.pop(key, None)
        if entry:
            self._current_memory -= entry.size
            logger.debug("缓存项已删除", key=key, size=entry.size)
            return True
        return False
    
    def _make_space_for(self, size: int) -> None:
        """为新项腾出空间
        
        Args:
            size: 需要的空间大小
        """
        # 检查是否需要清理空间
        while (len(self._cache) >= self.max_size or 
               self._current_memory + size > self.max_memory):
            
            if not self._cache:
                break
            
            # 删除最旧的项（LRU策略）
            oldest_key = next(iter(self._cache))
            self._remove_entry(oldest_key)
            self._evictions += 1
            
            logger.debug("缓存项被驱逐", key=oldest_key)
    
    def _calculate_size(self, data: Any) -> int:
        """计算数据大小
        
        Args:
            data: 数据
            
        Returns:
            数据大小（字节）
        """
        try:
            if isinstance(data, (str, bytes)):
                return len(data)
            elif isinstance(data, (int, float)):
                return 8
            else:
                # 使用pickle序列化来估算大小
                return len(pickle.dumps(data))
        except Exception:
            # 如果无法计算，返回默认大小
            return 1024

class FileCacheManager:
    """文件缓存管理器
    
    提供多级缓存、智能预加载和缓存策略管理。
    """
    
    def __init__(self, cache_dir: Optional[Union[str, Path]] = None,
                 memory_cache_size: int = 1000, 
                 memory_cache_memory: int = 100 * 1024 * 1024,
                 disk_cache_size: int = 10000,
                 enable_preload: bool = True):
        """初始化缓存管理器
        
        Args:
            cache_dir: 磁盘缓存目录
            memory_cache_size: 内存缓存最大项数
            memory_cache_memory: 内存缓存最大内存使用量
            disk_cache_size: 磁盘缓存最大项数
            enable_preload: 是否启用预加载
        """
        self.cache_dir = Path(cache_dir) if cache_dir else Path.cwd() / ".cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 内存缓存
        self.memory_cache = FileCache(
            max_size=memory_cache_size,
            max_memory=memory_cache_memory
        )
        
        # 磁盘缓存索引
        self.disk_cache_size = disk_cache_size
        self._disk_index: Dict[str, Dict[str, Any]] = {}
        self._disk_index_file = self.cache_dir / "index.json"
        self._load_disk_index()
        
        # 预加载相关
        self.enable_preload = enable_preload
        self._preload_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="cache-preload")
        self._preload_futures: Dict[str, Future] = {}
        
        # 访问模式分析
        self._access_patterns: Dict[str, List[datetime]] = {}
        self._pattern_lock = threading.RLock()
        
        # 清理线程
        self._cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self._stop_cleanup = threading.Event()
        self._cleanup_thread.start()
        
        logger.info("文件缓存管理器初始化完成", 
                   cache_dir=str(self.cache_dir),
                   memory_cache_size=memory_cache_size,
                   disk_cache_size=disk_cache_size,
                   enable_preload=enable_preload)
    
    def get(self, key: str, loader: Optional[Callable[[], Any]] = None) -> Optional[Any]:
        """获取缓存数据
        
        Args:
            key: 缓存键
            loader: 数据加载函数（缓存未命中时使用）
            
        Returns:
            缓存的数据
        """
        # 记录访问模式
        self._record_access(key)
        
        # 首先尝试内存缓存
        data = self.memory_cache.get(key)
        if data is not None:
            logger.debug("内存缓存命中", key=key)
            self._trigger_preload(key)
            return data
        
        # 尝试磁盘缓存
        data = self._get_from_disk(key)
        if data is not None:
            # 将数据提升到内存缓存
            self.memory_cache.put(key, data)
            logger.debug("磁盘缓存命中并提升到内存", key=key)
            self._trigger_preload(key)
            return data
        
        # 如果提供了加载函数，使用它加载数据
        if loader:
            try:
                data = loader()
                if data is not None:
                    self.put(key, data)
                    logger.debug("数据加载并缓存", key=key)
                    return data
            except Exception as e:
                logger.error("数据加载失败", key=key, error=str(e))
        
        logger.debug("缓存完全未命中", key=key)
        return None
    
    def put(self, key: str, data: Any, metadata: Optional[FileMetadata] = None,
            tags: Optional[Set[str]] = None, persistent: bool = True) -> bool:
        """缓存数据
        
        Args:
            key: 缓存键
            data: 缓存数据
            metadata: 文件元数据
            tags: 标签集合
            persistent: 是否持久化到磁盘
            
        Returns:
            是否成功缓存
        """
        # 添加到内存缓存
        success = self.memory_cache.put(key, data, metadata, tags)
        
        # 如果需要，持久化到磁盘
        if success and persistent:
            self._put_to_disk(key, data, metadata, tags)
        
        if success:
            logger.debug("数据已缓存", key=key, persistent=persistent)
        
        return success
    
    def remove(self, key: str) -> bool:
        """删除缓存项
        
        Args:
            key: 缓存键
            
        Returns:
            是否成功删除
        """
        # 从内存缓存删除
        memory_removed = self.memory_cache.remove(key)
        
        # 从磁盘缓存删除
        disk_removed = self._remove_from_disk(key)
        
        # 清理访问模式记录
        with self._pattern_lock:
            self._access_patterns.pop(key, None)
        
        logger.debug("缓存项已删除", key=key, 
                    memory_removed=memory_removed, disk_removed=disk_removed)
        
        return memory_removed or disk_removed
    
    def clear(self) -> None:
        """清空所有缓存"""
        self.memory_cache.clear()
        self._clear_disk_cache()
        
        with self._pattern_lock:
            self._access_patterns.clear()
        
        logger.info("所有缓存已清空")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息
        
        Returns:
            统计信息字典
        """
        memory_stats = self.memory_cache.get_stats()
        
        return {
            "memory_cache": memory_stats,
            "disk_cache": {
                "size": len(self._disk_index),
                "max_size": self.disk_cache_size,
                "cache_dir": str(self.cache_dir)
            },
            "preload": {
                "enabled": self.enable_preload,
                "active_tasks": len(self._preload_futures)
            },
            "access_patterns": len(self._access_patterns)
        }
    
    def _get_from_disk(self, key: str) -> Optional[Any]:
        """从磁盘获取缓存数据
        
        Args:
            key: 缓存键
            
        Returns:
            缓存的数据
        """
        if key not in self._disk_index:
            return None
        
        entry_info = self._disk_index[key]
        cache_file = self.cache_dir / entry_info["filename"]
        
        try:
            if cache_file.exists():
                # 检查TTL
                created_at = datetime.fromisoformat(entry_info["created_at"])
                if (datetime.now() - created_at).total_seconds() > 3600:  # 1小时TTL
                    self._remove_from_disk(key)
                    return None
                
                with open(cache_file, 'rb') as f:
                    data = pickle.load(f)
                
                # 更新访问时间
                entry_info["accessed_at"] = datetime.now().isoformat()
                entry_info["access_count"] = entry_info.get("access_count", 0) + 1
                self._save_disk_index()
                
                return data
            else:
                # 文件不存在，清理索引
                del self._disk_index[key]
                self._save_disk_index()
                return None
                
        except Exception as e:
            logger.error("从磁盘读取缓存失败", key=key, error=str(e))
            self._remove_from_disk(key)
            return None
    
    def _put_to_disk(self, key: str, data: Any, metadata: Optional[FileMetadata] = None,
                    tags: Optional[Set[str]] = None) -> bool:
        """将数据保存到磁盘
        
        Args:
            key: 缓存键
            data: 缓存数据
            metadata: 文件元数据
            tags: 标签集合
            
        Returns:
            是否成功保存
        """
        try:
            # 生成文件名
            key_hash = hashlib.md5(key.encode()).hexdigest()
            filename = f"{key_hash}.cache"
            cache_file = self.cache_dir / filename
            
            # 保存数据
            with open(cache_file, 'wb') as f:
                pickle.dump(data, f)
            
            # 更新索引
            now = datetime.now()
            self._disk_index[key] = {
                "filename": filename,
                "created_at": now.isoformat(),
                "accessed_at": now.isoformat(),
                "access_count": 1,
                "size": cache_file.stat().st_size,
                "tags": list(tags) if tags else [],
                "metadata": metadata.to_dict() if metadata else None
            }
            
            # 确保不超过磁盘缓存大小限制
            self._enforce_disk_cache_limit()
            
            # 保存索引
            self._save_disk_index()
            
            return True
            
        except Exception as e:
            logger.error("保存到磁盘缓存失败", key=key, error=str(e))
            return False
    
    def _remove_from_disk(self, key: str) -> bool:
        """从磁盘删除缓存项
        
        Args:
            key: 缓存键
            
        Returns:
            是否成功删除
        """
        if key not in self._disk_index:
            return False
        
        try:
            entry_info = self._disk_index[key]
            cache_file = self.cache_dir / entry_info["filename"]
            
            if cache_file.exists():
                cache_file.unlink()
            
            del self._disk_index[key]
            self._save_disk_index()
            
            return True
            
        except Exception as e:
            logger.error("从磁盘删除缓存失败", key=key, error=str(e))
            return False
    
    def _clear_disk_cache(self) -> None:
        """清空磁盘缓存"""
        try:
            for entry_info in self._disk_index.values():
                cache_file = self.cache_dir / entry_info["filename"]
                if cache_file.exists():
                    cache_file.unlink()
            
            self._disk_index.clear()
            self._save_disk_index()
            
        except Exception as e:
            logger.error("清空磁盘缓存失败", error=str(e))
    
    def _load_disk_index(self) -> None:
        """加载磁盘缓存索引"""
        try:
            if self._disk_index_file.exists():
                with open(self._disk_index_file, 'r', encoding='utf-8') as f:
                    self._disk_index = json.load(f)
        except Exception as e:
            logger.error("加载磁盘缓存索引失败", error=str(e))
            self._disk_index = {}
    
    def _save_disk_index(self) -> None:
        """保存磁盘缓存索引"""
        try:
            with open(self._disk_index_file, 'w', encoding='utf-8') as f:
                json.dump(self._disk_index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("保存磁盘缓存索引失败", error=str(e))
    
    def _enforce_disk_cache_limit(self) -> None:
        """强制执行磁盘缓存大小限制"""
        if len(self._disk_index) <= self.disk_cache_size:
            return
        
        # 按访问时间排序，删除最旧的项
        sorted_items = sorted(
            self._disk_index.items(),
            key=lambda x: x[1]["accessed_at"]
        )
        
        items_to_remove = len(self._disk_index) - self.disk_cache_size
        for i in range(items_to_remove):
            key = sorted_items[i][0]
            self._remove_from_disk(key)
    
    def _record_access(self, key: str) -> None:
        """记录访问模式
        
        Args:
            key: 缓存键
        """
        with self._pattern_lock:
            if key not in self._access_patterns:
                self._access_patterns[key] = []
            
            # 记录访问时间，只保留最近50次访问
            self._access_patterns[key].append(datetime.now())
            if len(self._access_patterns[key]) > 50:
                self._access_patterns[key] = self._access_patterns[key][-50:]
    
    def _trigger_preload(self, key: str) -> None:
        """触发相关数据预加载
        
        Args:
            key: 当前访问的缓存键
        """
        if not self.enable_preload:
            return
        
        # 基于访问模式预测可能需要的数据
        related_keys = self._predict_related_keys(key)
        
        for related_key in related_keys:
            if (related_key not in self._preload_futures and 
                self.memory_cache.get(related_key) is None):
                
                # 启动预加载任务
                future = self._preload_executor.submit(self._preload_data, related_key)
                self._preload_futures[related_key] = future
    
    def _predict_related_keys(self, key: str) -> List[str]:
        """预测相关的缓存键
        
        Args:
            key: 当前缓存键
            
        Returns:
            相关缓存键列表
        """
        # 简单的相关性预测：基于键名相似性
        related_keys = []
        
        for cached_key in list(self._access_patterns.keys()):
            if cached_key != key and self._keys_related(key, cached_key):
                related_keys.append(cached_key)
        
        return related_keys[:3]  # 最多预加载3个相关项
    
    def _keys_related(self, key1: str, key2: str) -> bool:
        """判断两个键是否相关
        
        Args:
            key1: 第一个键
            key2: 第二个键
            
        Returns:
            是否相关
        """
        # 简单的相关性判断：共享前缀或后缀
        common_parts = set(key1.split('_')) & set(key2.split('_'))
        return len(common_parts) > 0
    
    def _preload_data(self, key: str) -> None:
        """预加载数据
        
        Args:
            key: 缓存键
        """
        try:
            # 尝试从磁盘加载到内存
            data = self._get_from_disk(key)
            if data is not None:
                self.memory_cache.put(key, data)
                logger.debug("预加载成功", key=key)
        except Exception as e:
            logger.debug("预加载失败", key=key, error=str(e))
        finally:
            # 清理完成的预加载任务
            self._preload_futures.pop(key, None)
    
    def _cleanup_worker(self) -> None:
        """清理工作线程"""
        while not self._stop_cleanup.wait(300):  # 每5分钟清理一次
            try:
                # 清理内存缓存
                cleaned = self.memory_cache.cleanup()
                
                # 清理磁盘缓存
                disk_cleaned = self._cleanup_disk_cache()
                
                if cleaned > 0 or disk_cleaned > 0:
                    logger.info("缓存清理完成", 
                               memory_cleaned=cleaned, disk_cleaned=disk_cleaned)
                
            except Exception as e:
                logger.error("缓存清理时发生错误", error=str(e))
    
    def _cleanup_disk_cache(self) -> int:
        """清理过期的磁盘缓存
        
        Returns:
            清理的项数
        """
        keys_to_remove = []
        now = datetime.now()
        
        for key, entry_info in self._disk_index.items():
            try:
                created_at = datetime.fromisoformat(entry_info["created_at"])
                if (now - created_at).total_seconds() > 3600:  # 1小时TTL
                    keys_to_remove.append(key)
            except Exception:
                # 如果日期解析失败，也删除这个项
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            self._remove_from_disk(key)
        
        return len(keys_to_remove)
    
    def stop(self) -> None:
        """停止缓存管理器"""
        # 停止清理线程
        self._stop_cleanup.set()
        if self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5)
        
        # 关闭预加载线程池
        self._preload_executor.shutdown(wait=True)
        
        # 保存索引
        self._save_disk_index()
        
        logger.info("文件缓存管理器已停止")
    
    def __del__(self):
        """析构函数，确保资源清理"""
        try:
            self.stop()
        except Exception:
            pass