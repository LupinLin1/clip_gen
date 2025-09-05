"""
测试异常处理模块
"""

import json
import pytest

from src.gemini_kling_mcp.exceptions import (
    MCPError, ConfigurationError, ValidationError,
    AuthenticationError, AuthorizationError, ServiceUnavailableError,
    RateLimitError, TimeoutError, FileProcessingError,
    APIError, GeminiAPIError, KlingAPIError, ToolExecutionError,
    ResourceNotFoundError, ResourceExistsError, NetworkError, ServerError,
    ErrorHandler, ERROR_CODE_MAPPING
)

class TestMCPError:
    """测试MCPError基础异常类"""
    
    def test_basic_creation(self):
        """测试基础异常创建"""
        error = MCPError("Test error")
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.error_code == "MCPError"
        assert error.details == {}
    
    def test_creation_with_all_parameters(self):
        """测试使用所有参数创建异常"""
        details = {"key": "value", "number": 123}
        error = MCPError("Test error", "CUSTOM_ERROR", details)
        
        assert error.message == "Test error"
        assert error.error_code == "CUSTOM_ERROR"
        assert error.details == details
    
    def test_to_dict(self):
        """测试转换为字典"""
        details = {"context": "test"}
        error = MCPError("Test error", "TEST_ERROR", details)
        
        result = error.to_dict()
        expected = {
            "error": {
                "code": "TEST_ERROR",
                "message": "Test error",
                "details": {"context": "test"}
            }
        }
        
        assert result == expected
    
    def test_to_json(self):
        """测试转换为JSON"""
        error = MCPError("Test error", "TEST_ERROR", {"key": "value"})
        
        json_str = error.to_json()
        parsed = json.loads(json_str)
        
        assert parsed["error"]["code"] == "TEST_ERROR"
        assert parsed["error"]["message"] == "Test error"
        assert parsed["error"]["details"]["key"] == "value"

class TestSpecificExceptions:
    """测试特定异常类"""
    
    def test_configuration_error(self):
        """测试配置错误"""
        error = ConfigurationError("Config is invalid")
        assert isinstance(error, MCPError)
        assert error.error_code == "ConfigurationError"
    
    def test_validation_error(self):
        """测试验证错误"""
        error = ValidationError("Parameter is invalid")
        assert isinstance(error, MCPError)
        assert error.error_code == "ValidationError"
    
    def test_rate_limit_error_with_retry_after(self):
        """测试限流错误带重试时间"""
        error = RateLimitError("Rate limit exceeded", retry_after=60)
        assert isinstance(error, MCPError)
        assert error.details["retry_after"] == 60
    
    def test_api_error_with_details(self):
        """测试API错误带详情"""
        error = APIError(
            "API call failed",
            service="test-service",
            status_code=500,
            response_body='{"error": "Internal error"}'
        )
        
        assert error.details["service"] == "test-service"
        assert error.details["status_code"] == 500
        assert error.details["response_body"] == '{"error": "Internal error"}'
    
    def test_gemini_api_error(self):
        """测试Gemini API错误"""
        error = GeminiAPIError("Gemini error", status_code=400)
        assert isinstance(error, APIError)
        assert error.details["service"] == "gemini"
        assert error.details["status_code"] == 400
    
    def test_kling_api_error(self):
        """测试Kling API错误"""
        error = KlingAPIError("Kling error", status_code=429)
        assert isinstance(error, APIError)
        assert error.details["service"] == "kling"
        assert error.details["status_code"] == 429
    
    def test_tool_execution_error(self):
        """测试工具执行错误"""
        error = ToolExecutionError("Tool failed", tool_name="test_tool")
        assert isinstance(error, MCPError)
        assert error.details["tool_name"] == "test_tool"

