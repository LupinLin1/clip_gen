"""
文件安全系统

提供文件路径验证、访问控制和安全检查功能。
"""

import os
import stat
from pathlib import Path
from typing import Set, List, Optional, Union, Dict, Any
try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False
    magic = None
import mimetypes

from ..logger import get_logger
from ..config import get_config
from ..exceptions import ValidationError

logger = get_logger(__name__)

class SecurityError(ValidationError):
    """安全相关错误"""
    pass

class FileSecurityValidator:
    """文件安全验证器
    
    提供文件路径验证、类型检查、大小限制和访问控制功能。
    """
    
    def __init__(self):
        """初始化安全验证器"""
        config = get_config()
        
        # 安全配置
        self.max_file_size = config.file.max_file_size
        self.allowed_extensions = set(config.file.allowed_formats)
        self.temp_dir = Path(config.file.temp_dir).resolve()
        
        # 允许的基础路径（沙箱）
        self.allowed_base_paths: Set[Path] = {self.temp_dir}
        
        # 危险的文件扩展名
        self.dangerous_extensions = {
            'exe', 'bat', 'cmd', 'com', 'pif', 'scr', 'vbs', 'js', 'jar', 
            'msi', 'dll', 'sh', 'ps1', 'php', 'asp', 'jsp', 'py'
        }
        
        # 允许的MIME类型模式
        self.allowed_mime_patterns = {
            'image/*', 'video/*', 'audio/*', 'text/plain', 'text/csv',
            'application/json', 'application/yaml', 'application/x-yaml'
        }
        
        # 文件魔数检查（如果可用）
        if HAS_MAGIC:
            try:
                self.magic_mime = magic.Magic(mime=True)
            except Exception:
                self.magic_mime = None
        else:
            self.magic_mime = None
        
        logger.info("文件安全验证器初始化完成", 
                   temp_dir=str(self.temp_dir),
                   max_file_size=self.max_file_size)
    
    def add_allowed_path(self, path: Union[str, Path]) -> None:
        """添加允许的基础路径
        
        Args:
            path: 允许的路径
        """
        resolved_path = Path(path).resolve()
        self.allowed_base_paths.add(resolved_path)
        logger.info("添加允许的基础路径", path=str(resolved_path))
    
    def validate_path(self, file_path: Union[str, Path], 
                     allow_create: bool = False) -> Path:
        """验证文件路径的安全性
        
        Args:
            file_path: 文件路径
            allow_create: 是否允许创建不存在的文件
            
        Returns:
            规范化的安全路径
            
        Raises:
            SecurityError: 路径不安全
        """
        try:
            # 转换为Path对象并解析
            path = Path(file_path).resolve()
            
            # 检查路径遍历攻击
            self._check_path_traversal(path)
            
            # 检查是否在允许的路径范围内
            self._check_allowed_paths(path)
            
            # 检查文件是否存在（如果需要）
            if not allow_create and not path.exists():
                raise SecurityError(f"文件不存在: {path}")
            
            # 如果文件存在，进行额外检查
            if path.exists():
                self._check_file_permissions(path)
            
            logger.debug("路径验证通过", path=str(path))
            return path
            
        except SecurityError:
            raise
        except Exception as e:
            logger.error("路径验证失败", path=str(file_path), error=str(e))
            raise SecurityError(f"路径验证失败: {e}")
    
    def validate_file_type(self, file_path: Union[str, Path]) -> str:
        """验证文件类型
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件的MIME类型
            
        Raises:
            SecurityError: 文件类型不安全或不支持
        """
        path = Path(file_path)
        
        if not path.exists():
            raise SecurityError(f"文件不存在: {path}")
        
        try:
            # 检查文件扩展名
            extension = path.suffix.lower().lstrip('.')
            if extension in self.dangerous_extensions:
                raise SecurityError(f"危险的文件类型: .{extension}")
            
            if extension and extension not in self.allowed_extensions:
                raise SecurityError(f"不支持的文件扩展名: .{extension}")
            
            # 使用python-magic进行文件类型检测（如果可用）
            if self.magic_mime:
                try:
                    mime_type = self.magic_mime.from_file(str(path))
                except Exception:
                    # 回退到mimetypes模块
                    mime_type, _ = mimetypes.guess_type(str(path))
                    if not mime_type:
                        mime_type = "application/octet-stream"
            else:
                # 直接使用mimetypes模块
                mime_type, _ = mimetypes.guess_type(str(path))
                if not mime_type:
                    mime_type = "application/octet-stream"
            
            # 验证MIME类型
            if not self._is_mime_type_allowed(mime_type):
                raise SecurityError(f"不支持的MIME类型: {mime_type}")
            
            # 额外的文件内容验证
            self._validate_file_content(path, mime_type)
            
            logger.debug("文件类型验证通过", path=str(path), mime_type=mime_type)
            return mime_type
            
        except SecurityError:
            raise
        except Exception as e:
            logger.error("文件类型验证失败", path=str(path), error=str(e))
            raise SecurityError(f"文件类型验证失败: {e}")
    
    def validate_file_size(self, file_path: Union[str, Path]) -> int:
        """验证文件大小
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件大小（字节）
            
        Raises:
            SecurityError: 文件过大
        """
        path = Path(file_path)
        
        if not path.exists():
            raise SecurityError(f"文件不存在: {path}")
        
        try:
            file_size = path.stat().st_size
            
            if file_size > self.max_file_size:
                raise SecurityError(
                    f"文件过大: {file_size} bytes > {self.max_file_size} bytes"
                )
            
            if file_size == 0:
                logger.warning("文件大小为0", path=str(path))
            
            logger.debug("文件大小验证通过", path=str(path), size=file_size)
            return file_size
            
        except SecurityError:
            raise
        except Exception as e:
            logger.error("文件大小验证失败", path=str(path), error=str(e))
            raise SecurityError(f"文件大小验证失败: {e}")
    
    def validate_file(self, file_path: Union[str, Path], 
                     allow_create: bool = False) -> Dict[str, Any]:
        """完整的文件安全验证
        
        Args:
            file_path: 文件路径
            allow_create: 是否允许创建不存在的文件
            
        Returns:
            包含验证结果的字典
            
        Raises:
            SecurityError: 文件不安全
        """
        try:
            # 验证路径
            safe_path = self.validate_path(file_path, allow_create)
            
            result = {
                "path": str(safe_path),
                "safe": True,
                "exists": safe_path.exists()
            }
            
            # 如果文件存在，进行进一步验证
            if safe_path.exists():
                # 验证文件大小
                file_size = self.validate_file_size(safe_path)
                result["size"] = file_size
                
                # 验证文件类型
                mime_type = self.validate_file_type(safe_path)
                result["mime_type"] = mime_type
                result["extension"] = safe_path.suffix.lower()
            
            logger.info("文件安全验证通过", **result)
            return result
            
        except SecurityError as e:
            logger.error("文件安全验证失败", path=str(file_path), error=str(e))
            raise
        except Exception as e:
            logger.error("文件验证过程中发生错误", path=str(file_path), error=str(e))
            raise SecurityError(f"文件验证失败: {e}")
    
    def _check_path_traversal(self, path: Path) -> None:
        """检查路径遍历攻击
        
        Args:
            path: 要检查的路径
            
        Raises:
            SecurityError: 检测到路径遍历攻击
        """
        # 检查路径组件中是否包含危险字符
        dangerous_components = {'.', '..', '~'}
        path_parts = path.parts
        
        for part in path_parts:
            if part in dangerous_components:
                raise SecurityError(f"检测到路径遍历攻击: {path}")
        
        # 检查绝对路径是否试图访问系统敏感目录
        sensitive_dirs = {'/etc', '/proc', '/sys', '/dev', '/boot', '/root'}
        path_str = str(path).lower()
        
        for sensitive_dir in sensitive_dirs:
            if path_str.startswith(sensitive_dir):
                raise SecurityError(f"尝试访问敏感目录: {path}")
    
    def _check_allowed_paths(self, path: Path) -> None:
        """检查路径是否在允许的范围内
        
        Args:
            path: 要检查的路径
            
        Raises:
            SecurityError: 路径不在允许的范围内
        """
        for allowed_path in self.allowed_base_paths:
            try:
                path.relative_to(allowed_path)
                return  # 路径在允许的范围内
            except ValueError:
                continue
        
        # 如果没有找到匹配的允许路径
        raise SecurityError(f"路径不在允许的范围内: {path}")
    
    def _check_file_permissions(self, path: Path) -> None:
        """检查文件权限
        
        Args:
            path: 文件路径
            
        Raises:
            SecurityError: 文件权限不当
        """
        try:
            file_stat = path.stat()
            
            # 检查是否为符号链接（可能的安全风险）
            if path.is_symlink():
                logger.warning("检测到符号链接", path=str(path))
                # 可以选择是否允许符号链接
                # raise SecurityError(f"不允许符号链接: {path}")
            
            # 检查文件权限（避免过于宽松的权限）
            mode = file_stat.st_mode
            if stat.S_ISREG(mode):
                # 检查文件是否对其他用户可写
                if mode & stat.S_IWOTH:
                    logger.warning("文件对其他用户可写", path=str(path))
            
        except Exception as e:
            logger.error("检查文件权限失败", path=str(path), error=str(e))
            raise SecurityError(f"无法检查文件权限: {e}")
    
    def _is_mime_type_allowed(self, mime_type: str) -> bool:
        """检查MIME类型是否被允许
        
        Args:
            mime_type: MIME类型
            
        Returns:
            是否允许
        """
        if not mime_type:
            return False
        
        for pattern in self.allowed_mime_patterns:
            if pattern.endswith('*'):
                # 通配符匹配
                prefix = pattern[:-1]
                if mime_type.startswith(prefix):
                    return True
            else:
                # 精确匹配
                if mime_type == pattern:
                    return True
        
        return False
    
    def _validate_file_content(self, path: Path, mime_type: str) -> None:
        """验证文件内容的安全性
        
        Args:
            path: 文件路径
            mime_type: MIME类型
            
        Raises:
            SecurityError: 文件内容不安全
        """
        try:
            if mime_type.startswith('text/'):
                # 对文本文件进行额外检查
                self._validate_text_file(path)
            elif mime_type.startswith('image/'):
                # 对图像文件进行基本验证
                self._validate_image_file(path)
        except SecurityError:
            raise
        except Exception as e:
            logger.warning("文件内容验证时发生错误", path=str(path), error=str(e))
            # 不抛出异常，仅记录警告
    
    def _validate_text_file(self, path: Path) -> None:
        """验证文本文件内容
        
        Args:
            path: 文件路径
            
        Raises:
            SecurityError: 文本文件内容不安全
        """
        try:
            # 读取文件开头部分进行检查
            with open(path, 'rb') as f:
                header = f.read(1024)  # 读取前1KB
            
            # 检查是否包含可执行文件的特征
            if header.startswith(b'MZ') or header.startswith(b'\x7fELF'):
                raise SecurityError("文本文件包含可执行文件特征")
            
            # 检查是否包含脚本解释器指令
            try:
                text_header = header.decode('utf-8', errors='ignore')
                dangerous_patterns = ['#!/bin/', '#!python', '#!node', '<?php']
                for pattern in dangerous_patterns:
                    if pattern in text_header:
                        logger.warning("文本文件包含脚本解释器指令", 
                                     path=str(path), pattern=pattern)
                        # 可以选择是否阻止，这里仅警告
                        break
            except Exception:
                pass
            
        except SecurityError:
            raise
        except Exception as e:
            logger.warning("验证文本文件时发生错误", path=str(path), error=str(e))
    
    def _validate_image_file(self, path: Path) -> None:
        """验证图像文件
        
        Args:
            path: 文件路径
            
        Raises:
            SecurityError: 图像文件不安全
        """
        try:
            # 读取文件头部进行基本检查
            with open(path, 'rb') as f:
                header = f.read(32)
            
            # 检查常见图像格式的文件头
            image_signatures = {
                b'\xff\xd8\xff': 'JPEG',
                b'\x89PNG\r\n\x1a\n': 'PNG',
                b'GIF87a': 'GIF',
                b'GIF89a': 'GIF',
                b'RIFF': 'WEBP',  # WEBP文件以RIFF开头
                b'BM': 'BMP'
            }
            
            valid_signature = False
            for signature, format_name in image_signatures.items():
                if header.startswith(signature):
                    valid_signature = True
                    logger.debug("检测到图像格式", path=str(path), format=format_name)
                    break
            
            if not valid_signature:
                logger.warning("图像文件签名不匹配", path=str(path))
                # 可以选择是否严格验证
                # raise SecurityError("图像文件签名不匹配")
            
        except SecurityError:
            raise
        except Exception as e:
            logger.warning("验证图像文件时发生错误", path=str(path), error=str(e))

