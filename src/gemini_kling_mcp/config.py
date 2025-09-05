"""
配置管理模块

提供环境变量和配置文件的统一管理，支持默认值和验证。
"""

import os
import json
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from pathlib import Path

@dataclass
class ServerConfig:
    """MCP服务器配置"""
    host: str = "localhost"
    port: int = 0  # 0表示使用stdio模式
    log_level: str = "INFO"
    debug: bool = False
    
    @classmethod
    def from_env(cls) -> "ServerConfig":
        """从环境变量加载配置"""
        return cls(
            host=os.getenv("MCP_SERVER_HOST", "localhost"),
            port=int(os.getenv("MCP_SERVER_PORT", "0")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            debug=os.getenv("DEBUG", "false").lower() == "true"
        )

@dataclass
class GeminiConfig:
    """Gemini API配置"""
    api_key: str
    base_url: str = "https://generativelanguage.googleapis.com"
    timeout: int = 30
    max_retries: int = 3
    
    @classmethod
    def from_env(cls) -> "GeminiConfig":
        """从环境变量加载配置"""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY环境变量必须设置")
        
        return cls(
            api_key=api_key,
            base_url=os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com"),
            timeout=int(os.getenv("GEMINI_TIMEOUT", "30")),
            max_retries=int(os.getenv("GEMINI_MAX_RETRIES", "3"))
        )

@dataclass 
class KlingConfig:
    """Kling API配置"""
    api_key: str
    base_url: str = "https://api.klingai.com"
    timeout: int = 300  # 视频生成需要更长时间
    max_retries: int = 3
    
    @classmethod
    def from_env(cls) -> "KlingConfig":
        """从环境变量加载配置"""
        api_key = os.getenv("KLING_API_KEY")
        if not api_key:
            raise ValueError("KLING_API_KEY环境变量必须设置")
        
        return cls(
            api_key=api_key,
            base_url=os.getenv("KLING_BASE_URL", "https://api.klingai.com"),
            timeout=int(os.getenv("KLING_TIMEOUT", "300")),
            max_retries=int(os.getenv("KLING_MAX_RETRIES", "3"))
        )

@dataclass
class FileConfig:
    """文件处理配置"""
    temp_dir: str = "/tmp/gemini_kling_mcp"
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    cleanup_interval: int = 3600  # 1小时
    allowed_formats: List[str] = field(default_factory=lambda: [
        "jpg", "jpeg", "png", "gif", "webp", "bmp",
        "mp4", "avi", "mov", "mkv", "webm",
        "txt", "json", "yaml", "yml"
    ])
    
    @classmethod
    def from_env(cls) -> "FileConfig":
        """从环境变量加载配置"""
        allowed_formats_str = os.getenv("ALLOWED_FILE_FORMATS", "")
        allowed_formats = allowed_formats_str.split(",") if allowed_formats_str else [
            "jpg", "jpeg", "png", "gif", "webp", "bmp",
            "mp4", "avi", "mov", "mkv", "webm", 
            "txt", "json", "yaml", "yml"
        ]
        
        return cls(
            temp_dir=os.getenv("TEMP_DIR", "/tmp/gemini_kling_mcp"),
            max_file_size=int(os.getenv("MAX_FILE_SIZE", str(100 * 1024 * 1024))),
            cleanup_interval=int(os.getenv("CLEANUP_INTERVAL", "3600")),
            allowed_formats=[fmt.strip() for fmt in allowed_formats]
        )

@dataclass
class Config:
    """主配置类"""
    server: ServerConfig
    gemini: GeminiConfig
    kling: KlingConfig
    file: FileConfig
    
    @classmethod
    def from_env(cls) -> "Config":
        """从环境变量加载完整配置"""
        return cls(
            server=ServerConfig.from_env(),
            gemini=GeminiConfig.from_env(),
            kling=KlingConfig.from_env(),
            file=FileConfig.from_env()
        )
    
    @classmethod
    def from_file(cls, config_path: str) -> "Config":
        """从配置文件加载配置"""
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        # 创建配置实例，优先使用环境变量，然后使用配置文件值，最后使用默认值
        return cls(
            server=ServerConfig(
                host=os.getenv("MCP_SERVER_HOST", config_data.get("server", {}).get("host", "localhost")),
                port=int(os.getenv("MCP_SERVER_PORT", config_data.get("server", {}).get("port", 0))),
                log_level=os.getenv("LOG_LEVEL", config_data.get("server", {}).get("log_level", "INFO")),
                debug=os.getenv("DEBUG", str(config_data.get("server", {}).get("debug", False))).lower() == "true"
            ),
            gemini=GeminiConfig(
                api_key=os.getenv("GEMINI_API_KEY", config_data.get("gemini", {}).get("api_key", "")),
                base_url=os.getenv("GEMINI_BASE_URL", config_data.get("gemini", {}).get("base_url", "https://generativelanguage.googleapis.com")),
                timeout=int(os.getenv("GEMINI_TIMEOUT", config_data.get("gemini", {}).get("timeout", 30))),
                max_retries=int(os.getenv("GEMINI_MAX_RETRIES", config_data.get("gemini", {}).get("max_retries", 3)))
            ),
            kling=KlingConfig(
                api_key=os.getenv("KLING_API_KEY", config_data.get("kling", {}).get("api_key", "")),
                base_url=os.getenv("KLING_BASE_URL", config_data.get("kling", {}).get("base_url", "https://api.klingai.com")),
                timeout=int(os.getenv("KLING_TIMEOUT", config_data.get("kling", {}).get("timeout", 300))),
                max_retries=int(os.getenv("KLING_MAX_RETRIES", config_data.get("kling", {}).get("max_retries", 3)))
            ),
            file=FileConfig(
                temp_dir=os.getenv("TEMP_DIR", config_data.get("file", {}).get("temp_dir", "/tmp/gemini_kling_mcp")),
                max_file_size=int(os.getenv("MAX_FILE_SIZE", config_data.get("file", {}).get("max_file_size", 100 * 1024 * 1024))),
                cleanup_interval=int(os.getenv("CLEANUP_INTERVAL", config_data.get("file", {}).get("cleanup_interval", 3600))),
                allowed_formats=os.getenv("ALLOWED_FILE_FORMATS", "").split(",") if os.getenv("ALLOWED_FILE_FORMATS") else config_data.get("file", {}).get("allowed_formats", [
                    "jpg", "jpeg", "png", "gif", "webp", "bmp",
                    "mp4", "avi", "mov", "mkv", "webm",
                    "txt", "json", "yaml", "yml"
                ])
            )
        )
    
    def validate(self) -> None:
        """验证配置"""
        errors = []
        
        # 验证API密钥
        if not self.gemini.api_key:
            errors.append("Gemini API密钥未设置")
        if not self.kling.api_key:
            errors.append("Kling API密钥未设置")
        
        # 验证端口范围
        if self.server.port < 0 or self.server.port > 65535:
            errors.append(f"服务器端口范围无效: {self.server.port}")
        
        # 验证超时时间
        if self.gemini.timeout <= 0:
            errors.append(f"Gemini超时时间无效: {self.gemini.timeout}")
        if self.kling.timeout <= 0:
            errors.append(f"Kling超时时间无效: {self.kling.timeout}")
        
        # 验证文件大小限制
        if self.file.max_file_size <= 0:
            errors.append(f"最大文件大小无效: {self.file.max_file_size}")
        
        # 验证临时目录
        temp_dir = Path(self.file.temp_dir)
        try:
            temp_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"无法创建临时目录 {self.file.temp_dir}: {e}")
        
        if errors:
            raise ValueError("配置验证失败:\n" + "\n".join(f"- {error}" for error in errors))
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于序列化）"""
        return {
            "server": {
                "host": self.server.host,
                "port": self.server.port,
                "log_level": self.server.log_level,
                "debug": self.server.debug
            },
            "gemini": {
                "api_key": "***" if self.gemini.api_key else "",  # 隐藏敏感信息
                "base_url": self.gemini.base_url,
                "timeout": self.gemini.timeout,
                "max_retries": self.gemini.max_retries
            },
            "kling": {
                "api_key": "***" if self.kling.api_key else "",  # 隐藏敏感信息
                "base_url": self.kling.base_url,
                "timeout": self.kling.timeout,
                "max_retries": self.kling.max_retries
            },
            "file": {
                "temp_dir": self.file.temp_dir,
                "max_file_size": self.file.max_file_size,
                "cleanup_interval": self.file.cleanup_interval,
                "allowed_formats": self.file.allowed_formats
            }
        }

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: Optional[str] = None):
        self._config: Optional[Config] = None
        self._config_path = config_path
        
    def load_config(self) -> Config:
        """加载配置"""
        if self._config_path and os.path.exists(self._config_path):
            self._config = Config.from_file(self._config_path)
        else:
            self._config = Config.from_env()
        
        self._config.validate()
        return self._config
    
    @property
    def config(self) -> Config:
        """获取当前配置"""
        if self._config is None:
            self._config = self.load_config()
        return self._config
    
    def reload_config(self) -> Config:
        """重新加载配置"""
        self._config = None
        return self.load_config()

# 全局配置实例
config_manager = ConfigManager()

def get_config() -> Config:
    """获取全局配置实例"""
    return config_manager.config