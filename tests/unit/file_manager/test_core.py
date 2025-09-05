"""
文件管理器核心功能测试
"""

import os
import tempfile
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from gemini_kling_mcp.file_manager.core import FileManager, TempFileManager, FileMetadata


class TestFileMetadata:
    """文件元数据测试"""
    
    def test_file_metadata_creation(self):
        """测试文件元数据创建"""
        path = Path("/tmp/test.txt")
        size = 1024
        created_at = datetime.now()
        modified_at = created_at
        mime_type = "text/plain"
        extension = ".txt"
        checksum = "abc123"
        
        metadata = FileMetadata(
            path=path,
            size=size,
            created_at=created_at,
            modified_at=modified_at,
            mime_type=mime_type,
            extension=extension,
            checksum=checksum
        )
        
        assert metadata.path == path
        assert metadata.size == size
        assert metadata.mime_type == mime_type
        assert metadata.extension == extension
        assert metadata.checksum == checksum
    
    def test_file_metadata_to_dict(self):
        """测试文件元数据转换为字典"""
        path = Path("/tmp/test.txt")
        created_at = datetime.now()
        
        metadata = FileMetadata(
            path=path,
            size=1024,
            created_at=created_at,
            modified_at=created_at,
            mime_type="text/plain",
            extension=".txt",
            checksum="abc123"
        )
        
        result = metadata.to_dict()
        
        assert result["path"] == str(path)
        assert result["size"] == 1024
        assert result["mime_type"] == "text/plain"
        assert result["extension"] == ".txt"
        assert result["checksum"] == "abc123"
        assert "created_at" in result
        assert "modified_at" in result


