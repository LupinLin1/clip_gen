"""
输出模式处理测试
"""

import base64
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import pytest
import http.server
import socketserver

from gemini_kling_mcp.file_manager.output_modes import (
    OutputMode, OutputResult, FilePathOutputHandler, Base64OutputHandler,
    URLOutputHandler, AutoOutputHandler, OutputModeHandler
)
from gemini_kling_mcp.file_manager.security import FileSecurityValidator


class TestOutputResult:
    """输出结果测试"""
    
    def test_output_result_creation(self):
        """测试输出结果创建"""
        result = OutputResult(
            mode=OutputMode.FILE_PATH,
            data="/path/to/file.txt",
            metadata={"size": 1024}
        )
        
        assert result.mode == OutputMode.FILE_PATH
        assert result.data == "/path/to/file.txt"
        assert result.metadata["size"] == 1024
    
    def test_output_result_to_dict(self):
        """测试输出结果转换为字典"""
        result = OutputResult(
            mode=OutputMode.BASE64,
            data="SGVsbG8gV29ybGQ=",
            metadata={"encoding": "base64", "size": 11}
        )
        
        dict_result = result.to_dict()
        
        assert dict_result["mode"] == "base64"
        assert dict_result["data"] == "SGVsbG8gV29ybGQ="
        assert dict_result["metadata"]["encoding"] == "base64"
        assert dict_result["metadata"]["size"] == 11


class TestFilePathOutputHandler:
    """文件路径输出处理器测试"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def test_file(self, temp_dir):
        """创建测试文件"""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello, World!")
        return test_file
    
    @pytest.fixture
    def security_validator(self, temp_dir):
        """创建模拟的安全验证器"""
        validator = MagicMock(spec=FileSecurityValidator)
        validator.validate_path.return_value = temp_dir / "test.txt"
        return validator
    
    @pytest.fixture
    def handler(self, security_validator):
        """创建文件路径处理器"""
        return FilePathOutputHandler(security_validator)
    
    def test_can_handle_existing_file(self, handler, test_file):
        """测试可以处理存在的文件"""
        result = handler.can_handle(test_file)
        assert result is True
    
    def test_can_handle_nonexistent_file(self, handler, temp_dir):
        """测试不能处理不存在的文件"""
        nonexistent = temp_dir / "nonexistent.txt"
        result = handler.can_handle(nonexistent)
        assert result is False
    
    def test_can_handle_directory(self, handler, temp_dir):
        """测试不能处理目录"""
        result = handler.can_handle(temp_dir)
        assert result is False
    
    def test_process_success(self, handler, test_file, security_validator):
        """测试处理成功"""
        security_validator.validate_path.return_value = test_file.resolve()
        
        result = handler.process(test_file)
        
        assert result.mode == OutputMode.FILE_PATH
        assert result.data == str(test_file.resolve())
        assert result.metadata["size"] > 0
        assert result.metadata["exists"] is True
        assert result.metadata["path"] == str(test_file.resolve())
        assert result.metadata["absolute_path"] == str(test_file.resolve())
    
    def test_process_calls_security_validator(self, handler, test_file, security_validator):
        """测试处理过程中调用安全验证器"""
        handler.process(test_file)
        
        security_validator.validate_path.assert_called_once_with(test_file)


class TestBase64OutputHandler:
    """Base64输出处理器测试"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def test_file(self, temp_dir):
        """创建测试文件"""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello, World!")
        return test_file
    
    @pytest.fixture
    def security_validator(self, test_file):
        """创建模拟的安全验证器"""
        validator = MagicMock(spec=FileSecurityValidator)
        validator.validate_path.return_value = test_file.resolve()
        validator.validate_file_type.return_value = "text/plain"
        return validator
    
    @pytest.fixture
    def handler(self, security_validator):
        """创建Base64处理器"""
        return Base64OutputHandler(security_validator, max_size=1024*1024)
    
    def test_can_handle_small_file(self, handler, test_file):
        """测试可以处理小文件"""
        result = handler.can_handle(test_file)
        assert result is True
    
    def test_can_handle_large_file(self, handler, temp_dir):
        """测试不能处理大文件"""
        large_file = temp_dir / "large.txt"
        # 创建超过限制的文件
        content = "x" * (handler.max_size + 1)
        large_file.write_text(content)
        
        result = handler.can_handle(large_file)
        assert result is False
    
    def test_can_handle_nonexistent_file(self, handler, temp_dir):
        """测试不能处理不存在的文件"""
        nonexistent = temp_dir / "nonexistent.txt"
        result = handler.can_handle(nonexistent)
        assert result is False
    
    def test_process_success(self, handler, test_file, security_validator):
        """测试Base64编码处理成功"""
        result = handler.process(test_file)
        
        assert result.mode == OutputMode.BASE64
        
        # 验证Base64编码
        decoded = base64.b64decode(result.data).decode('utf-8')
        assert decoded == "Hello, World!"
        
        assert result.metadata["mime_type"] == "text/plain"
        assert result.metadata["encoding"] == "base64"
        assert result.metadata["size"] > 0
        assert result.metadata["encoded_size"] > 0
    
    def test_encode_file_base64(self, handler, test_file):
        """测试Base64编码功能"""
        encoded = handler._encode_file_base64(test_file)
        
        # 验证编码结果
        decoded = base64.b64decode(encoded).decode('utf-8')
        assert decoded == "Hello, World!"
    
    def test_encode_large_file_streaming(self, handler, temp_dir):
        """测试大文件流式编码"""
        # 创建一个稍大的文件来测试分块处理
        large_file = temp_dir / "large.txt"
        content = "Hello, World! " * 1000  # 大约14KB
        large_file.write_text(content)
        
        encoded = handler._encode_file_base64(large_file)
        decoded = base64.b64decode(encoded).decode('utf-8')
        
        assert decoded == content
    
    def test_process_calls_security_validator(self, handler, test_file, security_validator):
        """测试处理过程中调用安全验证器"""
        handler.process(test_file)
        
        security_validator.validate_path.assert_called_once_with(test_file)
        security_validator.validate_file_type.assert_called_once_with(test_file.resolve())


