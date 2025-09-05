"""
文件缓存系统测试
"""

import json
import pickle
import tempfile
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import pytest

from gemini_kling_mcp.file_manager.cache import (
    CacheEntry, FileCache, FileCacheManager
)
from gemini_kling_mcp.file_manager.core import FileMetadata


class TestCacheEntry:
    """缓存条目测试"""
    
    @pytest.fixture
    def sample_metadata(self):
        """创建示例文件元数据"""
        return FileMetadata(
            path=Path("/tmp/test.txt"),
            size=1024,
            created_at=datetime.now(),
            modified_at=datetime.now(),
            mime_type="text/plain",
            extension=".txt",
            checksum="abc123"
        )
    
    def test_cache_entry_creation(self, sample_metadata):
        """测试缓存条目创建"""
        now = datetime.now()
        entry = CacheEntry(
            key="test_key",
            data="test_data",
            metadata=sample_metadata,
            created_at=now,
            accessed_at=now,
            size=1024
        )
        
        assert entry.key == "test_key"
        assert entry.data == "test_data"
        assert entry.metadata == sample_metadata
        assert entry.size == 1024
        assert entry.access_count == 0
    
    def test_update_access(self, sample_metadata):
        """测试更新访问信息"""
        entry = CacheEntry(
            key="test_key",
            data="test_data",
            metadata=sample_metadata,
            created_at=datetime.now(),
            accessed_at=datetime.now(),
            size=1024
        )
        
        original_access_time = entry.accessed_at
        original_count = entry.access_count
        
        # 等待一点时间确保时间戳不同
        time.sleep(0.01)
        entry.update_access()
        
        assert entry.accessed_at > original_access_time
        assert entry.access_count == original_count + 1
    
    def test_age_calculation(self, sample_metadata):
        """测试年龄计算"""
        old_time = datetime.now() - timedelta(seconds=10)
        entry = CacheEntry(
            key="test_key",
            data="test_data",
            metadata=sample_metadata,
            created_at=old_time,
            accessed_at=old_time,
            size=1024
        )
        
        age = entry.age()
        assert age >= 10  # 至少10秒
        assert age < 11   # 不应该超过11秒
    
    def test_idle_time_calculation(self, sample_metadata):
        """测试空闲时间计算"""
        now = datetime.now()
        idle_time_start = now - timedelta(seconds=5)
        
        entry = CacheEntry(
            key="test_key",
            data="test_data",
            metadata=sample_metadata,
            created_at=now,
            accessed_at=idle_time_start,
            size=1024
        )
        
        idle_time = entry.idle_time()
        assert idle_time >= 5  # 至少5秒
        assert idle_time < 6   # 不应该超过6秒
    
    def test_to_dict(self, sample_metadata):
        """测试转换为字典"""
        now = datetime.now()
        entry = CacheEntry(
            key="test_key",
            data="test_data",
            metadata=sample_metadata,
            created_at=now,
            accessed_at=now,
            size=1024,
            tags={"tag1", "tag2"}
        )
        
        result = entry.to_dict()
        
        assert result["key"] == "test_key"
        assert result["size"] == 1024
        assert set(result["tags"]) == {"tag1", "tag2"}
        assert "created_at" in result
        assert "accessed_at" in result
        assert result["access_count"] == 0
        assert result["metadata"] is not None


