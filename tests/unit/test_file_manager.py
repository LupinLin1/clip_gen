"""
文件管理器单元测试

测试文件管理器的核心功能，包括文件元数据、文件操作和临时文件管理。
"""

import pytest
import tempfile
import shutil
import os
import time
import threading
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, Mock, mock_open

from src.gemini_kling_mcp.file_manager.core import (
    FileManager, TempFileManager, FileMetadata
)
from src.gemini_kling_mcp.config import FileConfig


@pytest.mark.unit
class TestFileMetadata:
    """文件元数据测试类"""
    
    def test_metadata_creation(self):
        """测试元数据创建"""
        path = Path("/test/file.txt")
        created_at = datetime.now()
        metadata = FileMetadata(
            path=path,
            size=1024,
            created_at=created_at,
            modified_at=created_at,
            mime_type="text/plain",
            extension=".txt",
            checksum="abc123",
            tags={"temp", "test"}
        )
        
        assert metadata.path == path
        assert metadata.size == 1024
        assert metadata.mime_type == "text/plain"
        assert metadata.extension == ".txt"
        assert metadata.checksum == "abc123"
        assert "temp" in metadata.tags
        assert "test" in metadata.tags
    
    def test_metadata_to_dict(self):
        """测试元数据转换为字典"""
        path = Path("/test/file.txt")
        created_at = datetime(2023, 1, 1, 12, 0, 0)
        modified_at = datetime(2023, 1, 1, 12, 30, 0)
        
        metadata = FileMetadata(
            path=path,
            size=2048,
            created_at=created_at,
            modified_at=modified_at,
            mime_type="application/json",
            extension=".json",
            checksum="def456",
            tags={"json", "data"}
        )
        
        result = metadata.to_dict()
        
        assert result["path"] == str(path)
        assert result["size"] == 2048
        assert result["created_at"] == "2023-01-01T12:00:00"
        assert result["modified_at"] == "2023-01-01T12:30:00"
        assert result["mime_type"] == "application/json"
        assert result["extension"] == ".json"
        assert result["checksum"] == "def456"
        assert set(result["tags"]) == {"json", "data"}


