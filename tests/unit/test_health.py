"""
测试健康检查模块
"""

import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
import aiohttp

from src.gemini_kling_mcp.utils.health import (
    HealthStatus, ComponentStatus, HealthChecker, ResourceMonitor
)
from src.gemini_kling_mcp.config import Config

class TestHealthStatus:
    """测试HealthStatus枚举"""
    
    def test_enum_values(self):
        """测试枚举值"""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.DEGRADED.value == "degraded"

class TestComponentStatus:
    """测试ComponentStatus类"""
    
    def test_basic_creation(self):
        """测试基础创建"""
        status = ComponentStatus("test_component", HealthStatus.HEALTHY)
        
        assert status.name == "test_component"
        assert status.status == HealthStatus.HEALTHY
        assert status.message == ""
        assert status.details == {}
        assert status.timestamp > 0
    
    def test_creation_with_all_parameters(self):
        """测试使用所有参数创建"""
        details = {"key": "value", "count": 123}
        status = ComponentStatus(
            "test_component",
            HealthStatus.DEGRADED,
            "Component is degraded",
            details
        )
        
        assert status.name == "test_component"
        assert status.status == HealthStatus.DEGRADED
        assert status.message == "Component is degraded"
        assert status.details == details
    
    def test_to_dict(self):
        """测试转换为字典"""
        details = {"context": "test"}
        status = ComponentStatus(
            "test_component",
            HealthStatus.UNHEALTHY,
            "Component failed",
            details
        )
        
        result = status.to_dict()
        
        assert result["name"] == "test_component"
        assert result["status"] == "unhealthy"
        assert result["message"] == "Component failed"
        assert result["details"] == details
        assert "timestamp" in result
        assert isinstance(result["timestamp"], float)