class TestFileCache:
    """文件缓存测试"""
    
    @pytest.fixture
    def cache(self):
        """创建文件缓存实例"""
        return FileCache(max_size=10, max_memory=1024*1024, ttl=3600)
    
    @pytest.fixture
    def sample_metadata(self):
        """创建示例文件元数据"""
        return FileMetadata(
            path=Path("/tmp/test.txt"),
            size=1024,
            created_at=datetime.now(),
            modified_at=datetime.now(),
            mime_type="text/plain",
            extension=".txt",
            checksum="abc123"
        )
    
    def test_cache_initialization(self):
        """测试缓存初始化"""
        cache = FileCache(max_size=5, max_memory=2048, ttl=1800)
        
        assert cache.max_size == 5
        assert cache.max_memory == 2048
        assert cache.ttl == 1800
        assert len(cache._cache) == 0
        assert cache._hits == 0
        assert cache._misses == 0
        assert cache._current_memory == 0
    
    def test_put_and_get_success(self, cache, sample_metadata):
        """测试缓存存取成功"""
        key = "test_key"
        data = "test_data"
        
        # 放入缓存
        result = cache.put(key, data, sample_metadata)
        assert result is True
        
        # 从缓存获取
        retrieved_data = cache.get(key)
        assert retrieved_data == data
        
        # 检查统计信息
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 0
    
    def test_get_nonexistent_key(self, cache):
        """测试获取不存在的键"""
        result = cache.get("nonexistent_key")
        
        assert result is None
        
        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 1
    
    def test_put_large_item_rejection(self, cache):
        """测试拒绝过大的缓存项"""
        key = "large_key"
        data = "x" * (cache.max_memory + 1)  # 超过内存限制
        
        result = cache.put(key, data)
        assert result is False
        
        # 应该没有被缓存
        retrieved = cache.get(key)
        assert retrieved is None
    
    def test_ttl_expiration(self, sample_metadata):
        """测试TTL过期"""
        cache = FileCache(max_size=10, max_memory=1024*1024, ttl=1)  # 1秒TTL
        
        key = "test_key"
        data = "test_data"
        
        # 放入缓存
        cache.put(key, data, sample_metadata)
        
        # 立即获取应该成功
        result = cache.get(key)
        assert result == data
        
        # 等待过期
        time.sleep(1.1)
        
        # 现在应该过期了
        result = cache.get(key)
        assert result is None
        
        # 应该从缓存中被移除
        assert key not in cache._cache
    
    def test_lru_eviction(self, cache, sample_metadata):
        """测试LRU淘汰策略"""
        # 填满缓存
        for i in range(cache.max_size):
            cache.put(f"key_{i}", f"data_{i}", sample_metadata)
        
        # 访问第一个项使其成为最近使用的
        cache.get("key_0")
        
        # 添加一个新项，应该淘汰最久未使用的项
        cache.put("new_key", "new_data", sample_metadata)
        
        # key_0应该还在（因为最近访问过）
        assert cache.get("key_0") is not None
        
        # key_1应该被淘汰了（最久未使用）
        assert cache.get("key_1") is None
        
        # 新项应该在
        assert cache.get("new_key") == "new_data"
    
    def test_memory_limit_eviction(self, sample_metadata):
        """测试内存限制淘汰"""
        cache = FileCache(max_size=100, max_memory=1000, ttl=3600)
        
        # 添加多个项直到接近内存限制
        for i in range(5):
            data = "x" * 150  # 每个项约150字节
            cache.put(f"key_{i}", data, sample_metadata, size=150)
        
        # 添加一个大项，应该触发内存淘汰
        large_data = "x" * 400
        cache.put("large_key", large_data, sample_metadata, size=400)
        
        # 应该有一些旧项被淘汰
        assert len(cache._cache) < 6
        assert cache.get("large_key") == large_data
    
    def test_remove_item(self, cache, sample_metadata):
        """测试移除缓存项"""
        key = "test_key"
        data = "test_data"
        
        # 添加项
        cache.put(key, data, sample_metadata)
        assert cache.get(key) == data
        
        # 移除项
        result = cache.remove(key)
        assert result is True
        
        # 应该不存在了
        assert cache.get(key) is None
        
        # 再次移除应该返回False
        result = cache.remove(key)
        assert result is False
    
    def test_clear_cache(self, cache, sample_metadata):
        """测试清空缓存"""
        # 添加多个项
        for i in range(5):
            cache.put(f"key_{i}", f"data_{i}", sample_metadata)
        
        assert len(cache._cache) == 5
        
        # 清空缓存
        cache.clear()
        
        assert len(cache._cache) == 0
        assert cache._current_memory == 0
        
        # 所有项都应该获取不到
        for i in range(5):
            assert cache.get(f"key_{i}") is None
    
    def test_cleanup_expired_items(self, sample_metadata):
        """测试清理过期项"""
        cache = FileCache(max_size=10, max_memory=1024*1024, ttl=1)
        
        # 添加项
        for i in range(3):
            cache.put(f"key_{i}", f"data_{i}", sample_metadata)
        
        # 修改一些项的创建时间使其过期
        old_time = datetime.now() - timedelta(seconds=2)
        cache._cache["key_0"].created_at = old_time
        cache._cache["key_1"].created_at = old_time
        
        # 清理过期项
        cleaned = cache.cleanup()
        
        assert cleaned == 2
        assert cache.get("key_0") is None
        assert cache.get("key_1") is None
        assert cache.get("key_2") is not None  # 应该还在
    
    def test_get_stats(self, cache, sample_metadata):
        """测试获取统计信息"""
        # 添加一些项
        cache.put("key1", "data1", sample_metadata, size=100)
        cache.put("key2", "data2", sample_metadata, size=200)
        
        # 一些访问
        cache.get("key1")  # 命中
        cache.get("key1")  # 命中
        cache.get("nonexistent")  # 未命中
        
        stats = cache.get_stats()
        
        assert stats["size"] == 2
        assert stats["max_size"] == cache.max_size
        assert stats["memory_usage"] == 300
        assert stats["max_memory"] == cache.max_memory
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 2/3
        assert stats["evictions"] == 0
        assert stats["ttl"] == cache.ttl
    
    def test_get_entries(self, cache, sample_metadata):
        """测试获取所有缓存条目"""
        # 添加一些项
        cache.put("key1", "data1", sample_metadata, tags={"tag1"})
        cache.put("key2", "data2", sample_metadata, tags={"tag2"})
        
        entries = cache.get_entries()
        
        assert len(entries) == 2
        assert all(isinstance(entry, dict) for entry in entries)
        assert any(entry["key"] == "key1" for entry in entries)
        assert any(entry["key"] == "key2" for entry in entries)
    
    def test_find_by_tag(self, cache, sample_metadata):
        """测试按标签查找"""
        # 添加带标签的项
        cache.put("key1", "data1", sample_metadata, tags={"important", "text"})
        cache.put("key2", "data2", sample_metadata, tags={"important", "image"})
        cache.put("key3", "data3", sample_metadata, tags={"text"})
        
        # 查找带有"important"标签的项
        important_keys = cache.find_by_tag("important")
        assert set(important_keys) == {"key1", "key2"}
        
        # 查找带有"text"标签的项
        text_keys = cache.find_by_tag("text")
        assert set(text_keys) == {"key1", "key3"}
        
        # 查找不存在的标签
        nonexistent_keys = cache.find_by_tag("nonexistent")
        assert nonexistent_keys == []
    
    def test_calculate_size_different_types(self, cache):
        """测试计算不同类型数据的大小"""
        # 字符串
        str_size = cache._calculate_size("hello")
        assert str_size == 5
        
        # 字节
        bytes_size = cache._calculate_size(b"hello")
        assert bytes_size == 5
        
        # 整数
        int_size = cache._calculate_size(42)
        assert int_size == 8
        
        # 浮点数
        float_size = cache._calculate_size(3.14)
        assert float_size == 8
        
        # 复杂对象（使用pickle）
        complex_obj = {"key": "value", "list": [1, 2, 3]}
        complex_size = cache._calculate_size(complex_obj)
        assert complex_size > 0
    
    def test_concurrent_access(self, cache, sample_metadata):
        """测试并发访问"""
        import concurrent.futures
        
        def worker(worker_id):
            results = []
            for i in range(10):
                key = f"worker_{worker_id}_key_{i}"
                data = f"worker_{worker_id}_data_{i}"
                
                # 放入缓存
                cache.put(key, data, sample_metadata)
                
                # 获取数据
                retrieved = cache.get(key)
                results.append(retrieved == data)
            
            return results
        
        # 并发执行
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(worker, i) for i in range(3)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # 所有操作都应该成功
        for worker_results in results:
            assert all(worker_results)