@pytest.mark.unit
class TestFileManager:
    """文件管理器测试类"""
    
    @pytest.fixture
    def mock_file_config(self):
        """Mock文件配置"""
        return FileConfig(
            temp_dir="/tmp/test",
            max_file_size=1024 * 1024,  # 1MB
            cleanup_interval=3600,
            allowed_formats=["jpg", "png", "txt", "json", "mp4"]
        )
    
    @pytest.fixture
    def test_file_manager(self, temp_dir, mock_file_config):
        """测试文件管理器"""
        with patch('src.gemini_kling_mcp.file_manager.core.get_config') as mock_config:
            mock_config.return_value.file = mock_file_config
            manager = FileManager(temp_dir)
            yield manager
    
    @pytest.fixture
    def create_test_file(self, temp_dir):
        """创建测试文件"""
        def _create_file(filename: str, content: str = "test content", size: int = None):
            file_path = Path(temp_dir) / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            if size is not None:
                # 创建指定大小的文件
                with open(file_path, 'wb') as f:
                    f.write(b'x' * size)
            else:
                # 创建包含内容的文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            return file_path
        
        return _create_file
    
    def test_file_manager_initialization(self, temp_dir, mock_file_config):
        """测试文件管理器初始化"""
        with patch('src.gemini_kling_mcp.file_manager.core.get_config') as mock_config:
            mock_config.return_value.file = mock_file_config
            
            manager = FileManager(temp_dir)
            
            assert manager.base_dir == Path(temp_dir)
            assert manager.max_file_size == 1024 * 1024
            assert manager.allowed_formats == {"jpg", "png", "txt", "json", "mp4"}
            assert manager.base_dir.exists()
    
    def test_get_file_metadata_success(self, test_file_manager, create_test_file):
        """测试成功获取文件元数据"""
        test_file = create_test_file("test.txt", "Hello, World!")
        
        metadata = test_file_manager.get_file_metadata(test_file)
        
        assert metadata.path == test_file.resolve()
        assert metadata.size > 0
        assert metadata.mime_type == "text/plain"
        assert metadata.extension == ".txt"
        assert isinstance(metadata.created_at, datetime)
        assert isinstance(metadata.modified_at, datetime)
        assert len(metadata.checksum) > 0
    
    def test_get_file_metadata_nonexistent_file(self, test_file_manager, temp_dir):
        """测试获取不存在文件的元数据"""
        nonexistent_file = Path(temp_dir) / "nonexistent.txt"
        
        with pytest.raises(FileNotFoundError, match="文件不存在"):
            test_file_manager.get_file_metadata(nonexistent_file)
    
    def test_calculate_checksum(self, test_file_manager, create_test_file):
        """测试计算文件校验和"""
        test_file = create_test_file("checksum_test.txt", "consistent content")
        
        # 计算两次校验和应该相同
        checksum1 = test_file_manager._calculate_checksum(test_file)
        checksum2 = test_file_manager._calculate_checksum(test_file)
        
        assert checksum1 == checksum2
        assert len(checksum1) == 64  # SHA256 hex length
        assert checksum1 != ""
    
    def test_calculate_checksum_empty_file(self, test_file_manager, create_test_file):
        """测试计算空文件校验和"""
        test_file = create_test_file("empty.txt", "")
        
        checksum = test_file_manager._calculate_checksum(test_file)
        
        # SHA256 of empty string
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert checksum == expected
    
    def test_validate_file_success(self, test_file_manager, create_test_file):
        """测试文件验证成功"""
        test_file = create_test_file("valid.txt", "valid content")
        
        result = test_file_manager.validate_file(test_file)
        
        assert result is True
    
    def test_validate_file_nonexistent(self, test_file_manager, temp_dir):
        """测试验证不存在的文件"""
        nonexistent_file = Path(temp_dir) / "nonexistent.txt"
        
        result = test_file_manager.validate_file(nonexistent_file)
        
        assert result is False
    
    def test_validate_file_too_large(self, test_file_manager, create_test_file):
        """测试文件过大验证失败"""
        # 创建超过最大大小限制的文件
        large_file = create_test_file("large.txt", size=2 * 1024 * 1024)  # 2MB
        
        result = test_file_manager.validate_file(large_file)
        
        assert result is False
    
    def test_validate_file_invalid_format(self, test_file_manager, create_test_file):
        """测试无效文件格式验证失败"""
        invalid_file = create_test_file("test.exe", "executable content")
        
        result = test_file_manager.validate_file(invalid_file)
        
        assert result is False
    
    def test_copy_file_success(self, test_file_manager, create_test_file, temp_dir):
        """测试成功复制文件"""
        source_file = create_test_file("source.txt", "source content")
        dest_file = Path(temp_dir) / "dest.txt"
        
        result_path = test_file_manager.copy_file(source_file, dest_file)
        
        assert result_path == dest_file.resolve()
        assert dest_file.exists()
        assert source_file.exists()  # 源文件应该仍然存在
        
        # 验证内容相同
        assert source_file.read_text() == dest_file.read_text()
    
    def test_copy_file_with_directories(self, test_file_manager, create_test_file, temp_dir):
        """测试复制文件到不存在的目录"""
        source_file = create_test_file("source.txt", "source content")
        dest_file = Path(temp_dir) / "subdir" / "dest.txt"
        
        result_path = test_file_manager.copy_file(source_file, dest_file)
        
        assert result_path == dest_file.resolve()
        assert dest_file.exists()
        assert dest_file.parent.exists()  # 目录应该被创建
    
    def test_copy_file_overwrite(self, test_file_manager, create_test_file, temp_dir):
        """测试覆盖复制文件"""
        source_file = create_test_file("source.txt", "new content")
        dest_file = create_test_file("dest.txt", "old content")
        
        # 不允许覆盖
        with pytest.raises(FileExistsError, match="目标文件已存在"):
            test_file_manager.copy_file(source_file, dest_file)
        
        # 允许覆盖
        result_path = test_file_manager.copy_file(source_file, dest_file, overwrite=True)
        
        assert result_path == dest_file.resolve()
        assert dest_file.read_text() == "new content"
    
    def test_copy_file_nonexistent_source(self, test_file_manager, temp_dir):
        """测试复制不存在的源文件"""
        source_file = Path(temp_dir) / "nonexistent.txt"
        dest_file = Path(temp_dir) / "dest.txt"
        
        with pytest.raises(FileNotFoundError, match="源文件不存在"):
            test_file_manager.copy_file(source_file, dest_file)
    
    def test_move_file_success(self, test_file_manager, create_test_file, temp_dir):
        """测试成功移动文件"""
        source_file = create_test_file("source.txt", "source content")
        dest_file = Path(temp_dir) / "moved.txt"
        
        result_path = test_file_manager.move_file(source_file, dest_file)
        
        assert result_path == dest_file.resolve()
        assert dest_file.exists()
        assert not source_file.exists()  # 源文件应该不再存在
        assert dest_file.read_text() == "source content"
    
    def test_move_file_overwrite(self, test_file_manager, create_test_file, temp_dir):
        """测试覆盖移动文件"""
        source_file = create_test_file("source.txt", "new content")
        dest_file = create_test_file("dest.txt", "old content")
        
        # 不允许覆盖
        with pytest.raises(FileExistsError, match="目标文件已存在"):
            test_file_manager.move_file(source_file, dest_file)
        
        # 允许覆盖
        result_path = test_file_manager.move_file(source_file, dest_file, overwrite=True)
        
        assert result_path == dest_file.resolve()
        assert dest_file.read_text() == "new content"
        assert not source_file.exists()
    
    def test_delete_file_success(self, test_file_manager, create_test_file):
        """测试成功删除文件"""
        test_file = create_test_file("to_delete.txt", "content to delete")
        
        result = test_file_manager.delete_file(test_file)
        
        assert result is True
        assert not test_file.exists()
    
    def test_delete_file_nonexistent(self, test_file_manager, temp_dir):
        """测试删除不存在的文件"""
        nonexistent_file = Path(temp_dir) / "nonexistent.txt"
        
        # 非强制模式
        result = test_file_manager.delete_file(nonexistent_file)
        assert result is False
        
        # 强制模式
        result = test_file_manager.delete_file(nonexistent_file, force=True)
        assert result is True
    
    @patch('src.gemini_kling_mcp.file_manager.core.magic')
    def test_get_file_metadata_with_magic(self, mock_magic, test_file_manager, create_test_file):
        """测试使用python-magic获取MIME类型"""
        with patch('src.gemini_kling_mcp.file_manager.core.HAS_MAGIC', True):
            mock_magic.from_file.return_value = "image/jpeg"
            
            test_file = create_test_file("test.unknown", "binary content")
            
            with patch('mimetypes.guess_type', return_value=(None, None)):
                metadata = test_file_manager.get_file_metadata(test_file)
                
                assert metadata.mime_type == "image/jpeg"
                mock_magic.from_file.assert_called_once()