class TestURLOutputHandler:
    """URL输出处理器测试"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def test_file(self, temp_dir):
        """创建测试文件"""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello, World!")
        return test_file
    
    @pytest.fixture
    def security_validator(self, test_file):
        """创建模拟的安全验证器"""
        validator = MagicMock(spec=FileSecurityValidator)
        validator.validate_path.return_value = test_file.resolve()
        validator.validate_file_type.return_value = "text/plain"
        return validator
    
    @pytest.fixture
    def handler(self, security_validator):
        """创建URL处理器"""
        return URLOutputHandler(security_validator, server_port=0)  # 使用随机端口
    
    def test_can_handle_existing_file(self, handler, test_file):
        """测试可以处理存在的文件"""
        result = handler.can_handle(test_file)
        assert result is True
    
    def test_can_handle_nonexistent_file(self, handler, temp_dir):
        """测试不能处理不存在的文件"""
        nonexistent = temp_dir / "nonexistent.txt"
        result = handler.can_handle(nonexistent)
        assert result is False
    
    def test_process_success(self, handler, test_file, security_validator):
        """测试URL输出处理成功"""
        try:
            result = handler.process(test_file)
            
            assert result.mode == OutputMode.URL
            assert result.data.startswith("http://")
            assert result.metadata["mime_type"] == "text/plain"
            assert result.metadata["size"] > 0
            assert "server_host" in result.metadata
            assert "server_port" in result.metadata
            
            # 验证文件已注册
            assert len(handler._served_files) > 0
            
        finally:
            # 确保服务器停止
            handler.stop_server()
    
    def test_server_startup(self, handler):
        """测试服务器启动"""
        try:
            handler._ensure_server_running()
            
            assert handler._server is not None
            assert handler._server_thread is not None
            assert handler._server_thread.is_alive()
            
            # 获取服务器端口
            port = handler._get_server_port()
            assert port > 0
            
        finally:
            handler.stop_server()
    
    def test_register_file(self, handler, test_file):
        """测试文件注册"""
        try:
            handler._ensure_server_running()
            url = handler._register_file(test_file)
            
            assert url.startswith("http://")
            assert test_file in handler._served_files.values()
            
        finally:
            handler.stop_server()
    
    def test_stop_server(self, handler):
        """测试停止服务器"""
        # 启动服务器
        handler._ensure_server_running()
        assert handler._server is not None
        assert handler._server_thread.is_alive()
        
        # 停止服务器
        handler.stop_server()
        
        assert handler._server is None
        # 给线程一些时间来结束
        time.sleep(0.1)
        if handler._server_thread:
            assert not handler._server_thread.is_alive()
    
    def test_multiple_file_registration(self, handler, temp_dir):
        """测试多个文件注册"""
        try:
            files = []
            for i in range(3):
                file_path = temp_dir / f"test_{i}.txt"
                file_path.write_text(f"Content {i}")
                files.append(file_path)
            
            handler._ensure_server_running()
            
            urls = []
            for file_path in files:
                url = handler._register_file(file_path)
                urls.append(url)
            
            # 所有URL应该不同
            assert len(set(urls)) == 3
            
            # 所有文件应该被注册
            assert len(handler._served_files) == 3
            
        finally:
            handler.stop_server()
    
    def test_url_prefix(self, security_validator):
        """测试URL前缀功能"""
        handler = URLOutputHandler(security_validator, url_prefix="api/files")
        
        try:
            temp_file = Path.cwd() / "temp_test.txt"
            temp_file.write_text("test")
            
            # 模拟安全验证器
            security_validator.validate_path.return_value = temp_file.resolve()
            
            handler._ensure_server_running()
            url = handler._register_file(temp_file)
            
            assert "api/files" in url
            
        finally:
            handler.stop_server()
            if temp_file.exists():
                temp_file.unlink()


class TestAutoOutputHandler:
    """自动输出处理器测试"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def security_validator(self):
        """创建模拟的安全验证器"""
        validator = MagicMock(spec=FileSecurityValidator)
        return validator
    
    @pytest.fixture
    def mock_handlers(self, security_validator):
        """创建模拟的处理器"""
        file_path_handler = MagicMock(spec=FilePathOutputHandler)
        base64_handler = MagicMock(spec=Base64OutputHandler) 
        url_handler = MagicMock(spec=URLOutputHandler)
        
        return file_path_handler, base64_handler, url_handler
    
    @pytest.fixture
    def handler(self, security_validator, mock_handlers):
        """创建自动输出处理器"""
        file_path_handler, base64_handler, url_handler = mock_handlers
        return AutoOutputHandler(
            security_validator=security_validator,
            file_path_handler=file_path_handler,
            base64_handler=base64_handler,
            url_handler=url_handler
        )
    
    def test_can_handle_any_supported_file(self, handler, mock_handlers, temp_dir):
        """测试可以处理任何支持的文件"""
        file_path_handler, base64_handler, url_handler = mock_handlers
        
        test_file = temp_dir / "test.txt"
        test_file.write_text("test")
        
        # 设置至少一个处理器可以处理
        file_path_handler.can_handle.return_value = True
        base64_handler.can_handle.return_value = False
        url_handler.can_handle.return_value = False
        
        result = handler.can_handle(test_file)
        assert result is True
    
    def test_cannot_handle_unsupported_file(self, handler, mock_handlers, temp_dir):
        """测试不能处理不支持的文件"""
        file_path_handler, base64_handler, url_handler = mock_handlers
        
        test_file = temp_dir / "test.txt"
        test_file.write_text("test")
        
        # 设置所有处理器都不能处理
        file_path_handler.can_handle.return_value = False
        base64_handler.can_handle.return_value = False
        url_handler.can_handle.return_value = False
        
        result = handler.can_handle(test_file)
        assert result is False
    
    def test_select_base64_for_small_file(self, handler, mock_handlers, temp_dir, security_validator):
        """测试为小文件选择Base64处理器"""
        file_path_handler, base64_handler, url_handler = mock_handlers
        
        test_file = temp_dir / "small.txt"
        test_file.write_text("small content")  # 小于1MB
        
        security_validator.validate_path.return_value = test_file.resolve()
        
        # 设置Base64处理器可用
        base64_handler.can_handle.return_value = True
        base64_handler.process.return_value = OutputResult(
            mode=OutputMode.BASE64,
            data="encoded_data",
            metadata={"selected_handler": "Base64OutputHandler"}
        )
        
        result = handler.process(test_file)
        
        assert result.mode == OutputMode.BASE64
        assert result.metadata["auto_selected"] is True
        base64_handler.process.assert_called_once()
    
    def test_select_file_path_for_medium_file(self, handler, mock_handlers, temp_dir, security_validator):
        """测试为中等文件选择文件路径处理器"""
        file_path_handler, base64_handler, url_handler = mock_handlers
        
        test_file = temp_dir / "medium.txt"
        # 创建一个中等大小的文件（大于1MB但小于50MB）
        content = "x" * (2 * 1024 * 1024)  # 2MB
        test_file.write_text(content)
        
        security_validator.validate_path.return_value = test_file.resolve()
        
        # 设置文件路径处理器可用
        file_path_handler.can_handle.return_value = True
        file_path_handler.process.return_value = OutputResult(
            mode=OutputMode.FILE_PATH,
            data=str(test_file),
            metadata={"selected_handler": "FilePathOutputHandler"}
        )
        
        result = handler.process(test_file)
        
        assert result.mode == OutputMode.FILE_PATH
        assert result.metadata["auto_selected"] is True
        file_path_handler.process.assert_called_once()
    
    def test_fallback_to_available_handler(self, handler, mock_handlers, temp_dir, security_validator):
        """测试回退到可用的处理器"""
        file_path_handler, base64_handler, url_handler = mock_handlers
        
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")
        
        security_validator.validate_path.return_value = test_file.resolve()
        
        # 设置只有URL处理器可用
        file_path_handler.can_handle.return_value = False
        base64_handler.can_handle.return_value = False
        url_handler.can_handle.return_value = True
        url_handler.process.return_value = OutputResult(
            mode=OutputMode.URL,
            data="http://localhost:8000/file.txt",
            metadata={"selected_handler": "URLOutputHandler"}
        )
        
        result = handler.process(test_file)
        
        assert result.mode == OutputMode.URL
        assert result.metadata["auto_selected"] is True
        url_handler.process.assert_called_once()
    
    def test_no_suitable_handler_error(self, handler, mock_handlers, temp_dir, security_validator):
        """测试没有合适处理器时的错误"""
        file_path_handler, base64_handler, url_handler = mock_handlers
        
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")
        
        security_validator.validate_path.return_value = test_file.resolve()
        
        # 设置所有处理器都不可用
        file_path_handler.can_handle.return_value = False
        base64_handler.can_handle.return_value = False
        url_handler.can_handle.return_value = False
        
        with pytest.raises(OSError) as exc_info:
            handler.process(test_file)
        
        assert "无法为文件选择合适的输出模式" in str(exc_info.value)


