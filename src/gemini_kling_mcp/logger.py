"""
结构化日志系统模块

提供统一的日志记录功能，支持不同日志级别和结构化输出。
"""

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path
import traceback

class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器"""
    
    def __init__(self, service_name: str = "gemini-kling-mcp"):
        super().__init__()
        self.service_name = service_name
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为结构化JSON格式"""
        # 基础日志信息
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # 添加额外的结构化数据
        if hasattr(record, 'extra_data'):
            log_data["data"] = record.extra_data
        
        # 添加请求ID（如果存在）
        if hasattr(record, 'request_id'):
            log_data["request_id"] = record.request_id
        
        return json.dumps(log_data, ensure_ascii=False, separators=(',', ':'))

class MCPLogger:
    """MCP服务专用日志器"""
    
    def __init__(self, name: str, level: str = "INFO", service_name: str = "gemini-kling-mcp"):
        self.logger = logging.getLogger(name)
        self.service_name = service_name
        self._setup_logger(level)
        self._request_id: Optional[str] = None
    
    def _setup_logger(self, level: str) -> None:
        """设置日志器"""
        # 清除现有的处理器
        self.logger.handlers.clear()
        
        # 设置日志级别
        numeric_level = getattr(logging, level.upper(), logging.INFO)
        self.logger.setLevel(numeric_level)
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        
        # 设置格式化器
        formatter = StructuredFormatter(self.service_name)
        console_handler.setFormatter(formatter)
        
        # 添加处理器
        self.logger.addHandler(console_handler)
        
        # 防止日志传播到根日志器
        self.logger.propagate = False
    
    def set_request_id(self, request_id: str) -> None:
        """设置请求ID"""
        self._request_id = request_id
    
    def clear_request_id(self) -> None:
        """清除请求ID"""
        self._request_id = None
    
    def _log_with_context(self, level: str, message: str, **kwargs) -> None:
        """带上下文信息的日志记录"""
        extra = {}
        
        # 添加请求ID
        if self._request_id:
            extra['request_id'] = self._request_id
        
        # 添加额外数据
        if kwargs:
            extra['extra_data'] = kwargs
        
        # 记录日志
        log_func = getattr(self.logger, level.lower())
        log_func(message, extra=extra)
    
    def debug(self, message: str, **kwargs) -> None:
        """记录DEBUG级别日志"""
        self._log_with_context("DEBUG", message, **kwargs)
    
    def info(self, message: str, **kwargs) -> None:
        """记录INFO级别日志"""
        self._log_with_context("INFO", message, **kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """记录WARNING级别日志"""
        self._log_with_context("WARNING", message, **kwargs)
    
    def error(self, message: str, **kwargs) -> None:
        """记录ERROR级别日志"""
        self._log_with_context("ERROR", message, **kwargs)
    
    def critical(self, message: str, **kwargs) -> None:
        """记录CRITICAL级别日志"""
        self._log_with_context("CRITICAL", message, **kwargs)
    
    def exception(self, message: str, **kwargs) -> None:
        """记录异常信息"""
        extra = {}
        
        # 添加请求ID
        if self._request_id:
            extra['request_id'] = self._request_id
        
        # 添加额外数据
        if kwargs:
            extra['extra_data'] = kwargs
        
        # 记录异常日志
        self.logger.error(message, exc_info=True, extra=extra)

    def log_api_call(self, service: str, method: str, status: str, 
                    duration: float, **kwargs) -> None:
        """记录API调用日志"""
        self.info(
            f"API调用: {service}.{method}",
            service=service,
            method=method,
            status=status,
            duration_ms=round(duration * 1000, 2),
            **kwargs
        )
    
    def log_tool_call(self, tool_name: str, parameters: Dict[str, Any], 
                     status: str, duration: float, **kwargs) -> None:
        """记录工具调用日志"""
        # 过滤敏感参数
        safe_params = self._filter_sensitive_data(parameters)
        
        self.info(
            f"工具调用: {tool_name}",
            tool=tool_name,
            parameters=safe_params,
            status=status,
            duration_ms=round(duration * 1000, 2),
            **kwargs
        )
    
    def log_server_event(self, event: str, **kwargs) -> None:
        """记录服务器事件日志"""
        self.info(
            f"服务器事件: {event}",
            event=event,
            **kwargs
        )
    
    def _filter_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """过滤敏感数据"""
        sensitive_keys = {'api_key', 'password', 'token', 'secret', 'auth'}
        filtered = {}
        
        for key, value in data.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                filtered[key] = "***"
            elif isinstance(value, dict):
                filtered[key] = self._filter_sensitive_data(value)
            else:
                filtered[key] = value
        
        return filtered

class LoggerManager:
    """日志管理器"""
    
    def __init__(self):
        self._loggers: Dict[str, MCPLogger] = {}
        self._default_level = "INFO"
        self._service_name = "gemini-kling-mcp"
    
    def get_logger(self, name: str, level: Optional[str] = None) -> MCPLogger:
        """获取或创建日志器"""
        if name not in self._loggers:
            log_level = level or self._default_level
            self._loggers[name] = MCPLogger(name, log_level, self._service_name)
        return self._loggers[name]
    
    def set_level(self, level: str) -> None:
        """设置全局日志级别"""
        self._default_level = level
        # 更新所有现有日志器的级别
        for logger in self._loggers.values():
            logger._setup_logger(level)
    
    def set_service_name(self, service_name: str) -> None:
        """设置服务名称"""
        self._service_name = service_name
        # 重新创建所有日志器
        names_and_levels = [(name, logger.logger.level) for name, logger in self._loggers.items()]
        self._loggers.clear()
        for name, level_num in names_and_levels:
            level_name = logging.getLevelName(level_num)
            self.get_logger(name, level_name)

# 全局日志管理器实例
logger_manager = LoggerManager()

def get_logger(name: str, level: Optional[str] = None) -> MCPLogger:
    """获取日志器实例"""
    return logger_manager.get_logger(name, level)

def set_log_level(level: str) -> None:
    """设置全局日志级别"""
    logger_manager.set_level(level)

def set_service_name(service_name: str) -> None:
    """设置服务名称"""
    logger_manager.set_service_name(service_name)

# 便捷的模块级日志器
logger = get_logger(__name__)