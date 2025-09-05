"""
测试配置管理模块
"""

import os
import json
import tempfile
from pathlib import Path
import pytest
from unittest.mock import patch, mock_open

from src.gemini_kling_mcp.config import (
    Config, ConfigManager, ServerConfig, GeminiConfig, 
    KlingConfig, FileConfig, get_config
)

class TestServerConfig:
    """测试ServerConfig类"""
    
    def test_default_values(self):
        """测试默认值"""
        config = ServerConfig()
        assert config.host == "localhost"
        assert config.port == 0
        assert config.log_level == "INFO"
        assert config.debug is False
    
    @patch.dict(os.environ, {
        'MCP_SERVER_HOST': 'test-host',
        'MCP_SERVER_PORT': '8080',
        'LOG_LEVEL': 'DEBUG',
        'DEBUG': 'true'
    })
    def test_from_env(self):
        """测试从环境变量加载"""
        config = ServerConfig.from_env()
        assert config.host == "test-host"
        assert config.port == 8080
        assert config.log_level == "DEBUG"
        assert config.debug is True

class TestGeminiConfig:
    """测试GeminiConfig类"""
    
    def test_missing_api_key_raises_error(self):
        """测试缺少API密钥时抛出错误"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="GEMINI_API_KEY环境变量必须设置"):
                GeminiConfig.from_env()
    
    @patch.dict(os.environ, {
        'GEMINI_API_KEY': 'test-key',
        'GEMINI_BASE_URL': 'https://test.api.com',
        'GEMINI_TIMEOUT': '60',
        'GEMINI_MAX_RETRIES': '5'
    })
    def test_from_env_with_all_values(self):
        """测试从环境变量加载所有值"""
        config = GeminiConfig.from_env()
        assert config.api_key == "test-key"
        assert config.base_url == "https://test.api.com"
        assert config.timeout == 60
        assert config.max_retries == 5
    
    @patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'})
    def test_from_env_with_defaults(self):
        """测试从环境变量加载时使用默认值"""
        config = GeminiConfig.from_env()
        assert config.api_key == "test-key"
        assert config.base_url == "https://generativelanguage.googleapis.com"
        assert config.timeout == 30
        assert config.max_retries == 3

class TestKlingConfig:
    """测试KlingConfig类"""
    
    def test_missing_api_key_raises_error(self):
        """测试缺少API密钥时抛出错误"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="KLING_API_KEY环境变量必须设置"):
                KlingConfig.from_env()
    
    @patch.dict(os.environ, {
        'KLING_API_KEY': 'test-key',
        'KLING_BASE_URL': 'https://test.kling.com',
        'KLING_TIMEOUT': '600',
        'KLING_MAX_RETRIES': '2'
    })
    def test_from_env_with_all_values(self):
        """测试从环境变量加载所有值"""
        config = KlingConfig.from_env()
        assert config.api_key == "test-key"
        assert config.base_url == "https://test.kling.com"
        assert config.timeout == 600
        assert config.max_retries == 2

class TestFileConfig:
    """测试FileConfig类"""
    
    def test_default_values(self):
        """测试默认值"""
        config = FileConfig()
        assert config.temp_dir == "/tmp/gemini_kling_mcp"
        assert config.max_file_size == 100 * 1024 * 1024
        assert config.cleanup_interval == 3600
        assert "jpg" in config.allowed_formats
        assert "png" in config.allowed_formats
    
    @patch.dict(os.environ, {
        'TEMP_DIR': '/custom/temp',
        'MAX_FILE_SIZE': '50000000',
        'CLEANUP_INTERVAL': '1800',
        'ALLOWED_FILE_FORMATS': 'jpg,png,gif'
    })
    def test_from_env_with_custom_values(self):
        """测试从环境变量加载自定义值"""
        config = FileConfig.from_env()
        assert config.temp_dir == "/custom/temp"
        assert config.max_file_size == 50000000
        assert config.cleanup_interval == 1800
        assert config.allowed_formats == ["jpg", "png", "gif"]

