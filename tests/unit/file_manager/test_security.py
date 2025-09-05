"""
文件安全系统测试
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from gemini_kling_mcp.file_manager.security import (
    FileSecurityValidator, SecurityError, FileAccessController
)


class TestFileSecurityValidator:
    """文件安全验证器测试"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def security_validator(self, temp_dir):
        """创建安全验证器实例"""
        with patch('gemini_kling_mcp.file_manager.security.get_config') as mock_config:
            mock_config.return_value.file.max_file_size = 1024 * 1024  # 1MB
            mock_config.return_value.file.allowed_formats = ["txt", "jpg", "png"]
            mock_config.return_value.file.temp_dir = str(temp_dir)
            
            validator = FileSecurityValidator()
            # 添加临时目录到允许的路径
            validator.add_allowed_path(temp_dir)
            return validator
    
    @pytest.fixture
    def test_file(self, temp_dir):
        """创建测试文件"""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello, World!")
        return test_file
    
    def test_validator_initialization(self, temp_dir):
        """测试验证器初始化"""
        with patch('gemini_kling_mcp.file_manager.security.get_config') as mock_config:
            mock_config.return_value.file.max_file_size = 2048
            mock_config.return_value.file.allowed_formats = ["txt", "jpg"]
            mock_config.return_value.file.temp_dir = str(temp_dir)
            
            validator = FileSecurityValidator()
            
            assert validator.max_file_size == 2048
            assert "txt" in validator.allowed_extensions
            assert "jpg" in validator.allowed_extensions
            assert validator.temp_dir in validator.allowed_base_paths
    
    def test_add_allowed_path(self, security_validator, temp_dir):
        """测试添加允许的路径"""
        new_path = temp_dir / "subdir"
        new_path.mkdir()
        
        security_validator.add_allowed_path(new_path)
        
        assert new_path.resolve() in security_validator.allowed_base_paths
    
    def test_validate_path_success(self, security_validator, test_file):
        """测试路径验证成功"""
        result = security_validator.validate_path(test_file)
        
        assert result == test_file.resolve()
    
    def test_validate_path_not_exists_disallowed(self, security_validator, temp_dir):
        """测试验证不存在文件（不允许创建）"""
        nonexistent_file = temp_dir / "nonexistent.txt"
        
        with pytest.raises(SecurityError):
            security_validator.validate_path(nonexistent_file, allow_create=False)
    
    def test_validate_path_not_exists_allowed(self, security_validator, temp_dir):
        """测试验证不存在文件（允许创建）"""
        nonexistent_file = temp_dir / "nonexistent.txt"
        
        result = security_validator.validate_path(nonexistent_file, allow_create=True)
        assert result == nonexistent_file.resolve()
    
    def test_validate_path_traversal_attack(self, security_validator, temp_dir):
        """测试路径遍历攻击防护"""
        # 尝试访问上级目录
        malicious_path = temp_dir / ".." / "sensitive_file.txt"
        
        with pytest.raises(SecurityError) as exc_info:
            security_validator.validate_path(malicious_path)
        
        assert "路径遍历攻击" in str(exc_info.value) or "路径不在允许的范围内" in str(exc_info.value)
    
    def test_validate_path_outside_allowed_paths(self, security_validator):
        """测试访问不被允许路径范围外的文件"""
        outside_file = Path("/etc/passwd")
        
        with pytest.raises(SecurityError) as exc_info:
            security_validator.validate_path(outside_file, allow_create=True)
        
        assert "路径不在允许的范围内" in str(exc_info.value)
    
    def test_validate_path_sensitive_directory(self, security_validator):
        """测试访问系统敏感目录"""
        sensitive_file = Path("/etc/passwd")
        
        with pytest.raises(SecurityError) as exc_info:
            security_validator.validate_path(sensitive_file, allow_create=True)
        
        assert "路径不在允许的范围内" in str(exc_info.value)
    
    def test_validate_file_type_success(self, security_validator, test_file):
        """测试文件类型验证成功"""
        with patch.object(security_validator, 'magic_mime') as mock_magic:
            mock_magic.from_file.return_value = "text/plain"
            
            result = security_validator.validate_file_type(test_file)
            
            assert result == "text/plain"
    
    def test_validate_file_type_dangerous_extension(self, security_validator, temp_dir):
        """测试危险文件扩展名"""
        dangerous_file = temp_dir / "malware.exe"
        dangerous_file.write_bytes(b"fake exe content")
        
        with pytest.raises(SecurityError) as exc_info:
            security_validator.validate_file_type(dangerous_file)
        
        assert "危险的文件类型" in str(exc_info.value)
    
    def test_validate_file_type_unsupported_extension(self, security_validator, temp_dir):
        """测试不支持的文件扩展名"""
        unsupported_file = temp_dir / "test.xyz"
        unsupported_file.write_text("test content")
        
        with pytest.raises(SecurityError) as exc_info:
            security_validator.validate_file_type(unsupported_file)
        
        assert "不支持的文件扩展名" in str(exc_info.value)
    
    def test_validate_file_type_unsupported_mime(self, security_validator, temp_dir):
        """测试不支持的MIME类型"""
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")
        
        with patch.object(security_validator, 'magic_mime') as mock_magic:
            mock_magic.from_file.return_value = "application/x-executable"
            
            with pytest.raises(SecurityError) as exc_info:
                security_validator.validate_file_type(test_file)
            
            assert "不支持的MIME类型" in str(exc_info.value)
    
    def test_validate_file_type_magic_fallback(self, security_validator, test_file):
        """测试magic模块失败后的回退机制"""
        with patch.object(security_validator, 'magic_mime') as mock_magic:
            mock_magic.from_file.side_effect = Exception("Magic failed")
            
            with patch('mimetypes.guess_type') as mock_mimetypes:
                mock_mimetypes.return_value = ("text/plain", None)
                
                result = security_validator.validate_file_type(test_file)
                assert result == "text/plain"
    
    def test_validate_file_size_success(self, security_validator, test_file):
        """测试文件大小验证成功"""
        result = security_validator.validate_file_size(test_file)
        
        assert result == test_file.stat().st_size
        assert result > 0
    
    def test_validate_file_size_too_large(self, security_validator, temp_dir):
        """测试文件过大"""
        large_file = temp_dir / "large.txt"
        # 创建超过限制的文件
        large_content = "x" * (security_validator.max_file_size + 1)
        large_file.write_text(large_content)
        
        with pytest.raises(SecurityError) as exc_info:
            security_validator.validate_file_size(large_file)
        
        assert "文件过大" in str(exc_info.value)
    
    def test_validate_file_size_zero_file(self, security_validator, temp_dir):
        """测试零字节文件"""
        empty_file = temp_dir / "empty.txt"
        empty_file.write_text("")
        
        result = security_validator.validate_file_size(empty_file)
        assert result == 0
    
    def test_validate_file_size_nonexistent(self, security_validator, temp_dir):
        """测试验证不存在文件的大小"""
        nonexistent_file = temp_dir / "nonexistent.txt"
        
        with pytest.raises(SecurityError) as exc_info:
            security_validator.validate_file_size(nonexistent_file)
        
        assert "文件不存在" in str(exc_info.value)
    
    def test_validate_file_complete_success(self, security_validator, test_file):
        """测试完整文件验证成功"""
        with patch.object(security_validator, 'magic_mime') as mock_magic:
            mock_magic.from_file.return_value = "text/plain"
            
            result = security_validator.validate_file(test_file)
            
            assert result["safe"] is True
            assert result["exists"] is True
            assert result["path"] == str(test_file.resolve())
            assert result["size"] > 0
            assert result["mime_type"] == "text/plain"
            assert result["extension"] == ".txt"
    
    def test_validate_file_nonexistent_allow_create(self, security_validator, temp_dir):
        """测试验证不存在文件（允许创建）"""
        nonexistent_file = temp_dir / "new_file.txt"
        
        result = security_validator.validate_file(nonexistent_file, allow_create=True)
        
        assert result["safe"] is True
        assert result["exists"] is False
        assert result["path"] == str(nonexistent_file.resolve())
    
    def test_validate_file_security_failure(self, security_validator):
        """测试文件安全验证失败"""
        malicious_file = Path("/etc/passwd")
        
        with pytest.raises(SecurityError):
            security_validator.validate_file(malicious_file)
    
    def test_is_mime_type_allowed_wildcard(self, security_validator):
        """测试MIME类型通配符匹配"""
        # 图像类型应该被允许
        assert security_validator._is_mime_type_allowed("image/jpeg") is True
        assert security_validator._is_mime_type_allowed("image/png") is True
        
        # 非允许的类型应该被拒绝
        assert security_validator._is_mime_type_allowed("application/x-executable") is False
    
    def test_is_mime_type_allowed_exact(self, security_validator):
        """测试MIME类型精确匹配"""
        assert security_validator._is_mime_type_allowed("text/plain") is True
        assert security_validator._is_mime_type_allowed("application/json") is True
        assert security_validator._is_mime_type_allowed("text/html") is False
    
    def test_validate_text_file_with_script(self, security_validator, temp_dir):
        """测试包含脚本的文本文件"""
        script_file = temp_dir / "script.txt"
        script_file.write_text("#!/bin/bash\necho 'hello'")
        
        # 应该不会抛出异常，只是记录警告
        with patch.object(security_validator, 'magic_mime') as mock_magic:
            mock_magic.from_file.return_value = "text/plain"
            
            security_validator._validate_text_file(script_file)
    
    def test_validate_text_file_with_executable_header(self, security_validator, temp_dir):
        """测试包含可执行文件头的文本文件"""
        fake_exe = temp_dir / "fake.txt"
        fake_exe.write_bytes(b"MZ\x90\x00fake exe header")
        
        with pytest.raises(SecurityError) as exc_info:
            security_validator._validate_text_file(fake_exe)
        
        assert "可执行文件特征" in str(exc_info.value)
    
    def test_validate_image_file_valid_jpeg(self, security_validator, temp_dir):
        """测试有效的JPEG图像文件"""
        jpeg_file = temp_dir / "test.jpg"
        # JPEG文件头
        jpeg_file.write_bytes(b'\xff\xd8\xff\xe0\x00\x10JFIF')
        
        # 应该不抛出异常
        security_validator._validate_image_file(jpeg_file)
    
    def test_validate_image_file_valid_png(self, security_validator, temp_dir):
        """测试有效的PNG图像文件"""
        png_file = temp_dir / "test.png"
        # PNG文件头
        png_file.write_bytes(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR')
        
        # 应该不抛出异常
        security_validator._validate_image_file(png_file)
    
    def test_validate_image_file_invalid_signature(self, security_validator, temp_dir):
        """测试无效图像文件签名"""
        fake_image = temp_dir / "fake.jpg"
        fake_image.write_bytes(b'not a real image file')
        
        # 应该不抛出异常，只是记录警告
        security_validator._validate_image_file(fake_image)
    
    def test_check_file_permissions_symlink(self, security_validator, temp_dir):
        """测试符号链接检查"""
        target_file = temp_dir / "target.txt"
        target_file.write_text("target content")
        
        symlink_file = temp_dir / "link.txt"
        symlink_file.symlink_to(target_file)
        
        # 应该不抛出异常，只是记录警告
        security_validator._check_file_permissions(symlink_file)
    
    def test_check_file_permissions_world_writable(self, security_validator, temp_dir):
        """测试检查全局可写文件权限"""
        test_file = temp_dir / "world_writable.txt"
        test_file.write_text("test content")
        
        # 设置全局可写权限
        test_file.chmod(0o666)
        
        # 应该不抛出异常，只是记录警告
        security_validator._check_file_permissions(test_file)


class TestFileAccessController:
    """文件访问控制器测试"""
    
    @pytest.fixture
    def access_controller(self):
        """创建访问控制器实例"""
        return FileAccessController()
    
    def test_controller_initialization(self, access_controller):
        """测试控制器初始化"""
        assert isinstance(access_controller.permissions, dict)
        assert isinstance(access_controller.roles, dict)
        assert "read" in access_controller.default_permissions
        assert "write" in access_controller.default_permissions
        assert "delete" in access_controller.default_permissions
    
    def test_add_permission(self, access_controller):
        """测试添加用户权限"""
        user_id = "user123"
        permission = "read"
        
        access_controller.add_permission(user_id, permission)
        
        assert user_id in access_controller.permissions
        assert permission in access_controller.permissions[user_id]
    
    def test_add_multiple_permissions(self, access_controller):
        """测试添加多个权限"""
        user_id = "user123"
        
        access_controller.add_permission(user_id, "read")
        access_controller.add_permission(user_id, "write")
        access_controller.add_permission(user_id, "delete")
        
        assert len(access_controller.permissions[user_id]) == 3
        assert "read" in access_controller.permissions[user_id]
        assert "write" in access_controller.permissions[user_id]
        assert "delete" in access_controller.permissions[user_id]
    
    def test_remove_permission(self, access_controller):
        """测试移除用户权限"""
        user_id = "user123"
        
        # 先添加权限
        access_controller.add_permission(user_id, "read")
        access_controller.add_permission(user_id, "write")
        
        # 移除权限
        access_controller.remove_permission(user_id, "read")
        
        assert "read" not in access_controller.permissions[user_id]
        assert "write" in access_controller.permissions[user_id]
    
    def test_remove_permission_nonexistent_user(self, access_controller):
        """测试移除不存在用户的权限"""
        # 应该不抛出异常
        access_controller.remove_permission("nonexistent", "read")
    
    def test_check_permission_with_explicit_permissions(self, access_controller):
        """测试检查显式设置的权限"""
        user_id = "user123"
        
        access_controller.add_permission(user_id, "read")
        
        assert access_controller.check_permission(user_id, "read") is True
        assert access_controller.check_permission(user_id, "write") is False
    
    def test_check_permission_with_default_permissions(self, access_controller):
        """测试检查默认权限"""
        user_id = "new_user"
        
        # 新用户应该有默认权限
        assert access_controller.check_permission(user_id, "read") is True
        assert access_controller.check_permission(user_id, "write") is True
        assert access_controller.check_permission(user_id, "delete") is True
    
    def test_check_permission_nonexistent_permission(self, access_controller):
        """测试检查不存在的权限"""
        user_id = "user123"
        
        assert access_controller.check_permission(user_id, "nonexistent") is False
    
    def test_require_permission_success(self, access_controller):
        """测试要求权限成功"""
        user_id = "user123"
        
        access_controller.add_permission(user_id, "admin")
        
        # 应该不抛出异常
        access_controller.require_permission(user_id, "admin")
    
    def test_require_permission_failure(self, access_controller):
        """测试要求权限失败"""
        user_id = "user123"
        
        # 只添加read权限，但要求admin权限
        access_controller.add_permission(user_id, "read")
        
        with pytest.raises(SecurityError) as exc_info:
            access_controller.require_permission(user_id, "admin")
        
        assert "权限不足" in str(exc_info.value)
        assert user_id in str(exc_info.value)
        assert "admin" in str(exc_info.value)
    
    def test_require_permission_with_default_permissions(self, access_controller):
        """测试使用默认权限要求权限"""
        user_id = "new_user"
        
        # 新用户应该有默认的read权限
        access_controller.require_permission(user_id, "read")
        
        # 但不应该有admin权限
        with pytest.raises(SecurityError):
            access_controller.require_permission(user_id, "admin")
    
    def test_permission_isolation(self, access_controller):
        """测试用户权限隔离"""
        user1 = "user1"
        user2 = "user2"
        
        # 给user1添加admin权限
        access_controller.add_permission(user1, "admin")
        
        # user1应该有admin权限
        assert access_controller.check_permission(user1, "admin") is True
        
        # user2不应该有admin权限
        assert access_controller.check_permission(user2, "admin") is False
    
    def test_multiple_users_same_permission(self, access_controller):
        """测试多个用户相同权限"""
        users = ["user1", "user2", "user3"]
        
        # 给所有用户添加相同权限
        for user in users:
            access_controller.add_permission(user, "special")
        
        # 所有用户都应该有该权限
        for user in users:
            assert access_controller.check_permission(user, "special") is True
    
    def test_permission_overwrite(self, access_controller):
        """测试权限覆盖"""
        user_id = "user123"
        
        # 清空默认权限，设置新权限
        access_controller.permissions[user_id] = {"limited"}
        
        # 用户应该只有limited权限
        assert access_controller.check_permission(user_id, "limited") is True
        assert access_controller.check_permission(user_id, "read") is False
        assert access_controller.check_permission(user_id, "write") is False
    
    def test_empty_permission_set(self, access_controller):
        """测试空权限集合"""
        user_id = "restricted_user"
        
        # 设置空权限集合
        access_controller.permissions[user_id] = set()
        
        # 用户不应该有任何权限
        assert access_controller.check_permission(user_id, "read") is False
        assert access_controller.check_permission(user_id, "write") is False
        assert access_controller.check_permission(user_id, "delete") is False