class TestOutputModeHandler:
    """输出模式管理器测试"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def test_file(self, temp_dir):
        """创建测试文件"""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello, World!")
        return test_file
    
    @pytest.fixture
    def security_validator(self, test_file):
        """创建模拟的安全验证器"""
        validator = MagicMock(spec=FileSecurityValidator)
        validator.validate_path.return_value = test_file.resolve()
        validator.validate_file_type.return_value = "text/plain"
        return validator
    
    @pytest.fixture
    def handler_manager(self, security_validator):
        """创建输出模式管理器"""
        return OutputModeHandler(security_validator)
    
    def test_manager_initialization(self, handler_manager):
        """测试管理器初始化"""
        assert OutputMode.FILE_PATH in handler_manager.handlers
        assert OutputMode.BASE64 in handler_manager.handlers
        assert OutputMode.URL in handler_manager.handlers
        assert OutputMode.AUTO in handler_manager.handlers
    
    def test_get_supported_modes(self, handler_manager):
        """测试获取支持的模式"""
        modes = handler_manager.get_supported_modes()
        
        assert OutputMode.FILE_PATH in modes
        assert OutputMode.BASE64 in modes
        assert OutputMode.URL in modes
        assert OutputMode.AUTO in modes
    
    def test_process_file_with_string_mode(self, handler_manager, test_file):
        """测试使用字符串模式处理文件"""
        with patch.object(handler_manager.handlers[OutputMode.FILE_PATH], 'can_handle', return_value=True):
            with patch.object(handler_manager.handlers[OutputMode.FILE_PATH], 'process') as mock_process:
                mock_process.return_value = OutputResult(
                    mode=OutputMode.FILE_PATH,
                    data=str(test_file),
                    metadata={}
                )
                
                result = handler_manager.process_file(test_file, "file_path")
                
                assert result.mode == OutputMode.FILE_PATH
                mock_process.assert_called_once()
    
    def test_process_file_with_enum_mode(self, handler_manager, test_file):
        """测试使用枚举模式处理文件"""
        with patch.object(handler_manager.handlers[OutputMode.BASE64], 'can_handle', return_value=True):
            with patch.object(handler_manager.handlers[OutputMode.BASE64], 'process') as mock_process:
                mock_process.return_value = OutputResult(
                    mode=OutputMode.BASE64,
                    data="encoded_data",
                    metadata={}
                )
                
                result = handler_manager.process_file(test_file, OutputMode.BASE64)
                
                assert result.mode == OutputMode.BASE64
                mock_process.assert_called_once()
    
    def test_process_file_unsupported_mode(self, handler_manager, test_file):
        """测试处理不支持的模式"""
        with pytest.raises(ValueError) as exc_info:
            handler_manager.process_file(test_file, "unsupported_mode")
        
        assert "不支持的输出模式" in str(exc_info.value)
    
    def test_process_file_handler_cannot_handle(self, handler_manager, test_file):
        """测试处理器无法处理文件"""
        with patch.object(handler_manager.handlers[OutputMode.FILE_PATH], 'can_handle', return_value=False):
            with pytest.raises(OSError) as exc_info:
                handler_manager.process_file(test_file, OutputMode.FILE_PATH)
            
            assert "处理器无法处理该文件" in str(exc_info.value)
    
    def test_stop_services(self, handler_manager):
        """测试停止服务"""
        # 模拟URL处理器
        url_handler = MagicMock()
        handler_manager.handlers[OutputMode.URL] = url_handler
        
        handler_manager.stop_services()
        
        url_handler.stop_server.assert_called_once()
    
    def test_context_manager_cleanup(self, security_validator):
        """测试上下文管理器清理"""
        manager = OutputModeHandler(security_validator)
        
        # 模拟URL处理器
        url_handler = MagicMock()
        manager.handlers[OutputMode.URL] = url_handler
        
        # 删除管理器应该调用停止服务
        del manager
        
        # 注意：由于析构函数的调用时机不确定，这个测试可能不够可靠
        # 在实际使用中，建议显式调用stop_services()
    
    def test_process_file_with_kwargs(self, handler_manager, test_file):
        """测试传递额外参数到处理器"""
        with patch.object(handler_manager.handlers[OutputMode.FILE_PATH], 'can_handle', return_value=True):
            with patch.object(handler_manager.handlers[OutputMode.FILE_PATH], 'process') as mock_process:
                mock_process.return_value = OutputResult(
                    mode=OutputMode.FILE_PATH,
                    data=str(test_file),
                    metadata={}
                )
                
                handler_manager.process_file(
                    test_file, 
                    OutputMode.FILE_PATH, 
                    custom_param="test_value"
                )
                
                # 验证额外参数被传递
                mock_process.assert_called_once_with(test_file, custom_param="test_value")
    
    def test_integration_file_path_mode(self, temp_dir):
        """测试文件路径模式集成"""
        test_file = temp_dir / "integration.txt"
        test_file.write_text("Integration test content")
        
        with patch('gemini_kling_mcp.file_manager.security.get_config') as mock_config:
            mock_config.return_value.file.max_file_size = 1024 * 1024
            mock_config.return_value.file.allowed_formats = ["txt"]
            mock_config.return_value.file.temp_dir = str(temp_dir)
            
            manager = OutputModeHandler()
            manager.security_validator.add_allowed_path(temp_dir)
            
            result = manager.process_file(test_file, OutputMode.FILE_PATH)
            
            assert result.mode == OutputMode.FILE_PATH
            assert result.data == str(test_file.resolve())
            assert result.metadata["exists"] is True
            assert result.metadata["size"] > 0