class TestFileManager:
    """文件管理器测试"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def file_manager(self, temp_dir):
        """创建文件管理器实例"""
        with patch('gemini_kling_mcp.file_manager.core.get_config') as mock_config:
            mock_config.return_value.file.temp_dir = str(temp_dir)
            mock_config.return_value.file.max_file_size = 1024 * 1024
            mock_config.return_value.file.allowed_formats = ["txt", "jpg"]
            return FileManager(base_dir=temp_dir)
    
    @pytest.fixture
    def test_file(self, temp_dir):
        """创建测试文件"""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello, World!")
        return test_file
    
    def test_file_manager_initialization(self, temp_dir):
        """测试文件管理器初始化"""
        with patch('gemini_kling_mcp.file_manager.core.get_config') as mock_config:
            mock_config.return_value.file.temp_dir = str(temp_dir)
            mock_config.return_value.file.max_file_size = 1024 * 1024
            mock_config.return_value.file.allowed_formats = ["txt", "jpg"]
            
            manager = FileManager(base_dir=temp_dir)
            
            assert manager.base_dir == temp_dir
            assert manager.base_dir.exists()
            assert isinstance(manager.max_file_size, int)
            assert isinstance(manager.allowed_formats, set)
    
    def test_file_manager_default_config(self):
        """测试文件管理器使用默认配置"""
        with patch('gemini_kling_mcp.file_manager.core.get_config') as mock_config:
            mock_config.return_value.file.temp_dir = "/tmp/test"
            mock_config.return_value.file.max_file_size = 1024 * 1024
            mock_config.return_value.file.allowed_formats = ["txt", "jpg"]
            
            manager = FileManager()
            
            assert str(manager.base_dir).endswith("test")
            assert manager.max_file_size == 1024 * 1024
            assert "txt" in manager.allowed_formats
            assert "jpg" in manager.allowed_formats
    
    def test_get_file_metadata(self, file_manager, test_file):
        """测试获取文件元数据"""
        with patch('gemini_kling_mcp.file_manager.core.magic') as mock_magic:
            mock_magic.from_file.return_value = "text/plain"
            
            metadata = file_manager.get_file_metadata(test_file)
            
            assert metadata.path == test_file.resolve()
            assert metadata.size == test_file.stat().st_size
            assert metadata.mime_type == "text/plain"
            assert metadata.extension == ".txt"
            assert metadata.checksum  # 应该有校验和
    
    def test_get_file_metadata_nonexistent_file(self, file_manager, temp_dir):
        """测试获取不存在文件的元数据"""
        nonexistent_file = temp_dir / "nonexistent.txt"
        
        with pytest.raises(FileNotFoundError):
            file_manager.get_file_metadata(nonexistent_file)
    
    def test_calculate_checksum(self, file_manager, test_file):
        """测试计算文件校验和"""
        checksum1 = file_manager._calculate_checksum(test_file)
        checksum2 = file_manager._calculate_checksum(test_file)
        
        assert checksum1 == checksum2  # 同样的文件应该有同样的校验和
        assert len(checksum1) == 64  # SHA256哈希长度
        assert isinstance(checksum1, str)
    
    def test_validate_file_success(self, file_manager, test_file):
        """测试文件验证成功"""
        result = file_manager.validate_file(test_file)
        assert result is True
    
    def test_validate_file_not_exists(self, file_manager, temp_dir):
        """测试验证不存在的文件"""
        nonexistent_file = temp_dir / "nonexistent.txt"
        result = file_manager.validate_file(nonexistent_file)
        assert result is False
    
    def test_validate_file_too_large(self, file_manager, temp_dir):
        """测试验证过大的文件"""
        large_file = temp_dir / "large.txt"
        large_file.write_text("x" * (file_manager.max_file_size + 1))
        
        result = file_manager.validate_file(large_file)
        assert result is False
    
    def test_validate_file_unsupported_format(self, file_manager, temp_dir):
        """测试验证不支持的文件格式"""
        # 假设.xyz不在允许的格式中
        if "xyz" in file_manager.allowed_formats:
            file_manager.allowed_formats.remove("xyz")
        
        unsupported_file = temp_dir / "test.xyz"
        unsupported_file.write_text("test content")
        
        result = file_manager.validate_file(unsupported_file)
        assert result is False
    
    def test_copy_file_success(self, file_manager, test_file, temp_dir):
        """测试文件复制成功"""
        dest_file = temp_dir / "copy.txt"
        
        result = file_manager.copy_file(test_file, dest_file)
        
        assert result == dest_file.resolve()
        assert dest_file.exists()
        assert dest_file.read_text() == test_file.read_text()
    
    def test_copy_file_overwrite(self, file_manager, test_file, temp_dir):
        """测试文件复制覆盖"""
        dest_file = temp_dir / "copy.txt"
        dest_file.write_text("existing content")
        
        # 不允许覆盖时应该失败
        with pytest.raises(FileExistsError):
            file_manager.copy_file(test_file, dest_file, overwrite=False)
        
        # 允许覆盖时应该成功
        result = file_manager.copy_file(test_file, dest_file, overwrite=True)
        
        assert result == dest_file.resolve()
        assert dest_file.read_text() == test_file.read_text()
    
    def test_copy_file_source_not_exists(self, file_manager, temp_dir):
        """测试复制不存在的源文件"""
        nonexistent_source = temp_dir / "nonexistent.txt"
        dest_file = temp_dir / "dest.txt"
        
        with pytest.raises(FileNotFoundError):
            file_manager.copy_file(nonexistent_source, dest_file)
    
    def test_move_file_success(self, file_manager, test_file, temp_dir):
        """测试文件移动成功"""
        dest_file = temp_dir / "moved.txt"
        original_content = test_file.read_text()
        
        result = file_manager.move_file(test_file, dest_file)
        
        assert result == dest_file.resolve()
        assert dest_file.exists()
        assert not test_file.exists()  # 源文件应该不存在了
        assert dest_file.read_text() == original_content
    
    def test_delete_file_success(self, file_manager, test_file):
        """测试文件删除成功"""
        assert test_file.exists()
        
        result = file_manager.delete_file(test_file)
        
        assert result is True
        assert not test_file.exists()
    
    def test_delete_file_not_exists(self, file_manager, temp_dir):
        """测试删除不存在的文件"""
        nonexistent_file = temp_dir / "nonexistent.txt"
        
        result = file_manager.delete_file(nonexistent_file)
        assert result is False
    
    def test_delete_file_force(self, file_manager, temp_dir):
        """测试强制删除文件"""
        nonexistent_file = temp_dir / "nonexistent.txt"
        
        result = file_manager.delete_file(nonexistent_file, force=True)
        assert result is True  # 强制模式下应该返回True


class TestTempFileManager:
    """临时文件管理器测试"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def temp_file_manager(self, temp_dir):
        """创建临时文件管理器实例"""
        with patch('gemini_kling_mcp.file_manager.core.get_config') as mock_config:
            mock_config.return_value.file.temp_dir = str(temp_dir)
            mock_config.return_value.file.max_file_size = 1024 * 1024
            mock_config.return_value.file.allowed_formats = ["txt", "jpg"]
            return TempFileManager(base_dir=temp_dir, cleanup_interval=1)
    
    def test_temp_file_manager_initialization(self, temp_dir):
        """测试临时文件管理器初始化"""
        with patch('gemini_kling_mcp.file_manager.core.get_config') as mock_config:
            mock_config.return_value.file.temp_dir = str(temp_dir)
            mock_config.return_value.file.max_file_size = 1024 * 1024
            mock_config.return_value.file.allowed_formats = ["txt", "jpg"]
            
            manager = TempFileManager(base_dir=temp_dir, cleanup_interval=60)
            
            assert manager.base_dir == temp_dir
            assert manager.cleanup_interval == 60
            assert isinstance(manager._temp_files, dict)
            assert isinstance(manager._lock, threading.RLock)
            assert manager._cleanup_thread is not None
            
            # 清理
            manager.stop_cleanup()
    
    def test_create_temp_file_without_content(self, temp_file_manager):
        """测试创建无内容的临时文件"""
        temp_file = temp_file_manager.create_temp_file(suffix=".txt", prefix="test_")
        
        assert temp_file.exists()
        assert temp_file.name.startswith("test_")
        assert temp_file.name.endswith(".txt")
        assert str(temp_file) in temp_file_manager._temp_files
        
        # 清理
        temp_file_manager.stop_cleanup()
    
    def test_create_temp_file_with_content(self, temp_file_manager):
        """测试创建有内容的临时文件"""
        content = b"Hello, World!"
        temp_file = temp_file_manager.create_temp_file(
            suffix=".txt", 
            prefix="test_", 
            content=content
        )
        
        assert temp_file.exists()
        assert temp_file.read_bytes() == content
        assert str(temp_file) in temp_file_manager._temp_files
        
        # 清理
        temp_file_manager.stop_cleanup()
    
    def test_create_temp_dir(self, temp_file_manager):
        """测试创建临时目录"""
        temp_dir = temp_file_manager.create_temp_dir(prefix="test_dir_")
        
        assert temp_dir.exists()
        assert temp_dir.is_dir()
        assert temp_dir.name.startswith("test_dir_")
        
        # 清理
        temp_file_manager.stop_cleanup()
    
    def test_register_temp_file(self, temp_file_manager, temp_dir):
        """测试注册临时文件"""
        # 创建一个常规文件
        regular_file = temp_dir / "regular.txt"
        regular_file.write_text("test content")
        
        # 注册为临时文件
        temp_file_manager.register_temp_file(regular_file, lifetime=30)
        
        assert str(regular_file) in temp_file_manager._temp_files
        metadata = temp_file_manager._temp_files[str(regular_file)]
        assert "lifetime:30" in metadata.tags
        
        # 清理
        temp_file_manager.stop_cleanup()
    
    def test_register_nonexistent_file(self, temp_file_manager, temp_dir):
        """测试注册不存在的文件"""
        nonexistent_file = temp_dir / "nonexistent.txt"
        
        # 应该不会抛出异常，但也不会添加到记录中
        temp_file_manager.register_temp_file(nonexistent_file)
        
        assert str(nonexistent_file) not in temp_file_manager._temp_files
        
        # 清理
        temp_file_manager.stop_cleanup()
    
    def test_cleanup_temp_files_by_age(self, temp_file_manager):
        """测试按年龄清理临时文件"""
        # 创建临时文件
        temp_file1 = temp_file_manager.create_temp_file(content=b"file1")
        temp_file2 = temp_file_manager.create_temp_file(content=b"file2")
        
        # 修改其中一个文件的创建时间
        old_time = datetime.now() - timedelta(hours=2)
        temp_file_manager._temp_files[str(temp_file1)].created_at = old_time
        
        # 清理超过1小时的文件
        cleaned = temp_file_manager.cleanup_temp_files(max_age=3600)
        
        assert cleaned == 1
        assert not temp_file1.exists()
        assert temp_file2.exists()
        assert str(temp_file1) not in temp_file_manager._temp_files
        assert str(temp_file2) in temp_file_manager._temp_files
        
        # 清理
        temp_file_manager.stop_cleanup()
    
    def test_cleanup_temp_files_force(self, temp_file_manager):
        """测试强制清理所有临时文件"""
        # 创建多个临时文件
        temp_files = []
        for i in range(3):
            temp_file = temp_file_manager.create_temp_file(content=f"file{i}".encode())
            temp_files.append(temp_file)
        
        assert len(temp_file_manager._temp_files) == 3
        
        # 强制清理所有文件
        cleaned = temp_file_manager.cleanup_temp_files(force=True)
        
        assert cleaned == 3
        assert len(temp_file_manager._temp_files) == 0
        for temp_file in temp_files:
            assert not temp_file.exists()
        
        # 清理
        temp_file_manager.stop_cleanup()
    
    def test_cleanup_temp_files_custom_lifetime(self, temp_file_manager, temp_dir):
        """测试自定义生命周期清理"""
        # 创建文件并注册
        test_file = temp_dir / "test_lifetime.txt"
        test_file.write_text("test content")
        
        # 注册为临时文件，设置30秒生命周期
        temp_file_manager.register_temp_file(test_file, lifetime=30)
        
        # 修改创建时间为1分钟前
        old_time = datetime.now() - timedelta(minutes=1)
        temp_file_manager._temp_files[str(test_file)].created_at = old_time
        
        # 清理应该删除这个文件（超过了自定义生命周期）
        cleaned = temp_file_manager.cleanup_temp_files(max_age=3600)
        
        assert cleaned == 1
        assert not test_file.exists()
        assert str(test_file) not in temp_file_manager._temp_files
        
        # 清理
        temp_file_manager.stop_cleanup()
    
    def test_get_temp_files_info(self, temp_file_manager):
        """测试获取临时文件信息"""
        # 创建一些临时文件
        temp_file1 = temp_file_manager.create_temp_file(content=b"file1")
        temp_file2 = temp_file_manager.create_temp_file(content=b"file2")
        
        info = temp_file_manager.get_temp_files_info()
        
        assert len(info) == 2
        assert all(isinstance(item, dict) for item in info)
        assert all("path" in item for item in info)
        assert all("size" in item for item in info)
        
        # 清理
        temp_file_manager.stop_cleanup()
    
    def test_automatic_cleanup(self, temp_dir):
        """测试自动清理功能"""
        with patch('gemini_kling_mcp.file_manager.core.get_config') as mock_config:
            mock_config.return_value.file.temp_dir = str(temp_dir)
            mock_config.return_value.file.max_file_size = 1024 * 1024
            mock_config.return_value.file.allowed_formats = ["txt", "jpg"]
            
            # 创建一个清理间隔很短的管理器
            manager = TempFileManager(base_dir=temp_dir, cleanup_interval=1)
        
        try:
            # 创建一个临时文件
            temp_file = manager.create_temp_file(content=b"test")
            
            # 修改其创建时间为很久以前
            old_time = datetime.now() - timedelta(hours=2)
            manager._temp_files[str(temp_file)].created_at = old_time
            
            # 等待自动清理
            time.sleep(2)
            
            # 文件应该被自动清理了
            assert not temp_file.exists()
            assert str(temp_file) not in manager._temp_files
            
        finally:
            manager.stop_cleanup()
    
    def test_stop_cleanup(self, temp_file_manager):
        """测试停止清理线程"""
        assert temp_file_manager._cleanup_thread.is_alive()
        
        temp_file_manager.stop_cleanup()
        
        # 等待线程结束
        time.sleep(0.1)
        assert not temp_file_manager._cleanup_thread.is_alive()
    
    def test_context_manager_behavior(self, temp_dir):
        """测试上下文管理器行为"""
        with patch('gemini_kling_mcp.file_manager.core.get_config') as mock_config:
            mock_config.return_value.file.temp_dir = str(temp_dir)
            mock_config.return_value.file.max_file_size = 1024 * 1024
            mock_config.return_value.file.allowed_formats = ["txt", "jpg"]
            
            manager = TempFileManager(base_dir=temp_dir, cleanup_interval=60)
        
        # 创建临时文件
        temp_file = manager.create_temp_file(content=b"test")
        assert temp_file.exists()
        
        # 删除管理器应该停止清理线程
        del manager
        
        # 文件应该仍然存在（因为析构函数不会清理文件，只是停止线程）
        assert temp_file.exists()
    
    @pytest.mark.slow
    def test_large_number_of_temp_files(self, temp_file_manager):
        """测试大量临时文件的处理"""
        temp_files = []
        
        # 创建100个临时文件
        for i in range(100):
            temp_file = temp_file_manager.create_temp_file(
                content=f"file_{i}".encode(),
                prefix=f"test_{i}_"
            )
            temp_files.append(temp_file)
        
        assert len(temp_file_manager._temp_files) == 100
        
        # 清理所有文件
        cleaned = temp_file_manager.cleanup_temp_files(force=True)
        
        assert cleaned == 100
        assert len(temp_file_manager._temp_files) == 0
        
        for temp_file in temp_files:
            assert not temp_file.exists()
        
        # 清理
        temp_file_manager.stop_cleanup()
    
    def test_concurrent_access(self, temp_file_manager):
        """测试并发访问"""
        import concurrent.futures
        
        def create_and_cleanup():
            # 创建临时文件
            temp_file = temp_file_manager.create_temp_file(content=b"concurrent test")
            
            # 稍等一下
            time.sleep(0.1)
            
            # 清理文件
            temp_file_manager.cleanup_temp_files(force=True)
            
            return str(temp_file)
        
        # 并发执行
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_and_cleanup) for _ in range(10)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        assert len(results) == 10
        assert len(set(results)) == 10  # 所有文件名应该不同
        
        # 清理
        temp_file_manager.stop_cleanup()