class TestFileCacheManager:
    """文件缓存管理器测试"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def cache_manager(self, temp_dir):
        """创建缓存管理器"""
        manager = FileCacheManager(
            cache_dir=temp_dir / "cache",
            memory_cache_size=10,
            memory_cache_memory=1024*1024,
            disk_cache_size=100,
            enable_preload=False  # 禁用预加载以简化测试
        )
        # 确保停止清理线程避免测试干扰
        manager._stop_cleanup.set()
        return manager
    
    @pytest.fixture
    def sample_metadata(self):
        """创建示例文件元数据"""
        return FileMetadata(
            path=Path("/tmp/test.txt"),
            size=1024,
            created_at=datetime.now(),
            modified_at=datetime.now(),
            mime_type="text/plain",
            extension=".txt",
            checksum="abc123"
        )
    
    def test_manager_initialization(self, temp_dir):
        """测试管理器初始化"""
        cache_dir = temp_dir / "test_cache"
        manager = FileCacheManager(cache_dir=cache_dir, enable_preload=False)
        
        try:
            assert manager.cache_dir == cache_dir
            assert cache_dir.exists()
            assert isinstance(manager.memory_cache, FileCache)
            assert isinstance(manager._disk_index, dict)
            assert manager._cleanup_thread.is_alive()
        finally:
            manager.stop()
    
    def test_put_and_get_memory_cache(self, cache_manager, sample_metadata):
        """测试内存缓存存取"""
        key = "test_key"
        data = "test_data"
        
        # 放入缓存
        result = cache_manager.put(key, data, sample_metadata, persistent=False)
        assert result is True
        
        # 从缓存获取
        retrieved = cache_manager.get(key)
        assert retrieved == data
    
    def test_put_and_get_with_disk_cache(self, cache_manager, sample_metadata):
        """测试磁盘缓存存取"""
        key = "disk_test_key"
        data = "disk_test_data"
        
        # 放入缓存（包括磁盘）
        result = cache_manager.put(key, data, sample_metadata, persistent=True)
        assert result is True
        
        # 清空内存缓存
        cache_manager.memory_cache.clear()
        
        # 应该能从磁盘缓存获取
        retrieved = cache_manager.get(key)
        assert retrieved == data
        
        # 现在应该也在内存缓存中
        memory_retrieved = cache_manager.memory_cache.get(key)
        assert memory_retrieved == data
    
    def test_get_with_loader(self, cache_manager):
        """测试使用加载器获取数据"""
        key = "loader_test_key"
        expected_data = "loaded_data"
        
        def data_loader():
            return expected_data
        
        # 首次获取应该调用加载器
        result = cache_manager.get(key, loader=data_loader)
        assert result == expected_data
        
        # 再次获取应该从缓存获取
        result2 = cache_manager.get(key)
        assert result2 == expected_data
    
    def test_get_with_failing_loader(self, cache_manager):
        """测试使用失败的加载器"""
        key = "failing_loader_key"
        
        def failing_loader():
            raise Exception("Loader failed")
        
        # 应该返回None而不是抛出异常
        result = cache_manager.get(key, loader=failing_loader)
        assert result is None
    
    def test_remove_from_both_caches(self, cache_manager, sample_metadata):
        """测试从内存和磁盘缓存中移除"""
        key = "remove_test_key"
        data = "remove_test_data"
        
        # 放入缓存
        cache_manager.put(key, data, sample_metadata, persistent=True)
        
        # 验证存在
        assert cache_manager.get(key) == data
        assert key in cache_manager._disk_index
        
        # 移除
        result = cache_manager.remove(key)
        assert result is True
        
        # 验证已移除
        assert cache_manager.get(key) is None
        assert key not in cache_manager._disk_index
    
    def test_clear_all_caches(self, cache_manager, sample_metadata):
        """测试清空所有缓存"""
        # 添加一些数据
        for i in range(3):
            cache_manager.put(f"key_{i}", f"data_{i}", sample_metadata, persistent=True)
        
        # 验证数据存在
        assert len(cache_manager._disk_index) == 3
        assert cache_manager.memory_cache.get_stats()["size"] == 3
        
        # 清空缓存
        cache_manager.clear()
        
        # 验证已清空
        assert len(cache_manager._disk_index) == 0
        assert cache_manager.memory_cache.get_stats()["size"] == 0
        
        # 验证数据不存在
        for i in range(3):
            assert cache_manager.get(f"key_{i}") is None
    
    def test_get_stats(self, cache_manager, sample_metadata):
        """测试获取统计信息"""
        # 添加一些数据
        cache_manager.put("key1", "data1", sample_metadata, persistent=True)
        cache_manager.put("key2", "data2", sample_metadata, persistent=False)
        
        stats = cache_manager.get_stats()
        
        assert "memory_cache" in stats
        assert "disk_cache" in stats
        assert "preload" in stats
        assert "access_patterns" in stats
        
        assert stats["memory_cache"]["size"] == 2
        assert stats["disk_cache"]["size"] == 1  # 只有一个持久化了
        assert stats["preload"]["enabled"] is False
    
    def test_disk_cache_operations(self, cache_manager, sample_metadata):
        """测试磁盘缓存操作"""
        key = "disk_key"
        data = "disk_data"
        
        # 直接测试磁盘缓存
        result = cache_manager._put_to_disk(key, data, sample_metadata)
        assert result is True
        assert key in cache_manager._disk_index
        
        # 从磁盘获取
        retrieved = cache_manager._get_from_disk(key)
        assert retrieved == data
        
        # 从磁盘移除
        removed = cache_manager._remove_from_disk(key)
        assert removed is True
        assert key not in cache_manager._disk_index
        
        # 再次获取应该返回None
        retrieved2 = cache_manager._get_from_disk(key)
        assert retrieved2 is None
    
    def test_disk_cache_ttl(self, cache_manager, sample_metadata):
        """测试磁盘缓存TTL"""
        key = "ttl_key"
        data = "ttl_data"
        
        # 放入磁盘缓存
        cache_manager._put_to_disk(key, data, sample_metadata)
        
        # 修改创建时间为很久以前
        old_time = datetime.now() - timedelta(hours=2)
        cache_manager._disk_index[key]["created_at"] = old_time.isoformat()
        
        # 尝试获取应该失败（过期）
        retrieved = cache_manager._get_from_disk(key)
        assert retrieved is None
        
        # 应该从索引中移除
        assert key not in cache_manager._disk_index
    
    def test_disk_cache_size_limit(self, cache_manager, sample_metadata):
        """测试磁盘缓存大小限制"""
        # 设置较小的磁盘缓存限制
        cache_manager.disk_cache_size = 3
        
        # 添加超过限制的项
        for i in range(5):
            cache_manager._put_to_disk(f"key_{i}", f"data_{i}", sample_metadata)
        
        # 强制执行大小限制
        cache_manager._enforce_disk_cache_limit()
        
        # 应该只保留最近的3个项
        assert len(cache_manager._disk_index) == 3
    
    def test_access_pattern_recording(self, cache_manager):
        """测试访问模式记录"""
        key = "pattern_key"
        
        # 记录多次访问
        for _ in range(3):
            cache_manager._record_access(key)
        
        # 检查记录
        assert key in cache_manager._access_patterns
        assert len(cache_manager._access_patterns[key]) == 3
        
        # 访问次数过多时应该限制记录数量
        for _ in range(60):  # 超过50次限制
            cache_manager._record_access(key)
        
        assert len(cache_manager._access_patterns[key]) == 50  # 应该被限制为50
    
    def test_disk_index_persistence(self, cache_manager, sample_metadata):
        """测试磁盘索引持久化"""
        key = "persist_key"
        data = "persist_data"
        
        # 放入磁盘缓存
        cache_manager._put_to_disk(key, data, sample_metadata)
        
        # 检查索引文件是否存在
        index_file = cache_manager.cache_dir / "index.json"
        assert index_file.exists()
        
        # 验证索引内容
        with open(index_file, 'r') as f:
            index_data = json.load(f)
        
        assert key in index_data
        assert "filename" in index_data[key]
        assert "created_at" in index_data[key]
    
    def test_disk_index_loading(self, temp_dir, sample_metadata):
        """测试磁盘索引加载"""
        cache_dir = temp_dir / "load_test_cache"
        cache_dir.mkdir()
        
        # 创建索引文件
        index_data = {
            "test_key": {
                "filename": "test_file.cache",
                "created_at": datetime.now().isoformat(),
                "accessed_at": datetime.now().isoformat(),
                "access_count": 1,
                "size": 100,
                "tags": [],
                "metadata": None
            }
        }
        
        index_file = cache_dir / "index.json"
        with open(index_file, 'w') as f:
            json.dump(index_data, f)
        
        # 创建缓存管理器，应该加载索引
        manager = FileCacheManager(cache_dir=cache_dir, enable_preload=False)
        
        try:
            assert "test_key" in manager._disk_index
            assert manager._disk_index["test_key"]["filename"] == "test_file.cache"
        finally:
            manager.stop()
    
    def test_keys_relationship_detection(self, cache_manager):
        """测试键关系检测"""
        # 相关的键（共享部分）
        assert cache_manager._keys_related("user_123_profile", "user_123_settings") is True
        assert cache_manager._keys_related("image_large", "image_thumbnail") is True
        
        # 不相关的键
        assert cache_manager._keys_related("user_profile", "system_config") is False
        assert cache_manager._keys_related("abc", "xyz") is False
    
    def test_cleanup_worker(self, temp_dir, sample_metadata):
        """测试清理工作线程"""
        # 创建短间隔的管理器用于测试
        manager = FileCacheManager(cache_dir=temp_dir / "cleanup_test", enable_preload=False)
        
        try:
            # 添加一些过期数据
            manager.put("test_key", "test_data", sample_metadata, persistent=True)
            
            # 修改时间使其过期
            old_time = datetime.now() - timedelta(hours=2)
            manager.memory_cache._cache["test_key"].created_at = old_time
            manager._disk_index["test_key"]["created_at"] = old_time.isoformat()
            
            # 手动触发清理
            memory_cleaned = manager.memory_cache.cleanup()
            disk_cleaned = manager._cleanup_disk_cache()
            
            assert memory_cleaned > 0 or disk_cleaned > 0
            
        finally:
            manager.stop()
    
    def test_stop_manager(self, cache_manager):
        """测试停止管理器"""
        # 检查线程是否运行
        assert cache_manager._cleanup_thread.is_alive()
        
        # 停止管理器
        cache_manager.stop()
        
        # 等待线程结束
        time.sleep(0.1)
        
        # 检查线程是否停止
        assert not cache_manager._cleanup_thread.is_alive()
        
        # 索引文件应该被保存
        assert cache_manager._disk_index_file.exists()
    
    @pytest.mark.slow
    def test_large_scale_operations(self, cache_manager, sample_metadata):
        """测试大规模操作"""
        # 添加大量数据
        num_items = 1000
        
        for i in range(num_items):
            key = f"large_scale_key_{i}"
            data = f"large_scale_data_{i}" * 10  # 稍大的数据
            cache_manager.put(key, data, sample_metadata, persistent=(i % 10 == 0))  # 每10个持久化1个
        
        # 验证内存缓存有数据（受限于max_size）
        memory_stats = cache_manager.memory_cache.get_stats()
        assert memory_stats["size"] <= cache_manager.memory_cache.max_size
        
        # 验证磁盘缓存有数据
        assert len(cache_manager._disk_index) == num_items // 10
        
        # 随机访问一些数据
        import random
        for _ in range(100):
            key = f"large_scale_key_{random.randint(0, num_items-1)}"
            data = cache_manager.get(key)
            # 数据要么存在要么不存在，但不应该出错
            assert data is None or isinstance(data, str)
    
    def test_concurrent_cache_operations(self, cache_manager, sample_metadata):
        """测试并发缓存操作"""
        import concurrent.futures
        
        def worker(worker_id):
            success_count = 0
            
            for i in range(10):
                key = f"concurrent_{worker_id}_{i}"
                data = f"data_{worker_id}_{i}"
                
                # 放入缓存
                if cache_manager.put(key, data, sample_metadata):
                    # 立即获取
                    retrieved = cache_manager.get(key)
                    if retrieved == data:
                        success_count += 1
            
            return success_count
        
        # 并发执行
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker, i) for i in range(5)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # 大部分操作应该成功（考虑到缓存大小限制）
        total_success = sum(results)
        assert total_success > 0