"""
输出模式处理

提供多种文件输出模式：file_path、base64、url 和 auto。
"""

import base64
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, Union, BinaryIO, List
from urllib.parse import urljoin
import threading
import http.server
import socketserver
from contextlib import contextmanager

from ..logger import get_logger
from .security import FileSecurityValidator

logger = get_logger(__name__)

class OutputMode(Enum):
    """输出模式枚举"""
    FILE_PATH = "file_path"
    BASE64 = "base64"
    URL = "url"
    AUTO = "auto"

@dataclass
class OutputResult:
    """输出结果"""
    mode: OutputMode
    data: Any
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "mode": self.mode.value,
            "data": self.data,
            "metadata": self.metadata
        }

class BaseOutputHandler(ABC):
    """输出处理器基类"""
    
    def __init__(self, security_validator: Optional[FileSecurityValidator] = None):
        """初始化输出处理器
        
        Args:
            security_validator: 安全验证器
        """
        self.security_validator = security_validator or FileSecurityValidator()
        
    @abstractmethod
    def can_handle(self, file_path: Union[str, Path], **kwargs) -> bool:
        """检查是否可以处理该文件
        
        Args:
            file_path: 文件路径
            **kwargs: 额外参数
            
        Returns:
            是否可以处理
        """
        pass
    
    @abstractmethod
    def process(self, file_path: Union[str, Path], **kwargs) -> OutputResult:
        """处理文件输出
        
        Args:
            file_path: 文件路径
            **kwargs: 额外参数
            
        Returns:
            输出结果
        """
        pass
    
    def _validate_file(self, file_path: Union[str, Path]) -> Path:
        """验证文件安全性
        
        Args:
            file_path: 文件路径
            
        Returns:
            验证后的安全路径
        """
        return self.security_validator.validate_path(file_path)

class FilePathOutputHandler(BaseOutputHandler):
    """文件路径输出处理器"""
    
    def can_handle(self, file_path: Union[str, Path], **kwargs) -> bool:
        """检查是否可以处理该文件"""
        try:
            path = Path(file_path)
            return path.exists() and path.is_file()
        except Exception:
            return False
    
    def process(self, file_path: Union[str, Path], **kwargs) -> OutputResult:
        """处理文件路径输出
        
        Args:
            file_path: 文件路径
            **kwargs: 额外参数
            
        Returns:
            输出结果
        """
        safe_path = self._validate_file(file_path)
        
        # 获取文件信息
        stat = safe_path.stat()
        
        metadata = {
            "size": stat.st_size,
            "path": str(safe_path),
            "absolute_path": str(safe_path.resolve()),
            "exists": True
        }
        
        logger.debug("文件路径输出处理完成", path=str(safe_path))
        
        return OutputResult(
            mode=OutputMode.FILE_PATH,
            data=str(safe_path),
            metadata=metadata
        )

class Base64OutputHandler(BaseOutputHandler):
    """Base64编码输出处理器"""
    
    def __init__(self, security_validator: Optional[FileSecurityValidator] = None,
                 chunk_size: int = 8192, max_size: int = 10 * 1024 * 1024):
        """初始化Base64处理器
        
        Args:
            security_validator: 安全验证器
            chunk_size: 分块大小
            max_size: 最大文件大小（用于Base64编码）
        """
        super().__init__(security_validator)
        self.chunk_size = chunk_size
        self.max_size = max_size
    
    def can_handle(self, file_path: Union[str, Path], **kwargs) -> bool:
        """检查是否可以处理该文件"""
        try:
            path = Path(file_path)
            if not path.exists() or not path.is_file():
                return False
            
            # 检查文件大小
            if path.stat().st_size > self.max_size:
                logger.warning("文件过大，不适合Base64编码", 
                              path=str(path), size=path.stat().st_size, max_size=self.max_size)
                return False
            
            return True
        except Exception:
            return False
    
    def process(self, file_path: Union[str, Path], **kwargs) -> OutputResult:
        """处理Base64编码输出
        
        Args:
            file_path: 文件路径
            **kwargs: 额外参数
            
        Returns:
            输出结果
        """
        safe_path = self._validate_file(file_path)
        
        try:
            # 使用流式处理编码大文件
            encoded_data = self._encode_file_base64(safe_path)
            
            # 获取文件信息
            stat = safe_path.stat()
            mime_type = self.security_validator.validate_file_type(safe_path)
            
            metadata = {
                "size": stat.st_size,
                "encoded_size": len(encoded_data),
                "mime_type": mime_type,
                "encoding": "base64",
                "path": str(safe_path)
            }
            
            logger.info("Base64编码输出处理完成", 
                       path=str(safe_path), original_size=stat.st_size, 
                       encoded_size=len(encoded_data))
            
            return OutputResult(
                mode=OutputMode.BASE64,
                data=encoded_data,
                metadata=metadata
            )
            
        except Exception as e:
            logger.error("Base64编码失败", path=str(safe_path), error=str(e))
            raise OSError(f"Base64编码失败: {e}")
    
    def _encode_file_base64(self, file_path: Path) -> str:
        """流式Base64编码文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            Base64编码字符串
        """
        encoded_chunks = []
        
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(self.chunk_size)
                if not chunk:
                    break
                encoded_chunk = base64.b64encode(chunk).decode('utf-8')
                encoded_chunks.append(encoded_chunk)
        
        return ''.join(encoded_chunks)