class TestErrorHandler:
    """测试ErrorHandler类"""
    
    def test_handle_gemini_error_400(self):
        """测试处理Gemini 400错误"""
        response_body = '{"error": {"message": "Invalid request"}}'
        error = ErrorHandler.handle_api_error(400, response_body, "gemini")
        
        assert isinstance(error, GeminiAPIError)
        assert "请求参数错误" in error.message
        assert error.error_code == "GEMINI_BAD_REQUEST"
        assert error.details["status_code"] == 400
    
    def test_handle_gemini_error_401(self):
        """测试处理Gemini 401错误"""
        response_body = '{"error": {"message": "Unauthorized"}}'
        error = ErrorHandler.handle_api_error(401, response_body, "gemini")
        
        assert isinstance(error, GeminiAPIError)
        assert "认证失败" in error.message
        assert error.error_code == "GEMINI_UNAUTHORIZED"
    
    def test_handle_gemini_error_429(self):
        """测试处理Gemini 429错误"""
        response_body = '{"error": {"message": "Rate limit exceeded"}}'
        error = ErrorHandler.handle_api_error(429, response_body, "gemini")
        
        assert isinstance(error, GeminiAPIError)
        assert "请求限流" in error.message
        assert error.error_code == "GEMINI_RATE_LIMIT"
    
    def test_handle_gemini_error_500(self):
        """测试处理Gemini 500错误"""
        response_body = '{"error": {"message": "Internal server error"}}'
        error = ErrorHandler.handle_api_error(500, response_body, "gemini")
        
        assert isinstance(error, GeminiAPIError)
        assert "服务器错误" in error.message
        assert error.error_code == "GEMINI_SERVER_ERROR"
    
    def test_handle_gemini_error_invalid_json(self):
        """测试处理Gemini错误响应JSON无效"""
        response_body = 'invalid json'
        error = ErrorHandler.handle_api_error(400, response_body, "gemini")
        
        assert isinstance(error, GeminiAPIError)
        assert "API响应解析失败" in error.message
    
    def test_handle_kling_error_400(self):
        """测试处理Kling 400错误"""
        response_body = '{"message": "Bad request"}'
        error = ErrorHandler.handle_api_error(400, response_body, "kling")
        
        assert isinstance(error, KlingAPIError)
        assert "请求参数错误" in error.message
        assert error.error_code == "KLING_BAD_REQUEST"
    
    def test_handle_kling_error_401(self):
        """测试处理Kling 401错误"""
        response_body = '{"message": "Invalid API key"}'
        error = ErrorHandler.handle_api_error(401, response_body, "kling")
        
        assert isinstance(error, KlingAPIError)
        assert "认证失败" in error.message
        assert error.error_code == "KLING_UNAUTHORIZED"
    
    def test_handle_unknown_service_error(self):
        """测试处理未知服务错误"""
        response_body = '{"error": "Unknown error"}'
        error = ErrorHandler.handle_api_error(500, response_body, "unknown")
        
        assert isinstance(error, APIError)
        assert "API调用失败" in error.message
        assert error.details["service"] == "unknown"
    
    def test_create_error_known_code(self):
        """测试根据已知错误代码创建异常"""
        error = ErrorHandler.create_error(
            "VALIDATION_ERROR",
            "Invalid parameter",
            {"param": "test"}
        )
        
        assert isinstance(error, ValidationError)
        assert error.message == "Invalid parameter"
        assert error.details["param"] == "test"
    
    def test_create_error_unknown_code(self):
        """测试根据未知错误代码创建异常"""
        error = ErrorHandler.create_error(
            "UNKNOWN_ERROR",
            "Unknown error",
            {"context": "test"}
        )
        
        assert isinstance(error, MCPError)
        assert error.error_code == "UNKNOWN_ERROR"
        assert error.message == "Unknown error"
    
    def test_wrap_mcp_exception(self):
        """测试包装MCP异常（直接返回）"""
        original = ValidationError("Original error")
        wrapped = ErrorHandler.wrap_exception(original)
        
        # 应该返回原异常
        assert wrapped is original
    
    def test_wrap_connection_error(self):
        """测试包装连接错误"""
        original = ConnectionError("Connection failed")
        wrapped = ErrorHandler.wrap_exception(original, "API call")
        
        assert isinstance(wrapped, NetworkError)
        assert "API call: Connection failed" in wrapped.message
        assert wrapped.details["original_exception"] == "ConnectionError"
    
    def test_wrap_timeout_error(self):
        """测试包装超时错误"""
        from src.gemini_kling_mcp.exceptions import TimeoutError as MCPTimeoutError
        original = TimeoutError("Request timeout")
        wrapped = ErrorHandler.wrap_exception(original)
        
        # 应该包装为我们的MCPTimeoutError
        assert isinstance(wrapped, MCPTimeoutError)
        assert "Request timeout" in wrapped.message
    
    def test_wrap_value_error(self):
        """测试包装值错误"""
        original = ValueError("Invalid value")
        wrapped = ErrorHandler.wrap_exception(original, "Validation")
        
        assert isinstance(wrapped, ValidationError)
        assert "Validation: Invalid value" in wrapped.message
    
    def test_wrap_file_not_found_error(self):
        """测试包装文件未找到错误"""
        original = FileNotFoundError("File not found")
        wrapped = ErrorHandler.wrap_exception(original)
        
        assert isinstance(wrapped, ResourceNotFoundError)
        assert "File not found" in wrapped.message
    
    def test_wrap_file_exists_error(self):
        """测试包装文件已存在错误"""
        original = FileExistsError("File exists")
        wrapped = ErrorHandler.wrap_exception(original)
        
        assert isinstance(wrapped, ResourceExistsError)
        assert "File exists" in wrapped.message
    
    def test_wrap_permission_error(self):
        """测试包装权限错误"""
        original = PermissionError("Permission denied")
        wrapped = ErrorHandler.wrap_exception(original)
        
        assert isinstance(wrapped, AuthorizationError)
        assert "Permission denied" in wrapped.message
    
    def test_wrap_generic_exception(self):
        """测试包装通用异常"""
        original = RuntimeError("Runtime error")
        wrapped = ErrorHandler.wrap_exception(original, "Operation")
        
        assert isinstance(wrapped, ServerError)
        assert "Operation: Runtime error" in wrapped.message
        assert wrapped.details["original_exception"] == "RuntimeError"

def test_error_code_mapping():
    """测试错误代码映射"""
    # 验证所有错误类都在映射中
    expected_errors = [
        ConfigurationError, ValidationError, AuthenticationError,
        AuthorizationError, ServiceUnavailableError, RateLimitError,
        TimeoutError, FileProcessingError, APIError, GeminiAPIError,
        KlingAPIError, ToolExecutionError, ResourceNotFoundError,
        ResourceExistsError, NetworkError, ServerError, MCPError
    ]
    
    mapped_errors = set(ERROR_CODE_MAPPING.values())
    
    for error_class in expected_errors:
        assert error_class in mapped_errors, f"{error_class.__name__} not in mapping"
    
    # 验证映射数量
    assert len(ERROR_CODE_MAPPING) >= len(expected_errors)