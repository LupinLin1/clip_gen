"""
测试日志系统模块
"""

import json
import logging
from io import StringIO
import pytest
from unittest.mock import patch, MagicMock

from src.gemini_kling_mcp.logger import (
    StructuredFormatter, MCPLogger, LoggerManager,
    get_logger, set_log_level, set_service_name
)

class TestStructuredFormatter:
    """测试StructuredFormatter类"""
    
    def test_format_basic_log(self):
        """测试基础日志格式化"""
        formatter = StructuredFormatter("test-service")
        
        # 创建日志记录
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.module = "test_module"
        record.funcName = "test_function"
        
        # 格式化日志
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        # 验证日志结构
        assert log_data["level"] == "INFO"
        assert log_data["service"] == "test-service"
        assert log_data["logger"] == "test.logger"
        assert log_data["message"] == "Test message"
        assert log_data["module"] == "test_module"
        assert log_data["function"] == "test_function"
        assert log_data["line"] == 42
        assert "timestamp" in log_data
    
    def test_format_with_exception(self):
        """测试包含异常的日志格式化"""
        formatter = StructuredFormatter()
        
        # 创建异常
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        
        # 创建日志记录
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="/test/path.py",
            lineno=42,
            msg="Error occurred",
            args=(),
            exc_info=exc_info
        )
        record.module = "test_module"
        record.funcName = "test_function"
        
        # 格式化日志
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        # 验证异常信息
        assert "exception" in log_data
        assert log_data["exception"]["type"] == "ValueError"
        assert log_data["exception"]["message"] == "Test error"
        assert isinstance(log_data["exception"]["traceback"], list)
    
    def test_format_with_extra_data(self):
        """测试包含额外数据的日志格式化"""
        formatter = StructuredFormatter()
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.module = "test_module"
        record.funcName = "test_function"
        record.extra_data = {"key": "value", "number": 123}
        record.request_id = "req-123"
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        # 验证额外数据
        assert log_data["data"] == {"key": "value", "number": 123}
        assert log_data["request_id"] == "req-123"

class TestMCPLogger:
    """测试MCPLogger类"""
    
    def test_logger_initialization(self):
        """测试日志器初始化"""
        logger = MCPLogger("test.logger", "DEBUG")
        assert logger.logger.name == "test.logger"
        assert logger.logger.level == logging.DEBUG
        assert logger.service_name == "gemini-kling-mcp"
        assert logger._request_id is None
    
    def test_set_and_clear_request_id(self):
        """测试设置和清除请求ID"""
        logger = MCPLogger("test.logger")
        
        # 设置请求ID
        logger.set_request_id("req-123")
        assert logger._request_id == "req-123"
        
        # 清除请求ID
        logger.clear_request_id()
        assert logger._request_id is None
    
    def test_log_levels(self):
        """测试不同日志级别"""
        # 使用StringIO捕获输出
        output = StringIO()
        logger = MCPLogger("test.logger", "DEBUG")
        
        # 重定向输出到StringIO
        logger.logger.handlers[0].stream = output
        
        # 测试各种日志级别
        logger.debug("Debug message", key="value")
        logger.info("Info message", key="value")
        logger.warning("Warning message", key="value") 
        logger.error("Error message", key="value")
        logger.critical("Critical message", key="value")
        
        # 获取输出并验证
        output_lines = output.getvalue().strip().split('\n')
        assert len(output_lines) == 5
        
        # 验证每行都是有效的JSON
        for line in output_lines:
            log_data = json.loads(line)
            assert "message" in log_data
            assert "level" in log_data
            assert log_data["data"]["key"] == "value"
    
    def test_exception_logging(self):
        """测试异常日志记录"""
        output = StringIO()
        logger = MCPLogger("test.logger")
        logger.logger.handlers[0].stream = output
        
        # 创建异常并记录
        try:
            raise RuntimeError("Test exception")
        except RuntimeError:
            logger.exception("Exception occurred", context="test")
        
        # 验证输出
        output_line = output.getvalue().strip()
        log_data = json.loads(output_line)
        
        assert log_data["level"] == "ERROR"
        assert "exception" in log_data
        assert log_data["exception"]["type"] == "RuntimeError"
        assert log_data["data"]["context"] == "test"
    
    def test_log_api_call(self):
        """测试API调用日志记录"""
        output = StringIO()
        logger = MCPLogger("test.logger")
        logger.logger.handlers[0].stream = output
        
        logger.log_api_call(
            service="gemini",
            method="generate_text",
            status="success",
            duration=0.5,
            tokens=100
        )
        
        output_line = output.getvalue().strip()
        log_data = json.loads(output_line)
        
        assert "API调用: gemini.generate_text" in log_data["message"]
        assert log_data["data"]["service"] == "gemini"
        assert log_data["data"]["method"] == "generate_text"
        assert log_data["data"]["status"] == "success"
        assert log_data["data"]["duration_ms"] == 500.0
        assert log_data["data"]["tokens"] == 100
    
    def test_log_tool_call(self):
        """测试工具调用日志记录"""
        output = StringIO()
        logger = MCPLogger("test.logger")
        logger.logger.handlers[0].stream = output
        
        logger.log_tool_call(
            tool_name="text_generate",
            parameters={"prompt": "test", "api_key": "secret"},
            status="success",
            duration=1.2
        )
        
        output_line = output.getvalue().strip()
        log_data = json.loads(output_line)
        
        assert "工具调用: text_generate" in log_data["message"]
        assert log_data["data"]["tool"] == "text_generate"
        # 敏感参数应该被过滤
        assert log_data["data"]["parameters"]["prompt"] == "test"
        assert log_data["data"]["parameters"]["api_key"] == "***"
        assert log_data["data"]["duration_ms"] == 1200.0
    
    def test_log_server_event(self):
        """测试服务器事件日志记录"""
        output = StringIO()
        logger = MCPLogger("test.logger")
        logger.logger.handlers[0].stream = output
        
        logger.log_server_event("startup", port=8080, workers=4)
        
        output_line = output.getvalue().strip()
        log_data = json.loads(output_line)
        
        assert "服务器事件: startup" in log_data["message"]
        assert log_data["data"]["event"] == "startup"
        assert log_data["data"]["port"] == 8080
        assert log_data["data"]["workers"] == 4
    
    def test_filter_sensitive_data(self):
        """测试敏感数据过滤"""
        logger = MCPLogger("test.logger")
        
        # 测试数据
        data = {
            "prompt": "Hello world",
            "api_key": "secret123",
            "password": "pass123",
            "token": "token123",
            "config": {
                "auth": "auth123",
                "timeout": 30
            },
            "normal_field": "normal_value"
        }
        
        filtered = logger._filter_sensitive_data(data)
        
        # 验证敏感字段被过滤
        assert filtered["api_key"] == "***"
        assert filtered["password"] == "***"
        assert filtered["token"] == "***"
        assert filtered["config"]["auth"] == "***"
        
        # 验证正常字段保持不变
        assert filtered["prompt"] == "Hello world"
        assert filtered["config"]["timeout"] == 30
        assert filtered["normal_field"] == "normal_value"