class TestHealthChecker:
    """测试HealthChecker类"""
    
    @pytest.fixture
    def mock_config(self):
        """创建模拟配置"""
        config = MagicMock()
        config.gemini.api_key = "test-key"
        config.gemini.base_url = "https://test.gemini.com"
        config.kling.api_key = "test-key"
        config.kling.base_url = "https://test.kling.com"
        config.file.temp_dir = "/tmp/test"
        return config
    
    def test_initialization(self, mock_config):
        """测试初始化"""
        checker = HealthChecker(mock_config)
        
        assert checker.config is mock_config
        assert len(checker._checks) == 4  # configuration, file_system, gemini_api, kling_api
        assert "configuration" in checker._checks
        assert "file_system" in checker._checks
        assert "gemini_api" in checker._checks
        assert "kling_api" in checker._checks
    
    @pytest.mark.asyncio
    async def test_check_health_all_healthy(self, mock_config):
        """测试所有组件健康的完整健康检查"""
        checker = HealthChecker(mock_config)
        
        # Mock所有检查为健康状态
        async def mock_healthy_check():
            return ComponentStatus("test", HealthStatus.HEALTHY, "OK")
        
        for check_name in checker._checks:
            checker._checks[check_name] = mock_healthy_check
        
        result = await checker.check_health()
        
        assert result["status"] == "healthy"
        assert len(result["components"]) == 4
        assert "timestamp" in result
        assert "duration" in result
        assert result["version"] == "0.1.0"
        
        # 验证所有组件状态
        for component in result["components"].values():
            assert component["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_check_health_one_unhealthy(self, mock_config):
        """测试一个组件不健康时的健康检查"""
        checker = HealthChecker(mock_config)
        
        # Mock一个检查为不健康状态
        async def mock_unhealthy_check():
            return ComponentStatus("test", HealthStatus.UNHEALTHY, "Failed")
        
        async def mock_healthy_check():
            return ComponentStatus("test", HealthStatus.HEALTHY, "OK")
        
        checker._checks["configuration"] = mock_unhealthy_check
        for check_name in list(checker._checks.keys())[1:]:
            checker._checks[check_name] = mock_healthy_check
        
        result = await checker.check_health()
        
        # 整体状态应该是unhealthy
        assert result["status"] == "unhealthy"
    
    @pytest.mark.asyncio
    async def test_check_health_one_degraded(self, mock_config):
        """测试一个组件降级时的健康检查"""
        checker = HealthChecker(mock_config)
        
        # Mock一个检查为降级状态
        async def mock_degraded_check():
            return ComponentStatus("test", HealthStatus.DEGRADED, "Degraded")
        
        async def mock_healthy_check():
            return ComponentStatus("test", HealthStatus.HEALTHY, "OK")
        
        checker._checks["configuration"] = mock_degraded_check
        for check_name in list(checker._checks.keys())[1:]:
            checker._checks[check_name] = mock_healthy_check
        
        result = await checker.check_health()
        
        # 整体状态应该是degraded
        assert result["status"] == "degraded"
    
    @pytest.mark.asyncio
    async def test_check_health_with_exception(self, mock_config):
        """测试健康检查过程中发生异常"""
        checker = HealthChecker(mock_config)
        
        # Mock一个检查抛出异常
        async def mock_exception_check():
            raise RuntimeError("Check failed")
        
        async def mock_healthy_check():
            return ComponentStatus("test", HealthStatus.HEALTHY, "OK")
        
        checker._checks["configuration"] = mock_exception_check
        for check_name in list(checker._checks.keys())[1:]:
            checker._checks[check_name] = mock_healthy_check
        
        result = await checker.check_health()
        
        # 整体状态应该是unhealthy（因为异常）
        assert result["status"] == "unhealthy"
        
        # 异常的组件应该有错误信息
        config_status = result["components"]["configuration"]
        assert config_status["status"] == "unhealthy"
        assert "健康检查异常" in config_status["message"]
    
    @pytest.mark.asyncio
    async def test_check_configuration_success(self, mock_config):
        """测试配置检查成功"""
        mock_config.validate = MagicMock()  # 不抛出异常
        
        checker = HealthChecker(mock_config)
        status = await checker._check_configuration()
        
        assert status.name == "configuration"
        assert status.status == HealthStatus.HEALTHY
        assert "配置验证通过" in status.message
    
    @pytest.mark.asyncio
    async def test_check_configuration_failure(self, mock_config):
        """测试配置检查失败"""
        mock_config.validate = MagicMock(side_effect=ValueError("Invalid config"))
        
        checker = HealthChecker(mock_config)
        status = await checker._check_configuration()
        
        assert status.name == "configuration"
        assert status.status == HealthStatus.UNHEALTHY
        assert "配置验证失败" in status.message
    
    @pytest.mark.asyncio
    async def test_check_file_system_success(self, mock_config):
        """测试文件系统检查成功"""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_config.file.temp_dir = temp_dir
            
            checker = HealthChecker(mock_config)
            
            with patch('shutil.disk_usage') as mock_disk_usage:
                mock_disk_usage.return_value = MagicMock(
                    total=100 * 1024**3,  # 100GB
                    free=50 * 1024**3,    # 50GB
                    used=50 * 1024**3     # 50GB
                )
                
                status = await checker._check_file_system()
        
        assert status.name == "file_system"
        assert status.status == HealthStatus.HEALTHY
        assert "文件系统正常" in status.message
        assert status.details["temp_dir_exists"] is True
        assert status.details["temp_dir_writable"] is True
        assert status.details["free_space_gb"] > 1.0
    
    @pytest.mark.asyncio
    async def test_check_file_system_low_disk_space(self, mock_config):
        """测试文件系统磁盘空间不足"""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_config.file.temp_dir = temp_dir
            
            checker = HealthChecker(mock_config)
            
            with patch('shutil.disk_usage') as mock_disk_usage:
                mock_disk_usage.return_value = MagicMock(
                    total=2 * 1024**3,    # 2GB
                    free=0.5 * 1024**3,   # 0.5GB (小于1GB)
                    used=1.5 * 1024**3    # 1.5GB
                )
                
                status = await checker._check_file_system()
        
        assert status.name == "file_system"
        assert status.status == HealthStatus.DEGRADED
        assert "磁盘空间不足" in status.message
    
    @pytest.mark.asyncio
    async def test_check_file_system_failure(self, mock_config):
        """测试文件系统检查失败"""
        mock_config.file.temp_dir = "/invalid/path/that/cannot/be/created"
        
        checker = HealthChecker(mock_config)
        status = await checker._check_file_system()
        
        assert status.name == "file_system"
        assert status.status == HealthStatus.UNHEALTHY
        assert "文件系统检查失败" in status.message
    
    @pytest.mark.asyncio
    async def test_check_gemini_api_success(self, mock_config):
        """测试Gemini API检查成功"""
        checker = HealthChecker(mock_config)
        
        # Mock aiohttp response
        mock_response = MagicMock()
        mock_response.status = 200
        
        # 创建正确的异步上下文管理器mock
        async def mock_get(url):
            return mock_response
        
        with patch('aiohttp.ClientSession') as mock_client_session:
            mock_session = AsyncMock()
            mock_session.get = mock_get
            mock_client_session.return_value.__aenter__.return_value = mock_session
            mock_client_session.return_value.__aexit__.return_value = None
            
            status = await checker._check_gemini_api()
        
        assert status.name == "gemini_api"
        assert status.status == HealthStatus.HEALTHY
        assert "Gemini API连接正常" in status.message
        assert status.details["response_status"] == 200
    
    @pytest.mark.asyncio
    async def test_check_gemini_api_auth_error(self, mock_config):
        """测试Gemini API认证错误"""
        checker = HealthChecker(mock_config)
        
        # Mock aiohttp response with 401
        mock_response = MagicMock()
        mock_response.status = 401
        
        # 创建正确的异步上下文管理器mock
        async def mock_get(url):
            return mock_response
        
        with patch('aiohttp.ClientSession') as mock_client_session:
            mock_session = AsyncMock()
            mock_session.get = mock_get
            mock_client_session.return_value.__aenter__.return_value = mock_session
            mock_client_session.return_value.__aexit__.return_value = None
            
            status = await checker._check_gemini_api()
        
        assert status.name == "gemini_api"
        assert status.status == HealthStatus.HEALTHY  # 401表示连接正常但认证问题
        assert "Gemini API连接正常" in status.message
    
    @pytest.mark.asyncio
    async def test_check_gemini_api_timeout(self, mock_config):
        """测试Gemini API超时"""
        checker = HealthChecker(mock_config)
        
        async def mock_get_timeout(url):
            raise asyncio.TimeoutError()
        
        with patch('aiohttp.ClientSession') as mock_client_session:
            mock_session = AsyncMock()
            mock_session.get = mock_get_timeout
            mock_client_session.return_value.__aenter__.return_value = mock_session
            mock_client_session.return_value.__aexit__.return_value = None
            
            status = await checker._check_gemini_api()
        
        assert status.name == "gemini_api"
        assert status.status == HealthStatus.UNHEALTHY
        assert "Gemini API连接超时" in status.message
    
    @pytest.mark.asyncio
    async def test_check_kling_api_success(self, mock_config):
        """测试Kling API检查成功"""
        checker = HealthChecker(mock_config)
        
        # Mock aiohttp response
        mock_response = MagicMock()
        mock_response.status = 404  # 404也被认为是正常的
        
        async def mock_get(url):
            return mock_response
        
        with patch('aiohttp.ClientSession') as mock_client_session:
            mock_session = AsyncMock()
            mock_session.get = mock_get
            mock_client_session.return_value.__aenter__.return_value = mock_session
            mock_client_session.return_value.__aexit__.return_value = None
            
            status = await checker._check_kling_api()
        
        assert status.name == "kling_api"
        assert status.status == HealthStatus.HEALTHY
        assert "Kling API连接正常" in status.message
    
    @pytest.mark.asyncio
    async def test_check_kling_api_degraded(self, mock_config):
        """测试Kling API降级状态"""
        checker = HealthChecker(mock_config)
        
        # Mock aiohttp response with unusual status
        mock_response = MagicMock()
        mock_response.status = 500
        
        async def mock_get(url):
            return mock_response
        
        with patch('aiohttp.ClientSession') as mock_client_session:
            mock_session = AsyncMock()
            mock_session.get = mock_get
            mock_client_session.return_value.__aenter__.return_value = mock_session
            mock_client_session.return_value.__aexit__.return_value = None
            
            status = await checker._check_kling_api()
        
        assert status.name == "kling_api"
        assert status.status == HealthStatus.DEGRADED
        assert "Kling API响应异常" in status.message
    
    def test_add_check(self, mock_config):
        """测试添加自定义健康检查"""
        checker = HealthChecker(mock_config)
        
        async def custom_check():
            return ComponentStatus("custom", HealthStatus.HEALTHY, "OK")
        
        checker.add_check("custom", custom_check)
        
        assert "custom" in checker._checks
        assert checker._checks["custom"] is custom_check
    
    def test_remove_check(self, mock_config):
        """测试移除健康检查"""
        checker = HealthChecker(mock_config)
        
        # 移除存在的检查
        assert checker.remove_check("configuration") is True
        assert "configuration" not in checker._checks
        
        # 移除不存在的检查
        assert checker.remove_check("nonexistent") is False
    
    @pytest.mark.asyncio
    async def test_check_component(self, mock_config):
        """测试检查单个组件"""
        checker = HealthChecker(mock_config)
        
        # Mock configuration check
        mock_config.validate = MagicMock()
        
        result = await checker.check_component("configuration")
        
        assert result is not None
        assert result["name"] == "configuration"
        assert result["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_check_component_nonexistent(self, mock_config):
        """测试检查不存在的组件"""
        checker = HealthChecker(mock_config)
        
        result = await checker.check_component("nonexistent")
        assert result is None

class TestResourceMonitor:
    """测试ResourceMonitor类"""
    
    @pytest.fixture
    def mock_config(self):
        """创建模拟配置"""
        config = MagicMock()
        config.file.temp_dir = "/tmp/test"
        return config
    
    @pytest.mark.asyncio
    async def test_get_system_stats_with_psutil(self, mock_config):
        """测试获取系统统计（有psutil）"""
        monitor = ResourceMonitor(mock_config)
        
        # Mock psutil
        mock_psutil = MagicMock()
        mock_psutil.cpu_percent.return_value = 25.5
        mock_psutil.cpu_count.return_value = 4
        
        mock_memory = MagicMock()
        mock_memory.total = 8 * 1024**3
        mock_memory.available = 6 * 1024**3
        mock_memory.percent = 25.0
        mock_memory.used = 2 * 1024**3
        mock_psutil.virtual_memory.return_value = mock_memory
        
        mock_disk = MagicMock()
        mock_disk.total = 100 * 1024**3
        mock_disk.used = 40 * 1024**3
        mock_disk.free = 60 * 1024**3
        mock_psutil.disk_usage.return_value = mock_disk
        
        mock_psutil.net_connections.return_value = ["conn1", "conn2", "conn3"]
        
        with patch.dict('sys.modules', {'psutil': mock_psutil}):
            stats = await monitor.get_system_stats()
        
        assert "cpu" in stats
        assert stats["cpu"]["percent"] == 25.5
        assert stats["cpu"]["count"] == 4
        
        assert "memory" in stats
        assert stats["memory"]["total"] == 8 * 1024**3
        assert stats["memory"]["percent"] == 25.0
        
        assert "disk" in stats
        assert stats["disk"]["total"] == 100 * 1024**3
        assert stats["disk"]["percent"] == 40.0  # (used / total) * 100
        
        assert "network" in stats
        assert stats["network"]["connections"] == 3
        
        assert "timestamp" in stats
    
    @pytest.mark.asyncio
    async def test_get_system_stats_without_psutil(self, mock_config):
        """测试获取系统统计（没有psutil）"""
        monitor = ResourceMonitor(mock_config)
        
        # Mock ImportError for psutil by temporarily removing it from sys.modules
        import sys
        original_psutil = sys.modules.get('psutil')
        if 'psutil' in sys.modules:
            del sys.modules['psutil']
        
        # Mock import to raise ImportError
        def mock_import(name, *args, **kwargs):
            if name == 'psutil':
                raise ImportError("No module named 'psutil'")
            return __import__(name, *args, **kwargs)
        
        with patch('builtins.__import__', side_effect=mock_import):
            stats = await monitor.get_system_stats()
        
        # Restore original psutil module if it existed
        if original_psutil is not None:
            sys.modules['psutil'] = original_psutil
        
        assert "error" in stats
        assert "psutil未安装" in stats["error"]
        assert "timestamp" in stats
    
    @pytest.mark.asyncio
    async def test_get_system_stats_exception(self, mock_config):
        """测试获取系统统计时发生异常"""
        monitor = ResourceMonitor(mock_config)
        
        # Mock psutil with exception
        mock_psutil = MagicMock()
        mock_psutil.cpu_percent.side_effect = RuntimeError("Access denied")
        
        with patch.dict('sys.modules', {'psutil': mock_psutil}):
            stats = await monitor.get_system_stats()
        
        assert "error" in stats
        assert "Access denied" in stats["error"]
        assert "timestamp" in stats