class FileAccessController:
    """文件访问控制器
    
    提供基于角色和权限的文件访问控制。
    """
    
    def __init__(self):
        """初始化访问控制器"""
        self.permissions: Dict[str, Set[str]] = {}
        self.roles: Dict[str, Set[str]] = {}
        
        # 默认权限
        self.default_permissions = {'read', 'write', 'delete'}
        
        logger.info("文件访问控制器初始化完成")
    
    def add_permission(self, user_id: str, permission: str) -> None:
        """为用户添加权限
        
        Args:
            user_id: 用户ID
            permission: 权限名称
        """
        if user_id not in self.permissions:
            self.permissions[user_id] = set()
        self.permissions[user_id].add(permission)
        
        logger.info("添加用户权限", user_id=user_id, permission=permission)
    
    def remove_permission(self, user_id: str, permission: str) -> None:
        """移除用户权限
        
        Args:
            user_id: 用户ID
            permission: 权限名称
        """
        if user_id in self.permissions:
            self.permissions[user_id].discard(permission)
            logger.info("移除用户权限", user_id=user_id, permission=permission)
    
    def check_permission(self, user_id: str, permission: str) -> bool:
        """检查用户权限
        
        Args:
            user_id: 用户ID
            permission: 权限名称
            
        Returns:
            是否有权限
        """
        user_permissions = self.permissions.get(user_id, self.default_permissions)
        has_permission = permission in user_permissions
        
        logger.debug("检查用户权限", 
                    user_id=user_id, permission=permission, has_permission=has_permission)
        
        return has_permission
    
    def require_permission(self, user_id: str, permission: str) -> None:
        """要求用户具有特定权限
        
        Args:
            user_id: 用户ID
            permission: 权限名称
            
        Raises:
            SecurityError: 权限不足
        """
        if not self.check_permission(user_id, permission):
            raise SecurityError(f"权限不足: 用户 {user_id} 缺少 {permission} 权限")