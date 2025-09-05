"""
核心文件管理器

提供临时文件管理、文件生命周期管理和文件元数据处理。
"""

import os
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Callable, Union
import mimetypes
import hashlib
try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False
    magic = None

from ..logger import get_logger
from ..config import get_config

logger = get_logger(__name__)

@dataclass
class FileMetadata:
    """文件元数据"""
    path: Path
    size: int
    created_at: datetime
    modified_at: datetime
    mime_type: str
    extension: str
    checksum: str
    tags: Set[str] = field(default_factory=set)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "path": str(self.path),
            "size": self.size,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
            "mime_type": self.mime_type,
            "extension": self.extension,
            "checksum": self.checksum,
            "tags": list(self.tags)
        }

class FileManager:
    """文件管理器基类"""
    
    def __init__(self, base_dir: Optional[Union[str, Path]] = None):
        """初始化文件管理器
        
        Args:
            base_dir: 基础目录路径，如果为None则使用配置中的临时目录
        """
        config = get_config()
        self.base_dir = Path(base_dir or config.file.temp_dir)
        self.max_file_size = config.file.max_file_size
        self.allowed_formats = set(config.file.allowed_formats)
        
        # 确保基础目录存在
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("文件管理器初始化完成", base_dir=str(self.base_dir))
    
    def get_file_metadata(self, file_path: Union[str, Path]) -> FileMetadata:
        """获取文件元数据
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件元数据对象
            
        Raises:
            FileNotFoundError: 文件不存在
            OSError: 文件操作错误
        """
        path = Path(file_path).resolve()
        
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {path}")
        
        try:
            stat = path.stat()
            
            # 获取MIME类型
            mime_type, _ = mimetypes.guess_type(str(path))
            if not mime_type:
                # 使用python-magic进行更准确的检测（如果可用）
                if HAS_MAGIC:
                    try:
                        mime_type = magic.from_file(str(path), mime=True)
                    except Exception:
                        mime_type = "application/octet-stream"
                else:
                    mime_type = "application/octet-stream"
            
            # 计算文件校验和
            checksum = self._calculate_checksum(path)
            
            metadata = FileMetadata(
                path=path,
                size=stat.st_size,
                created_at=datetime.fromtimestamp(stat.st_ctime),
                modified_at=datetime.fromtimestamp(stat.st_mtime),
                mime_type=mime_type,
                extension=path.suffix.lower(),
                checksum=checksum
            )
            
            logger.debug("获取文件元数据", path=str(path), size=stat.st_size, mime_type=mime_type)
            return metadata
            
        except Exception as e:
            logger.error("获取文件元数据失败", path=str(path), error=str(e))
            raise OSError(f"获取文件元数据失败: {e}")
    
    def _calculate_checksum(self, file_path: Path, algorithm: str = "sha256") -> str:
        """计算文件校验和
        
        Args:
            file_path: 文件路径
            algorithm: 哈希算法
            
        Returns:
            文件校验和
        """
        hash_algo = hashlib.new(algorithm)
        
        try:
            with open(file_path, 'rb') as f:
                # 分块读取以处理大文件
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_algo.update(chunk)
            
            return hash_algo.hexdigest()
        except Exception as e:
            logger.error("计算文件校验和失败", path=str(file_path), error=str(e))
            return ""
    
    def validate_file(self, file_path: Union[str, Path]) -> bool:
        """验证文件是否符合要求
        
        Args:
            file_path: 文件路径
            
        Returns:
            验证结果
        """
        path = Path(file_path)
        
        # 检查文件是否存在
        if not path.exists():
            logger.warning("文件验证失败: 文件不存在", path=str(path))
            return False
        
        # 检查文件大小
        if path.stat().st_size > self.max_file_size:
            logger.warning("文件验证失败: 文件过大", path=str(path), 
                         size=path.stat().st_size, max_size=self.max_file_size)
            return False
        
        # 检查文件格式
        extension = path.suffix.lower().lstrip('.')
        if extension and extension not in self.allowed_formats:
            logger.warning("文件验证失败: 不支持的文件格式", path=str(path), 
                         extension=extension, allowed=list(self.allowed_formats))
            return False
        
        logger.debug("文件验证通过", path=str(path))
        return True
    
    def copy_file(self, source: Union[str, Path], destination: Union[str, Path], 
                  overwrite: bool = False) -> Path:
        """复制文件
        
        Args:
            source: 源文件路径
            destination: 目标文件路径
            overwrite: 是否覆盖已存在的文件
            
        Returns:
            目标文件路径
            
        Raises:
            FileNotFoundError: 源文件不存在
            FileExistsError: 目标文件已存在且不允许覆盖
            OSError: 文件操作错误
        """
        src_path = Path(source).resolve()
        dest_path = Path(destination).resolve()
        
        if not src_path.exists():
            raise FileNotFoundError(f"源文件不存在: {src_path}")
        
        if dest_path.exists() and not overwrite:
            raise FileExistsError(f"目标文件已存在: {dest_path}")
        
        try:
            # 确保目标目录存在
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 复制文件
            shutil.copy2(src_path, dest_path)
            
            logger.info("文件复制成功", source=str(src_path), destination=str(dest_path))
            return dest_path
            
        except Exception as e:
            logger.error("文件复制失败", source=str(src_path), 
                        destination=str(dest_path), error=str(e))
            raise OSError(f"文件复制失败: {e}")
    
    def move_file(self, source: Union[str, Path], destination: Union[str, Path], 
                  overwrite: bool = False) -> Path:
        """移动文件
        
        Args:
            source: 源文件路径
            destination: 目标文件路径
            overwrite: 是否覆盖已存在的文件
            
        Returns:
            目标文件路径
            
        Raises:
            FileNotFoundError: 源文件不存在
            FileExistsError: 目标文件已存在且不允许覆盖
            OSError: 文件操作错误
        """
        src_path = Path(source).resolve()
        dest_path = Path(destination).resolve()
        
        if not src_path.exists():
            raise FileNotFoundError(f"源文件不存在: {src_path}")
        
        if dest_path.exists() and not overwrite:
            raise FileExistsError(f"目标文件已存在: {dest_path}")
        
        try:
            # 确保目标目录存在
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 移动文件
            shutil.move(str(src_path), str(dest_path))
            
            logger.info("文件移动成功", source=str(src_path), destination=str(dest_path))
            return dest_path
            
        except Exception as e:
            logger.error("文件移动失败", source=str(src_path), 
                        destination=str(dest_path), error=str(e))
            raise OSError(f"文件移动失败: {e}")
    
    def delete_file(self, file_path: Union[str, Path], force: bool = False) -> bool:
        """删除文件
        
        Args:
            file_path: 文件路径
            force: 是否强制删除（忽略错误）
            
        Returns:
            删除是否成功
        """
        path = Path(file_path).resolve()
        
        try:
            if path.exists():
                path.unlink()
                logger.info("文件删除成功", path=str(path))
                return True
            else:
                logger.warning("文件删除失败: 文件不存在", path=str(path))
                return force  # 强制模式下即使文件不存在也返回True
                
        except Exception as e:
            logger.error("文件删除失败", path=str(path), error=str(e))
            if not force:
                raise OSError(f"文件删除失败: {e}")
            return False