class URLOutputHandler(BaseOutputHandler):
    """URL输出处理器"""
    
    def __init__(self, security_validator: Optional[FileSecurityValidator] = None,
                 server_host: str = "localhost", server_port: int = 0,
                 url_prefix: str = ""):
        """初始化URL处理器
        
        Args:
            security_validator: 安全验证器
            server_host: 服务器主机
            server_port: 服务器端口（0表示自动选择）
            url_prefix: URL前缀
        """
        super().__init__(security_validator)
        self.server_host = server_host
        self.server_port = server_port
        self.url_prefix = url_prefix
        self._server: Optional[socketserver.TCPServer] = None
        self._server_thread: Optional[threading.Thread] = None
        self._served_files: Dict[str, Path] = {}
        self._lock = threading.RLock()
    
    def can_handle(self, file_path: Union[str, Path], **kwargs) -> bool:
        """检查是否可以处理该文件"""
        try:
            path = Path(file_path)
            return path.exists() and path.is_file()
        except Exception:
            return False
    
    def process(self, file_path: Union[str, Path], **kwargs) -> OutputResult:
        """处理URL输出
        
        Args:
            file_path: 文件路径
            **kwargs: 额外参数
            
        Returns:
            输出结果
        """
        safe_path = self._validate_file(file_path)
        
        try:
            # 启动文件服务器（如果尚未启动）
            self._ensure_server_running()
            
            # 生成文件URL
            file_url = self._register_file(safe_path)
            
            # 获取文件信息
            stat = safe_path.stat()
            mime_type = self.security_validator.validate_file_type(safe_path)
            
            metadata = {
                "size": stat.st_size,
                "mime_type": mime_type,
                "path": str(safe_path),
                "server_host": self.server_host,
                "server_port": self._get_server_port()
            }
            
            logger.info("URL输出处理完成", 
                       path=str(safe_path), url=file_url)
            
            return OutputResult(
                mode=OutputMode.URL,
                data=file_url,
                metadata=metadata
            )
            
        except Exception as e:
            logger.error("URL输出处理失败", path=str(safe_path), error=str(e))
            raise OSError(f"URL输出处理失败: {e}")
    
    def _ensure_server_running(self) -> None:
        """确保文件服务器正在运行"""
        with self._lock:
            if self._server is None or not self._server_thread or not self._server_thread.is_alive():
                self._start_server()
    
    def _start_server(self) -> None:
        """启动文件服务器"""
        try:
            # 创建自定义请求处理器
            handler = self._create_request_handler()
            
            # 创建服务器
            self._server = socketserver.TCPServer(
                (self.server_host, self.server_port), handler
            )
            
            # 获取实际端口号
            actual_port = self._server.server_address[1]
            
            # 启动服务器线程
            self._server_thread = threading.Thread(
                target=self._server.serve_forever, daemon=True
            )
            self._server_thread.start()
            
            logger.info("文件服务器启动", 
                       host=self.server_host, port=actual_port)
            
        except Exception as e:
            logger.error("启动文件服务器失败", error=str(e))
            raise OSError(f"启动文件服务器失败: {e}")
    
    def _create_request_handler(self):
        """创建请求处理器类"""
        served_files = self._served_files
        security_validator = self.security_validator
        
        class FileRequestHandler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                # 解析路径
                path = self.path.lstrip('/')
                
                if path in served_files:
                    file_path = served_files[path]
                    try:
                        # 验证文件仍然安全
                        safe_path = security_validator.validate_path(file_path)
                        
                        # 发送文件
                        with open(safe_path, 'rb') as f:
                            self.send_response(200)
                            self.send_header('Content-Type', self._guess_type(safe_path))
                            self.send_header('Content-Length', str(safe_path.stat().st_size))
                            self.end_headers()
                            
                            # 分块发送文件
                            while True:
                                chunk = f.read(8192)
                                if not chunk:
                                    break
                                self.wfile.write(chunk)
                        
                        logger.debug("文件服务请求成功", path=path, file_path=str(safe_path))
                        
                    except Exception as e:
                        logger.error("文件服务请求失败", path=path, error=str(e))
                        self.send_error(500, f"Internal Server Error: {e}")
                else:
                    logger.warning("文件未找到", path=path)
                    self.send_error(404, "File Not Found")
            
            def _guess_type(self, file_path: Path) -> str:
                """猜测文件MIME类型"""
                try:
                    return security_validator.validate_file_type(file_path)
                except Exception:
                    return 'application/octet-stream'
            
            def log_message(self, format, *args):
                """重写日志方法以使用我们的日志系统"""
                logger.debug("HTTP请求", message=format % args)
        
        return FileRequestHandler
    
    def _register_file(self, file_path: Path) -> str:
        """注册文件并生成URL
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件URL
        """
        # 生成唯一的文件标识符
        file_id = f"file_{len(self._served_files)}_{file_path.name}"
        
        # 注册文件
        self._served_files[file_id] = file_path
        
        # 生成URL
        base_url = f"http://{self.server_host}:{self._get_server_port()}"
        if self.url_prefix:
            file_url = urljoin(f"{base_url}/{self.url_prefix}/", file_id)
        else:
            file_url = urljoin(f"{base_url}/", file_id)
        
        return file_url
    
    def _get_server_port(self) -> int:
        """获取服务器端口"""
        if self._server:
            return self._server.server_address[1]
        return self.server_port
    
    def stop_server(self) -> None:
        """停止文件服务器"""
        with self._lock:
            if self._server:
                self._server.shutdown()
                self._server.server_close()
                self._server = None
                logger.info("文件服务器已停止")
            
            if self._server_thread and self._server_thread.is_alive():
                self._server_thread.join(timeout=5)
                self._server_thread = None

