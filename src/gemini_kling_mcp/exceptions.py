"""
异常处理模块

定义MCP服务的自定义异常类和错误处理机制。
"""

from typing import Optional, Dict, Any
import json
import builtins

class MCPError(Exception):
    """MCP服务基础异常类"""
    
    def __init__(self, message: str, error_code: Optional[str] = None, 
                 details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error": {
                "code": self.error_code,
                "message": self.message,
                "details": self.details
            }
        }
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

class ConfigurationError(MCPError):
    """配置错误"""
    pass

class ValidationError(MCPError):
    """参数验证错误"""
    pass

class AuthenticationError(MCPError):
    """认证错误"""
    pass

class AuthorizationError(MCPError):
    """授权错误"""
    pass

class ServiceUnavailableError(MCPError):
    """服务不可用错误"""
    pass

class RateLimitError(MCPError):
    """请求限流错误"""
    
    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        super().__init__(message, **kwargs)
        if retry_after:
            self.details["retry_after"] = retry_after

class TimeoutError(MCPError):
    """超时错误"""
    pass

class FileProcessingError(MCPError):
    """文件处理错误"""
    pass

class APIError(MCPError):
    """API调用错误基类"""
    
    def __init__(self, message: str, service: str, status_code: Optional[int] = None,
                 response_body: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.details.update({
            "service": service,
            "status_code": status_code,
            "response_body": response_body
        })

class GeminiAPIError(APIError):
    """Gemini API错误"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, service="gemini", **kwargs)

class KlingAPIError(APIError):
    """Kling API错误"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, service="kling", **kwargs)

class ToolExecutionError(MCPError):
    """工具执行错误"""
    
    def __init__(self, message: str, tool_name: str, **kwargs):
        super().__init__(message, **kwargs)
        self.details["tool_name"] = tool_name
    
    @property
    def tool_name(self) -> str:
        """获取工具名称"""
        return self.details.get("tool_name", "")

class ResourceNotFoundError(MCPError):
    """资源未找到错误"""
    pass

class ResourceExistsError(MCPError):
    """资源已存在错误"""
    pass

class NetworkError(MCPError):
    """网络错误"""
    pass

class ServerError(MCPError):
    """服务器内部错误"""
    pass

# 错误代码映射
ERROR_CODE_MAPPING = {
    "CONFIGURATION_ERROR": ConfigurationError,
    "VALIDATION_ERROR": ValidationError,
    "AUTHENTICATION_ERROR": AuthenticationError,
    "AUTHORIZATION_ERROR": AuthorizationError,
    "SERVICE_UNAVAILABLE": ServiceUnavailableError,
    "RATE_LIMIT_ERROR": RateLimitError,
    "TIMEOUT_ERROR": TimeoutError,
    "FILE_PROCESSING_ERROR": FileProcessingError,
    "API_ERROR": APIError,
    "GEMINI_API_ERROR": GeminiAPIError,
    "KLING_API_ERROR": KlingAPIError,
    "TOOL_EXECUTION_ERROR": ToolExecutionError,
    "RESOURCE_NOT_FOUND": ResourceNotFoundError,
    "RESOURCE_EXISTS": ResourceExistsError,
    "NETWORK_ERROR": NetworkError,
    "SERVER_ERROR": ServerError,
    "MCP_ERROR": MCPError
}

class ErrorHandler:
    """错误处理器"""
    
    @staticmethod
    def handle_api_error(response_status: int, response_body: str, 
                        service: str) -> MCPError:
        """处理API错误响应"""
        if service == "gemini":
            return ErrorHandler._handle_gemini_error(response_status, response_body)
        elif service == "kling":
            return ErrorHandler._handle_kling_error(response_status, response_body)
        else:
            return APIError(
                f"API调用失败: {response_status}",
                service=service,
                status_code=response_status,
                response_body=response_body
            )
    
    @staticmethod
    def _handle_gemini_error(status_code: int, response_body: str) -> GeminiAPIError:
        """处理Gemini API错误"""
        try:
            error_data = json.loads(response_body)
            error_message = error_data.get("error", {}).get("message", "未知错误")
        except (json.JSONDecodeError, KeyError):
            error_message = "API响应解析失败"
        
        if status_code == 400:
            error_code = "GEMINI_BAD_REQUEST"
            message = f"Gemini API请求参数错误: {error_message}"
        elif status_code == 401:
            error_code = "GEMINI_UNAUTHORIZED"
            message = f"Gemini API认证失败: {error_message}"
        elif status_code == 403:
            error_code = "GEMINI_FORBIDDEN"
            message = f"Gemini API访问被拒绝: {error_message}"
        elif status_code == 404:
            error_code = "GEMINI_NOT_FOUND"
            message = f"Gemini API资源未找到: {error_message}"
        elif status_code == 429:
            error_code = "GEMINI_RATE_LIMIT"
            message = f"Gemini API请求限流: {error_message}"
        elif status_code >= 500:
            error_code = "GEMINI_SERVER_ERROR"
            message = f"Gemini API服务器错误: {error_message}"
        else:
            error_code = "GEMINI_API_ERROR"
            message = f"Gemini API未知错误: {error_message}"
        
        return GeminiAPIError(
            message,
            error_code=error_code,
            status_code=status_code,
            response_body=response_body
        )
    
    @staticmethod
    def _handle_kling_error(status_code: int, response_body: str) -> KlingAPIError:
        """处理Kling API错误"""
        try:
            error_data = json.loads(response_body)
            error_message = error_data.get("message", "未知错误")
        except (json.JSONDecodeError, KeyError):
            error_message = "API响应解析失败"
        
        if status_code == 400:
            error_code = "KLING_BAD_REQUEST"
            message = f"Kling API请求参数错误: {error_message}"
        elif status_code == 401:
            error_code = "KLING_UNAUTHORIZED"
            message = f"Kling API认证失败: {error_message}"
        elif status_code == 403:
            error_code = "KLING_FORBIDDEN"
            message = f"Kling API访问被拒绝: {error_message}"
        elif status_code == 404:
            error_code = "KLING_NOT_FOUND"
            message = f"Kling API资源未找到: {error_message}"
        elif status_code == 429:
            error_code = "KLING_RATE_LIMIT"
            message = f"Kling API请求限流: {error_message}"
        elif status_code >= 500:
            error_code = "KLING_SERVER_ERROR"
            message = f"Kling API服务器错误: {error_message}"
        else:
            error_code = "KLING_API_ERROR"
            message = f"Kling API未知错误: {error_message}"
        
        return KlingAPIError(
            message,
            error_code=error_code,
            status_code=status_code,
            response_body=response_body
        )
    
    @staticmethod
    def create_error(error_code: str, message: str, 
                    details: Optional[Dict[str, Any]] = None) -> MCPError:
        """根据错误代码创建异常"""
        error_class = ERROR_CODE_MAPPING.get(error_code, MCPError)
        return error_class(message, error_code=error_code, details=details)
    
    @staticmethod
    def wrap_exception(exc: Exception, context: Optional[str] = None) -> MCPError:
        """包装标准异常为MCP异常"""
        if isinstance(exc, MCPError):
            return exc
        
        message = str(exc)
        if context:
            message = f"{context}: {message}"
        
        # 根据异常类型映射到相应的MCP异常
        if isinstance(exc, (ConnectionError, OSError)):
            return NetworkError(message, details={"original_exception": type(exc).__name__})
        elif isinstance(exc, builtins.TimeoutError):
            # 明确引用内置的TimeoutError以避免和我们的TimeoutError冲突
            return globals()['TimeoutError'](message, details={"original_exception": type(exc).__name__})
        elif isinstance(exc, (ValueError, TypeError)):
            return ValidationError(message, details={"original_exception": type(exc).__name__})
        elif isinstance(exc, FileNotFoundError):
            return ResourceNotFoundError(message, details={"original_exception": type(exc).__name__})
        elif isinstance(exc, FileExistsError):
            return ResourceExistsError(message, details={"original_exception": type(exc).__name__})
        elif isinstance(exc, PermissionError):
            return AuthorizationError(message, details={"original_exception": type(exc).__name__})
        else:
            return ServerError(message, details={"original_exception": type(exc).__name__})