@pytest.mark.unit
class TestTempFileManager:
    """临时文件管理器测试类"""
    
    @pytest.fixture
    def mock_file_config(self):
        """Mock文件配置"""
        return FileConfig(
            temp_dir="/tmp/test",
            max_file_size=1024 * 1024,
            cleanup_interval=1,  # 1秒清理间隔用于测试
            allowed_formats=["txt", "json", "tmp"]
        )
    
    @pytest.fixture
    def temp_file_manager(self, temp_dir, mock_file_config):
        """临时文件管理器"""
        with patch('src.gemini_kling_mcp.file_manager.core.get_config') as mock_config:
            mock_config.return_value.file = mock_file_config
            
            manager = TempFileManager(temp_dir, cleanup_interval=1)
            yield manager
            
            # 清理
            manager.stop_cleanup()
    
    def test_temp_file_manager_initialization(self, temp_dir, mock_file_config):
        """测试临时文件管理器初始化"""
        with patch('src.gemini_kling_mcp.file_manager.core.get_config') as mock_config:
            mock_config.return_value.file = mock_file_config
            
            manager = TempFileManager(temp_dir, cleanup_interval=60)
            
            assert manager.base_dir == Path(temp_dir)
            assert manager.cleanup_interval == 60
            assert isinstance(manager._temp_files, dict)
            assert manager._cleanup_thread is not None
            
            manager.stop_cleanup()
    
    def test_create_temp_file_without_content(self, temp_file_manager):
        """测试创建不含内容的临时文件"""
        temp_file = temp_file_manager.create_temp_file(suffix='.txt', prefix='test_')
        
        assert temp_file.exists()
        assert temp_file.suffix == '.txt'
        assert temp_file.name.startswith('test_')
        assert str(temp_file) in temp_file_manager._temp_files
    
    def test_create_temp_file_with_content(self, temp_file_manager):
        """测试创建包含内容的临时文件"""
        content = b"Hello, temporary world!"
        temp_file = temp_file_manager.create_temp_file(
            suffix='.txt',
            prefix='content_',
            content=content
        )
        
        assert temp_file.exists()
        assert temp_file.read_bytes() == content
        assert str(temp_file) in temp_file_manager._temp_files
        
        # 检查元数据
        metadata = temp_file_manager._temp_files[str(temp_file)]
        assert metadata.size == len(content)
    
    def test_create_temp_dir(self, temp_file_manager):
        """测试创建临时目录"""
        temp_dir = temp_file_manager.create_temp_dir(prefix='test_dir_')
        
        assert temp_dir.exists()
        assert temp_dir.is_dir()
        assert temp_dir.name.startswith('test_dir_')
    
    def test_register_temp_file(self, temp_file_manager, temp_dir):
        """测试注册现有文件为临时文件"""
        # 创建现有文件
        existing_file = Path(temp_dir) / "existing.txt"
        existing_file.write_text("existing content")
        
        # 注册为临时文件
        temp_file_manager.register_temp_file(existing_file, lifetime=300)
        
        assert str(existing_file) in temp_file_manager._temp_files
        
        metadata = temp_file_manager._temp_files[str(existing_file)]
        assert "lifetime:300" in metadata.tags
    
    def test_register_nonexistent_file(self, temp_file_manager, temp_dir):
        """测试注册不存在的文件"""
        nonexistent_file = Path(temp_dir) / "nonexistent.txt"
        
        # 注册不存在的文件应该不会抛出异常
        temp_file_manager.register_temp_file(nonexistent_file)
        
        # 不应该被添加到临时文件列表中
        assert str(nonexistent_file) not in temp_file_manager._temp_files
    
    def test_cleanup_temp_files_by_age(self, temp_file_manager):
        """测试按年龄清理临时文件"""
        # 创建临时文件
        temp_file = temp_file_manager.create_temp_file(suffix='.txt')
        
        assert temp_file.exists()
        assert str(temp_file) in temp_file_manager._temp_files
        
        # 清理年龄为0的文件（应该清理所有文件）
        cleaned_count = temp_file_manager.cleanup_temp_files(max_age=0)
        
        assert cleaned_count == 1
        assert not temp_file.exists()
        assert str(temp_file) not in temp_file_manager._temp_files
    
    def test_cleanup_temp_files_force(self, temp_file_manager):
        """测试强制清理临时文件"""
        # 创建多个临时文件
        temp_file1 = temp_file_manager.create_temp_file(suffix='.txt')
        temp_file2 = temp_file_manager.create_temp_file(suffix='.json')
        
        assert len(temp_file_manager._temp_files) == 2
        
        # 强制清理所有文件
        cleaned_count = temp_file_manager.cleanup_temp_files(force=True)
        
        assert cleaned_count == 2
        assert not temp_file1.exists()
        assert not temp_file2.exists()
        assert len(temp_file_manager._temp_files) == 0
    
    def test_cleanup_temp_files_custom_lifetime(self, temp_file_manager, temp_dir):
        """测试自定义生命周期的文件清理"""
        # 创建文件并设置自定义生命周期
        existing_file = Path(temp_dir) / "custom_lifetime.txt"
        existing_file.write_text("content")
        
        # 注册文件，设置1秒生命周期
        temp_file_manager.register_temp_file(existing_file, lifetime=1)
        
        # 等待超过生命周期
        time.sleep(1.1)
        
        # 清理应该删除文件
        cleaned_count = temp_file_manager.cleanup_temp_files()
        
        assert cleaned_count == 1
        assert not existing_file.exists()
    
    def test_get_temp_files_info(self, temp_file_manager):
        """测试获取临时文件信息"""
        # 创建临时文件
        temp_file = temp_file_manager.create_temp_file(suffix='.txt', content=b"test")
        
        info_list = temp_file_manager.get_temp_files_info()
        
        assert len(info_list) == 1
        info = info_list[0]
        
        assert info["path"] == str(temp_file)
        assert info["size"] == 4  # "test" is 4 bytes
        assert info["mime_type"] == "text/plain"
        assert info["extension"] == ".txt"
        assert "created_at" in info
        assert "modified_at" in info
        assert "checksum" in info
    
    def test_cleanup_thread_auto_cleanup(self, temp_dir, mock_file_config):
        """测试清理线程自动清理"""
        with patch('src.gemini_kling_mcp.file_manager.core.get_config') as mock_config:
            mock_config.return_value.file = mock_file_config
            
            # 使用很短的清理间隔
            manager = TempFileManager(temp_dir, cleanup_interval=0.5)
            
            # 创建临时文件
            temp_file = manager.create_temp_file(suffix='.txt')
            assert temp_file.exists()
            
            # 等待自动清理
            time.sleep(1)
            
            # 检查是否被清理（文件很新，应该还没被清理）
            assert temp_file.exists()
            
            # 手动清理所有文件
            manager.cleanup_temp_files(force=True)
            assert not temp_file.exists()
            
            manager.stop_cleanup()
    
    def test_stop_cleanup(self, temp_file_manager):
        """测试停止清理线程"""
        assert temp_file_manager._cleanup_thread is not None
        assert temp_file_manager._cleanup_thread.is_alive()
        
        temp_file_manager.stop_cleanup()
        
        # 等待线程停止
        time.sleep(0.1)
        assert temp_file_manager._stop_cleanup.is_set()
    
    def test_temp_file_manager_destructor(self, temp_dir, mock_file_config):
        """测试临时文件管理器析构函数"""
        with patch('src.gemini_kling_mcp.file_manager.core.get_config') as mock_config:
            mock_config.return_value.file = mock_file_config
            
            manager = TempFileManager(temp_dir, cleanup_interval=10)
            
            # 模拟析构
            manager.__del__()
            
            assert manager._stop_cleanup.is_set()
    
    def test_thread_safety(self, temp_file_manager):
        """测试线程安全性"""
        files_created = []
        
        def create_files():
            for i in range(10):
                temp_file = temp_file_manager.create_temp_file(
                    suffix=f'_{i}.txt',
                    content=f"content_{i}".encode()
                )
                files_created.append(temp_file)
        
        # 并发创建文件
        threads = [threading.Thread(target=create_files) for _ in range(3)]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # 验证所有文件都被创建和记录
        assert len(files_created) == 30
        assert len(temp_file_manager._temp_files) == 30
        
        for temp_file in files_created:
            assert temp_file.exists()
            assert str(temp_file) in temp_file_manager._temp_files
    
    def test_cleanup_with_file_permission_error(self, temp_file_manager, temp_dir):
        """测试清理时遇到权限错误"""
        # 创建临时文件
        temp_file = temp_file_manager.create_temp_file(suffix='.txt')
        
        # Mock unlink方法抛出权限错误
        with patch.object(Path, 'unlink', side_effect=PermissionError("Permission denied")):
            cleaned_count = temp_file_manager.cleanup_temp_files(force=True)
            
            # 即使删除失败，也应该从记录中移除
            assert cleaned_count == 0
            assert str(temp_file) not in temp_file_manager._temp_files
    
    def test_cleanup_worker_exception_handling(self, temp_dir, mock_file_config):
        """测试清理工作线程异常处理"""
        with patch('src.gemini_kling_mcp.file_manager.core.get_config') as mock_config:
            mock_config.return_value.file = mock_file_config
            
            manager = TempFileManager(temp_dir, cleanup_interval=0.1)
            
            # Mock cleanup_temp_files抛出异常
            with patch.object(manager, 'cleanup_temp_files', side_effect=Exception("Cleanup error")):
                # 等待清理线程执行
                time.sleep(0.2)
                
                # 线程应该还在运行（异常被捕获）
                assert manager._cleanup_thread.is_alive()
            
            manager.stop_cleanup()