class TestConfig:
    """测试Config主类"""
    
    @patch.dict(os.environ, {
        'GEMINI_API_KEY': 'gemini-key',
        'KLING_API_KEY': 'kling-key'
    })
    def test_from_env(self):
        """测试从环境变量创建完整配置"""
        config = Config.from_env()
        assert isinstance(config.server, ServerConfig)
        assert isinstance(config.gemini, GeminiConfig)
        assert isinstance(config.kling, KlingConfig)
        assert isinstance(config.file, FileConfig)
        assert config.gemini.api_key == "gemini-key"
        assert config.kling.api_key == "kling-key"
    
    def test_from_file_not_exists(self):
        """测试配置文件不存在时抛出错误"""
        with pytest.raises(FileNotFoundError):
            Config.from_file("/non/existent/file.json")
    
    def test_from_file_success(self):
        """测试从配置文件成功加载"""
        config_data = {
            "server": {
                "host": "test-host",
                "port": 8080,
                "log_level": "DEBUG",
                "debug": True
            },
            "gemini": {
                "api_key": "file-gemini-key",
                "base_url": "https://file.gemini.com",
                "timeout": 45,
                "max_retries": 4
            },
            "kling": {
                "api_key": "file-kling-key",
                "base_url": "https://file.kling.com",
                "timeout": 400,
                "max_retries": 2
            },
            "file": {
                "temp_dir": "/file/temp",
                "max_file_size": 75000000,
                "cleanup_interval": 2400,
                "allowed_formats": ["jpg", "png"]
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_file = f.name
        
        try:
            with patch.dict(os.environ, {}, clear=True):
                config = Config.from_file(temp_file)
                
                # 验证配置加载正确
                assert config.server.host == "test-host"
                assert config.server.port == 8080
                assert config.gemini.api_key == "file-gemini-key"
                assert config.kling.api_key == "file-kling-key"
                assert config.file.temp_dir == "/file/temp"
        finally:
            Path(temp_file).unlink()
    
    def test_env_overrides_file(self):
        """测试环境变量覆盖配置文件"""
        config_data = {
            "server": {"host": "file-host"},
            "gemini": {"api_key": "file-gemini-key"},
            "kling": {"api_key": "file-kling-key"}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_file = f.name
        
        try:
            with patch.dict(os.environ, {
                'MCP_SERVER_HOST': 'env-host',
                'GEMINI_API_KEY': 'env-gemini-key'
            }):
                config = Config.from_file(temp_file)
                
                # 环境变量应覆盖文件值
                assert config.server.host == "env-host"
                assert config.gemini.api_key == "env-gemini-key"
                # 文件值应保留（如果环境变量未设置）
                assert config.kling.api_key == "file-kling-key"
        finally:
            Path(temp_file).unlink()
    
    @patch.dict(os.environ, {
        'GEMINI_API_KEY': 'test-key',
        'KLING_API_KEY': 'test-key'
    })
    def test_validate_success(self):
        """测试配置验证成功"""
        config = Config.from_env()
        # 应该不抛出异常
        config.validate()
    
    @patch.dict(os.environ, {}, clear=True)
    def test_validate_missing_gemini_key(self):
        """测试验证失败 - 缺少Gemini API密钥"""
        with pytest.raises(ValueError, match="GEMINI_API_KEY环境变量必须设置"):
            Config.from_env()
    
    @patch.dict(os.environ, {
        'GEMINI_API_KEY': 'test-key',
        'KLING_API_KEY': 'test-key',
        'MCP_SERVER_PORT': '70000'  # 无效端口
    })
    def test_validate_invalid_port(self):
        """测试验证失败 - 无效端口"""
        config = Config.from_env()
        with pytest.raises(ValueError, match="服务器端口范围无效"):
            config.validate()
    
    @patch.dict(os.environ, {
        'GEMINI_API_KEY': 'test-key',
        'KLING_API_KEY': 'test-key'
    })
    def test_to_dict_hides_sensitive_data(self):
        """测试转换为字典时隐藏敏感信息"""
        config = Config.from_env()
        config_dict = config.to_dict()
        
        # API密钥应该被隐藏
        assert config_dict["gemini"]["api_key"] == "***"
        assert config_dict["kling"]["api_key"] == "***"
        
        # 其他信息应该正常显示
        assert config_dict["server"]["host"] == "localhost"
        assert config_dict["gemini"]["base_url"] == "https://generativelanguage.googleapis.com"

class TestConfigManager:
    """测试ConfigManager类"""
    
    def test_load_config_from_env(self):
        """测试从环境变量加载配置"""
        with patch.dict(os.environ, {
            'GEMINI_API_KEY': 'test-key',
            'KLING_API_KEY': 'test-key'
        }):
            manager = ConfigManager()
            config = manager.load_config()
            assert isinstance(config, Config)
            assert config.gemini.api_key == "test-key"
    
    def test_load_config_from_file(self):
        """测试从文件加载配置"""
        config_data = {
            "gemini": {"api_key": "file-key"},
            "kling": {"api_key": "file-key"}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_file = f.name
        
        try:
            manager = ConfigManager(temp_file)
            config = manager.load_config()
            assert isinstance(config, Config)
            assert config.gemini.api_key == "file-key"
        finally:
            Path(temp_file).unlink()
    
    def test_config_property_loads_on_first_access(self):
        """测试配置属性在首次访问时加载"""
        with patch.dict(os.environ, {
            'GEMINI_API_KEY': 'test-key',
            'KLING_API_KEY': 'test-key'
        }):
            manager = ConfigManager()
            assert manager._config is None
            
            # 首次访问应该加载配置
            config = manager.config
            assert manager._config is not None
            assert isinstance(config, Config)
    
    def test_reload_config(self):
        """测试重新加载配置"""
        with patch.dict(os.environ, {
            'GEMINI_API_KEY': 'test-key',
            'KLING_API_KEY': 'test-key'
        }):
            manager = ConfigManager()
            
            # 首次加载
            config1 = manager.config
            assert manager._config is not None
            
            # 重新加载
            config2 = manager.reload_config()
            assert isinstance(config2, Config)
            # 应该是新的实例
            assert config2 is not config1

@patch.dict(os.environ, {
    'GEMINI_API_KEY': 'test-key',
    'KLING_API_KEY': 'test-key'
})
def test_get_config_global_function():
    """测试全局get_config函数"""
    config = get_config()
    assert isinstance(config, Config)
    assert config.gemini.api_key == "test-key"