class AutoOutputHandler(BaseOutputHandler):
    """自动选择输出模式处理器"""
    
    def __init__(self, security_validator: Optional[FileSecurityValidator] = None,
                 file_path_handler: Optional[FilePathOutputHandler] = None,
                 base64_handler: Optional[Base64OutputHandler] = None,
                 url_handler: Optional[URLOutputHandler] = None):
        """初始化自动输出处理器
        
        Args:
            security_validator: 安全验证器
            file_path_handler: 文件路径处理器
            base64_handler: Base64处理器
            url_handler: URL处理器
        """
        super().__init__(security_validator)
        
        self.file_path_handler = file_path_handler or FilePathOutputHandler(security_validator)
        self.base64_handler = base64_handler or Base64OutputHandler(security_validator)
        self.url_handler = url_handler or URLOutputHandler(security_validator)
        
        # 默认优先级：文件路径 > Base64 > URL
        self.handlers = [
            self.file_path_handler,
            self.base64_handler,
            self.url_handler
        ]
    
    def can_handle(self, file_path: Union[str, Path], **kwargs) -> bool:
        """检查是否可以处理该文件"""
        return any(handler.can_handle(file_path, **kwargs) for handler in self.handlers)
    
    def process(self, file_path: Union[str, Path], **kwargs) -> OutputResult:
        """自动选择最适合的输出模式
        
        Args:
            file_path: 文件路径
            **kwargs: 额外参数
            
        Returns:
            输出结果
        """
        safe_path = self._validate_file(file_path)
        
        # 获取文件信息用于选择策略
        stat = safe_path.stat()
        file_size = stat.st_size
        
        # 选择策略
        selected_handler = self._select_best_handler(safe_path, file_size, **kwargs)
        
        if selected_handler:
            result = selected_handler.process(safe_path, **kwargs)
            
            # 添加自动选择的元数据
            result.metadata["auto_selected"] = True
            result.metadata["selected_handler"] = selected_handler.__class__.__name__
            
            logger.info("自动输出模式选择完成", 
                       path=str(safe_path), 
                       selected_mode=result.mode.value,
                       selected_handler=result.metadata["selected_handler"])
            
            return result
        else:
            raise OSError(f"无法为文件选择合适的输出模式: {safe_path}")
    
    def _select_best_handler(self, file_path: Path, file_size: int, 
                            **kwargs) -> Optional[BaseOutputHandler]:
        """选择最佳的输出处理器
        
        Args:
            file_path: 文件路径
            file_size: 文件大小
            **kwargs: 额外参数
            
        Returns:
            最佳处理器
        """
        # 策略1: 小文件优先使用Base64
        if file_size <= 1024 * 1024:  # 1MB
            if self.base64_handler.can_handle(file_path, **kwargs):
                return self.base64_handler
        
        # 策略2: 中等文件使用文件路径
        if file_size <= 50 * 1024 * 1024:  # 50MB
            if self.file_path_handler.can_handle(file_path, **kwargs):
                return self.file_path_handler
        
        # 策略3: 大文件使用URL
        if self.url_handler.can_handle(file_path, **kwargs):
            return self.url_handler
        
        # 回退策略：按优先级顺序尝试
        for handler in self.handlers:
            if handler.can_handle(file_path, **kwargs):
                return handler
        
        return None

