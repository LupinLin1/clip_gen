"""
健康检查和状态监控模块

提供服务器健康检查和状态监控功能。
"""

import asyncio
import aiohttp
import time
from typing import Dict, Any, List, Optional
from enum import Enum
from pathlib import Path

from ..config import Config
from ..logger import get_logger
from ..exceptions import MCPError

class HealthStatus(Enum):
    """健康状态枚举"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"

class ComponentStatus:
    """组件状态"""
    
    def __init__(self, name: str, status: HealthStatus, 
                 message: str = "", details: Optional[Dict[str, Any]] = None):
        self.name = name
        self.status = status
        self.message = message
        self.details = details or {}
        self.timestamp = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp
        }

class HealthChecker:
    """健康检查器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = get_logger("health_checker")
        self._checks: Dict[str, callable] = {}
        self._setup_default_checks()
    
    def _setup_default_checks(self) -> None:
        """设置默认健康检查"""
        self._checks = {
            "configuration": self._check_configuration,
            "file_system": self._check_file_system,
            "gemini_api": self._check_gemini_api,
            "kling_api": self._check_kling_api
        }
    
    async def check_health(self) -> Dict[str, Any]:
        """执行完整健康检查"""
        self.logger.info("开始健康检查")
        start_time = time.time()
        
        results = {}
        overall_status = HealthStatus.HEALTHY
        
        # 并行执行所有健康检查
        tasks = []
        for check_name, check_func in self._checks.items():
            task = asyncio.create_task(self._run_check(check_name, check_func))
            tasks.append(task)
        
        # 等待所有检查完成
        check_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理检查结果
        for i, result in enumerate(check_results):
            check_name = list(self._checks.keys())[i]
            
            if isinstance(result, Exception):
                # 检查过程中发生异常
                component_status = ComponentStatus(
                    check_name,
                    HealthStatus.UNHEALTHY,
                    f"健康检查异常: {str(result)}"
                )
                overall_status = HealthStatus.UNHEALTHY
            else:
                component_status = result
                # 更新整体状态
                if component_status.status == HealthStatus.UNHEALTHY:
                    overall_status = HealthStatus.UNHEALTHY
                elif component_status.status == HealthStatus.DEGRADED and overall_status == HealthStatus.HEALTHY:
                    overall_status = HealthStatus.DEGRADED
            
            results[check_name] = component_status.to_dict()
        
        duration = time.time() - start_time
        
        health_report = {
            "status": overall_status.value,
            "timestamp": start_time,
            "duration": round(duration * 1000, 2),  # 毫秒
            "components": results,
            "version": "0.1.0"
        }
        
        self.logger.info(
            f"健康检查完成: {overall_status.value}",
            duration_ms=health_report["duration"],
            components_count=len(results)
        )
        
        return health_report
    
    async def _run_check(self, name: str, check_func: callable) -> ComponentStatus:
        """运行单个健康检查"""
        try:
            return await check_func()
        except Exception as e:
            self.logger.error(f"健康检查失败: {name}", error=str(e))
            return ComponentStatus(
                name,
                HealthStatus.UNHEALTHY,
                f"检查失败: {str(e)}"
            )
    
    async def _check_configuration(self) -> ComponentStatus:
        """检查配置"""
        try:
            # 验证配置
            self.config.validate()
            
            return ComponentStatus(
                "configuration",
                HealthStatus.HEALTHY,
                "配置验证通过"
            )
        
        except ValueError as e:
            return ComponentStatus(
                "configuration",
                HealthStatus.UNHEALTHY,
                f"配置验证失败: {str(e)}"
            )
    
    async def _check_file_system(self) -> ComponentStatus:
        """检查文件系统"""
        try:
            temp_dir = Path(self.config.file.temp_dir)
            
            # 检查临时目录是否存在且可写
            if not temp_dir.exists():
                temp_dir.mkdir(parents=True, exist_ok=True)
            
            # 尝试创建测试文件
            test_file = temp_dir / "health_check.tmp"
            test_file.write_text("health check test")
            test_file.unlink()  # 删除测试文件
            
            # 检查磁盘空间
            import shutil
            disk_usage = shutil.disk_usage(temp_dir)
            free_space_gb = disk_usage.free / (1024 ** 3)
            
            details = {
                "temp_dir": str(temp_dir),
                "temp_dir_exists": temp_dir.exists(),
                "temp_dir_writable": True,
                "free_space_gb": round(free_space_gb, 2)
            }
            
            if free_space_gb < 1.0:  # 小于1GB
                return ComponentStatus(
                    "file_system",
                    HealthStatus.DEGRADED,
                    f"磁盘空间不足: {free_space_gb:.2f}GB",
                    details
                )
            
            return ComponentStatus(
                "file_system",
                HealthStatus.HEALTHY,
                "文件系统正常",
                details
            )
        
        except Exception as e:
            return ComponentStatus(
                "file_system",
                HealthStatus.UNHEALTHY,
                f"文件系统检查失败: {str(e)}"
            )
    
    async def _check_gemini_api(self) -> ComponentStatus:
        """检查Gemini API连接"""
        try:
            # 简单的连接测试（不实际调用API，避免消费quota）
            timeout = aiohttp.ClientTimeout(total=5)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # 只是测试连接，不发送实际请求
                url = f"{self.config.gemini.base_url}/v1/models"
                
                try:
                    async with session.get(url) as response:
                        status_code = response.status
                        
                        details = {
                            "base_url": self.config.gemini.base_url,
                            "response_status": status_code,
                            "api_key_configured": bool(self.config.gemini.api_key)
                        }
                        
                        if status_code in [200, 401, 403]:  # 401/403表示连接正常但认证问题
                            return ComponentStatus(
                                "gemini_api",
                                HealthStatus.HEALTHY,
                                "Gemini API连接正常",
                                details
                            )
                        else:
                            return ComponentStatus(
                                "gemini_api",
                                HealthStatus.DEGRADED,
                                f"Gemini API响应异常: {status_code}",
                                details
                            )
                            
                except asyncio.TimeoutError:
                    return ComponentStatus(
                        "gemini_api",
                        HealthStatus.UNHEALTHY,
                        "Gemini API连接超时",
                        {"base_url": self.config.gemini.base_url}
                    )
        
        except Exception as e:
            return ComponentStatus(
                "gemini_api",
                HealthStatus.UNHEALTHY,
                f"Gemini API检查失败: {str(e)}"
            )
    
    async def _check_kling_api(self) -> ComponentStatus:
        """检查Kling API连接"""
        try:
            # 简单的连接测试
            timeout = aiohttp.ClientTimeout(total=5)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # 测试连接到Kling API
                url = self.config.kling.base_url
                
                try:
                    async with session.get(url) as response:
                        status_code = response.status
                        
                        details = {
                            "base_url": self.config.kling.base_url,
                            "response_status": status_code,
                            "api_key_configured": bool(self.config.kling.api_key)
                        }
                        
                        if status_code in [200, 401, 403, 404]:  # 404也可能是正常的
                            return ComponentStatus(
                                "kling_api",
                                HealthStatus.HEALTHY,
                                "Kling API连接正常",
                                details
                            )
                        else:
                            return ComponentStatus(
                                "kling_api",
                                HealthStatus.DEGRADED,
                                f"Kling API响应异常: {status_code}",
                                details
                            )
                            
                except asyncio.TimeoutError:
                    return ComponentStatus(
                        "kling_api",
                        HealthStatus.UNHEALTHY,
                        "Kling API连接超时",
                        {"base_url": self.config.kling.base_url}
                    )
        
        except Exception as e:
            return ComponentStatus(
                "kling_api",
                HealthStatus.UNHEALTHY,
                f"Kling API检查失败: {str(e)}"
            )
    
    def add_check(self, name: str, check_func: callable) -> None:
        """添加自定义健康检查"""
        self._checks[name] = check_func
        self.logger.info(f"添加健康检查: {name}")
    
    def remove_check(self, name: str) -> bool:
        """移除健康检查"""
        if name in self._checks:
            del self._checks[name]
            self.logger.info(f"移除健康检查: {name}")
            return True
        return False
    
    async def check_component(self, component_name: str) -> Optional[Dict[str, Any]]:
        """检查单个组件"""
        if component_name not in self._checks:
            return None
        
        check_func = self._checks[component_name]
        result = await self._run_check(component_name, check_func)
        return result.to_dict()

class ResourceMonitor:
    """资源监控器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = get_logger("resource_monitor")
    
    async def get_system_stats(self) -> Dict[str, Any]:
        """获取系统资源统计"""
        try:
            import psutil
            
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 内存使用情况
            memory = psutil.virtual_memory()
            
            # 磁盘使用情况
            disk = psutil.disk_usage(self.config.file.temp_dir)
            
            # 网络连接数
            connections = len(psutil.net_connections())
            
            return {
                "cpu": {
                    "percent": cpu_percent,
                    "count": psutil.cpu_count()
                },
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent,
                    "used": memory.used
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": (disk.used / disk.total) * 100
                },
                "network": {
                    "connections": connections
                },
                "timestamp": time.time()
            }
            
        except ImportError:
            self.logger.warning("psutil未安装，无法获取系统资源统计")
            return {
                "error": "psutil未安装",
                "timestamp": time.time()
            }
        except Exception as e:
            self.logger.error(f"获取系统统计失败: {e}")
            return {
                "error": str(e),
                "timestamp": time.time()
            }