class TempFileManager(FileManager):
    """临时文件管理器
    
    提供临时文件的创建、管理和自动清理功能。
    """
    
    def __init__(self, base_dir: Optional[Union[str, Path]] = None, 
                 cleanup_interval: int = 3600):
        """初始化临时文件管理器
        
        Args:
            base_dir: 临时文件基础目录
            cleanup_interval: 清理间隔（秒）
        """
        super().__init__(base_dir)
        
        self.cleanup_interval = cleanup_interval
        self._temp_files: Dict[str, FileMetadata] = {}
        self._lock = threading.RLock()
        self._cleanup_thread: Optional[threading.Thread] = None
        self._stop_cleanup = threading.Event()
        
        # 启动清理线程
        self._start_cleanup_thread()
        
        logger.info("临时文件管理器初始化完成", 
                   base_dir=str(self.base_dir), cleanup_interval=cleanup_interval)
    
    def create_temp_file(self, suffix: str = '', prefix: str = 'tmp_', 
                        content: Optional[bytes] = None) -> Path:
        """创建临时文件
        
        Args:
            suffix: 文件后缀
            prefix: 文件前缀
            content: 文件内容
            
        Returns:
            临时文件路径
        """
        with self._lock:
            try:
                # 创建临时文件
                fd, temp_path = tempfile.mkstemp(
                    suffix=suffix, prefix=prefix, dir=self.base_dir
                )
                
                temp_file = Path(temp_path)
                
                # 写入内容（如果提供）
                if content is not None:
                    with os.fdopen(fd, 'wb') as f:
                        f.write(content)
                else:
                    os.close(fd)
                
                # 记录临时文件
                metadata = self.get_file_metadata(temp_file)
                self._temp_files[str(temp_file)] = metadata
                
                logger.info("临时文件创建成功", path=str(temp_file), size=metadata.size)
                return temp_file
                
            except Exception as e:
                logger.error("临时文件创建失败", error=str(e))
                raise OSError(f"临时文件创建失败: {e}")
    
    def create_temp_dir(self, prefix: str = 'tmp_dir_') -> Path:
        """创建临时目录
        
        Args:
            prefix: 目录前缀
            
        Returns:
            临时目录路径
        """
        with self._lock:
            try:
                temp_dir = tempfile.mkdtemp(prefix=prefix, dir=self.base_dir)
                temp_path = Path(temp_dir)
                
                logger.info("临时目录创建成功", path=str(temp_path))
                return temp_path
                
            except Exception as e:
                logger.error("临时目录创建失败", error=str(e))
                raise OSError(f"临时目录创建失败: {e}")
    
    def register_temp_file(self, file_path: Union[str, Path], 
                          lifetime: Optional[int] = None) -> None:
        """注册现有文件为临时文件
        
        Args:
            file_path: 文件路径
            lifetime: 文件生命周期（秒），None表示使用默认值
        """
        path = Path(file_path).resolve()
        
        with self._lock:
            if not path.exists():
                logger.warning("注册临时文件失败: 文件不存在", path=str(path))
                return
            
            try:
                metadata = self.get_file_metadata(path)
                
                # 设置生命周期
                if lifetime is not None:
                    metadata.tags.add(f"lifetime:{lifetime}")
                
                self._temp_files[str(path)] = metadata
                
                logger.info("临时文件注册成功", path=str(path))
                
            except Exception as e:
                logger.error("注册临时文件失败", path=str(path), error=str(e))
    
    def cleanup_temp_files(self, max_age: Optional[int] = None, 
                          force: bool = False) -> int:
        """清理临时文件
        
        Args:
            max_age: 最大文件年龄（秒），超过此时间的文件将被清理
            force: 是否强制清理所有临时文件
            
        Returns:
            清理的文件数量
        """
        if max_age is None:
            max_age = self.cleanup_interval
        
        current_time = datetime.now()
        cleaned_count = 0
        
        with self._lock:
            files_to_remove = []
            
            for file_path, metadata in self._temp_files.items():
                should_clean = force
                
                if not should_clean:
                    # 检查文件年龄
                    age = (current_time - metadata.created_at).total_seconds()
                    should_clean = age > max_age
                
                if not should_clean:
                    # 检查自定义生命周期
                    lifetime_tags = [tag for tag in metadata.tags if tag.startswith("lifetime:")]
                    if lifetime_tags:
                        try:
                            custom_lifetime = int(lifetime_tags[0].split(":")[1])
                            age = (current_time - metadata.created_at).total_seconds()
                            should_clean = age > custom_lifetime
                        except (ValueError, IndexError):
                            pass
                
                if should_clean:
                    try:
                        if Path(file_path).exists():
                            Path(file_path).unlink()
                            cleaned_count += 1
                            logger.debug("临时文件已清理", path=file_path)
                        
                        files_to_remove.append(file_path)
                        
                    except Exception as e:
                        logger.error("清理临时文件失败", path=file_path, error=str(e))
            
            # 从记录中移除已清理的文件
            for file_path in files_to_remove:
                del self._temp_files[file_path]
        
        if cleaned_count > 0:
            logger.info("临时文件清理完成", cleaned_count=cleaned_count)
        
        return cleaned_count
    
    def get_temp_files_info(self) -> List[Dict[str, Any]]:
        """获取临时文件信息
        
        Returns:
            临时文件信息列表
        """
        with self._lock:
            return [metadata.to_dict() for metadata in self._temp_files.values()]
    
    def _start_cleanup_thread(self) -> None:
        """启动清理线程"""
        if self._cleanup_thread is None or not self._cleanup_thread.is_alive():
            self._cleanup_thread = threading.Thread(
                target=self._cleanup_worker, daemon=True
            )
            self._cleanup_thread.start()
    
    def _cleanup_worker(self) -> None:
        """清理工作线程"""
        while not self._stop_cleanup.wait(self.cleanup_interval):
            try:
                self.cleanup_temp_files()
            except Exception as e:
                logger.error("自动清理临时文件时发生错误", error=str(e))
    
    def stop_cleanup(self) -> None:
        """停止清理线程"""
        self._stop_cleanup.set()
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5)
        logger.info("临时文件清理线程已停止")
    
    def __del__(self):
        """析构函数，确保清理线程停止"""
        try:
            self.stop_cleanup()
        except Exception:
            pass