class OutputModeHandler:
    """输出模式管理器"""
    
    def __init__(self, security_validator: Optional[FileSecurityValidator] = None):
        """初始化输出模式管理器
        
        Args:
            security_validator: 安全验证器
        """
        self.security_validator = security_validator or FileSecurityValidator()
        
        # 初始化各种处理器
        self.handlers = {
            OutputMode.FILE_PATH: FilePathOutputHandler(self.security_validator),
            OutputMode.BASE64: Base64OutputHandler(self.security_validator),
            OutputMode.URL: URLOutputHandler(self.security_validator),
            OutputMode.AUTO: AutoOutputHandler(self.security_validator)
        }
        
        logger.info("输出模式管理器初始化完成")
    
    def process_file(self, file_path: Union[str, Path], mode: Union[str, OutputMode],
                    **kwargs) -> OutputResult:
        """处理文件输出
        
        Args:
            file_path: 文件路径
            mode: 输出模式
            **kwargs: 额外参数
            
        Returns:
            输出结果
            
        Raises:
            ValueError: 不支持的输出模式
            OSError: 文件处理错误
        """
        # 转换模式类型
        if isinstance(mode, str):
            try:
                mode = OutputMode(mode)
            except ValueError:
                raise ValueError(f"不支持的输出模式: {mode}")
        
        # 获取对应的处理器
        handler = self.handlers.get(mode)
        if not handler:
            raise ValueError(f"未找到输出模式处理器: {mode}")
        
        # 检查是否可以处理
        if not handler.can_handle(file_path, **kwargs):
            raise OSError(f"处理器无法处理该文件: {file_path}")
        
        # 处理文件
        try:
            result = handler.process(file_path, **kwargs)
            logger.info("文件输出处理完成", 
                       path=str(file_path), mode=mode.value)
            return result
            
        except Exception as e:
            logger.error("文件输出处理失败", 
                        path=str(file_path), mode=mode.value, error=str(e))
            raise
    
    def get_supported_modes(self) -> List[OutputMode]:
        """获取支持的输出模式列表
        
        Returns:
            支持的输出模式列表
        """
        return list(self.handlers.keys())
    
    def stop_services(self) -> None:
        """停止相关服务"""
        # 停止URL服务器
        url_handler = self.handlers.get(OutputMode.URL)
        if url_handler and isinstance(url_handler, URLOutputHandler):
            url_handler.stop_server()
        
        logger.info("输出模式服务已停止")
    
    def __del__(self):
        """析构函数，确保服务停止"""
        try:
            self.stop_services()
        except Exception:
            pass