"""
文件处理和输出管理系统

提供临时文件管理、多种输出模式、文件类型检测和安全的文件操作。
"""

from .core import FileManager, TempFileManager
from .security import FileSecurityValidator, SecurityError
from .output_modes import OutputModeHandler, OutputMode
from .cache import FileCache, FileCacheManager

__all__ = [
    "FileManager",
    "TempFileManager", 
    "FileSecurityValidator",
    "SecurityError",
    "OutputModeHandler",
    "OutputMode",
    "FileCache",
    "FileCacheManager"
]

__version__ = "1.0.0"