class TestLoggerManager:
    """测试LoggerManager类"""
    
    def test_get_logger_creates_new(self):
        """测试获取新日志器"""
        manager = LoggerManager()
        logger = manager.get_logger("test.new", "DEBUG")
        
        assert isinstance(logger, MCPLogger)
        assert logger.logger.name == "test.new"
        assert logger.logger.level == logging.DEBUG
    
    def test_get_logger_returns_existing(self):
        """测试获取已存在的日志器"""
        manager = LoggerManager()
        logger1 = manager.get_logger("test.same")
        logger2 = manager.get_logger("test.same")
        
        # 应该返回同一个实例
        assert logger1 is logger2
    
    def test_set_level_updates_all_loggers(self):
        """测试设置级别更新所有日志器"""
        manager = LoggerManager()
        
        # 创建一些日志器
        logger1 = manager.get_logger("test.1", "INFO")
        logger2 = manager.get_logger("test.2", "DEBUG")
        
        # 设置新级别
        manager.set_level("ERROR")
        
        # 验证级别更新
        assert logger1.logger.level == logging.ERROR
        assert logger2.logger.level == logging.ERROR
    
    def test_set_service_name_recreates_loggers(self):
        """测试设置服务名重新创建日志器"""
        manager = LoggerManager()
        
        # 创建日志器
        logger1 = manager.get_logger("test.1")
        old_service_name = logger1.service_name
        
        # 设置新服务名
        manager.set_service_name("new-service")
        
        # 获取同名日志器应该是新实例
        logger2 = manager.get_logger("test.1")
        
        assert logger2.service_name == "new-service"
        assert logger2 is not logger1
    
    def test_tool_count_property(self):
        """测试工具计数属性"""
        manager = LoggerManager()
        
        assert len(manager._loggers) == 0
        
        manager.get_logger("test.1")
        assert len(manager._loggers) == 1
        
        manager.get_logger("test.2")
        assert len(manager._loggers) == 2

def test_global_functions():
    """测试全局函数"""
    # 测试get_logger
    logger = get_logger("test.global")
    assert isinstance(logger, MCPLogger)
    
    # 测试set_log_level
    with patch('src.gemini_kling_mcp.logger.logger_manager') as mock_manager:
        set_log_level("ERROR")
        mock_manager.set_level.assert_called_once_with("ERROR")
    
    # 测试set_service_name
    with patch('src.gemini_kling_mcp.logger.logger_manager') as mock_manager:
        set_service_name("test-service")
        mock_manager.set_service_name.assert_called_once_with("test-service")