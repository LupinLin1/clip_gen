"""
pytest配置和共用fixtures

提供测试所需的配置、fixtures和工具函数。
"""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, AsyncMock, Mock
from typing import Dict, Any, Generator, AsyncGenerator

from src.gemini_kling_mcp.config import GeminiConfig, KlingConfig, FileConfig, Config
from src.gemini_kling_mcp.workflow import WorkflowEngine, WorkflowStateManager
from tests.mocks import (
    create_mock_gemini_service,
    create_mock_gemini_image_service, 
    create_mock_kling_service,
    create_mock_gemini_client,
    create_mock_kling_client
)
from tests.test_data_generator import test_data_generator


# pytest配置
def pytest_configure(config):
    """pytest配置"""
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "e2e: marks tests as end-to-end tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )


# 异步测试配置
@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# 配置fixtures
@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    """创建临时目录"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def gemini_config() -> GeminiConfig:
    """测试用Gemini配置"""
    return GeminiConfig(
        api_key="test-gemini-key",
        base_url="https://gptproto.com",
        timeout=30,
        max_retries=3
    )


@pytest.fixture
def kling_config() -> KlingConfig:
    """测试用Kling配置"""
    return KlingConfig(
        api_key="test-kling-key",
        base_url="https://api.klingai.com",
        timeout=300,
        max_retries=3
    )


@pytest.fixture
def file_config(temp_dir: str) -> FileConfig:
    """测试用文件配置"""
    return FileConfig(
        temp_dir=temp_dir,
        max_file_size=10 * 1024 * 1024,  # 10MB
        cleanup_interval=3600,
        allowed_formats=["jpg", "png", "mp4", "txt", "json"]
    )


@pytest.fixture
def test_config(gemini_config: GeminiConfig, kling_config: KlingConfig, 
                file_config: FileConfig) -> Config:
    """测试用完整配置"""
    return Config(
        server=Mock(),
        gemini=gemini_config,
        kling=kling_config,
        file=file_config
    )


# Mock服务fixtures
@pytest.fixture
def mock_gemini_service():
    """Mock Gemini服务"""
    return create_mock_gemini_service(enable_errors=False)


@pytest.fixture
def mock_gemini_service_with_errors():
    """带错误的Mock Gemini服务"""
    return create_mock_gemini_service(enable_errors=True)


@pytest.fixture
def mock_gemini_image_service():
    """Mock Gemini图像服务"""
    return create_mock_gemini_image_service(enable_errors=False)


@pytest.fixture
def mock_kling_service():
    """Mock Kling服务"""
    return create_mock_kling_service(enable_errors=False)


@pytest.fixture
def mock_gemini_client(gemini_config: GeminiConfig):
    """Mock Gemini客户端"""
    return create_mock_gemini_client(gemini_config, enable_errors=False)


@pytest.fixture
def mock_kling_client(kling_config: KlingConfig):
    """Mock Kling客户端"""
    return create_mock_kling_client(kling_config, enable_errors=False)


# 工作流fixtures
@pytest.fixture
def workflow_engine(temp_dir: str):
    """工作流引擎fixture"""
    from src.gemini_kling_mcp.workflow.state_manager import JSONFileBackend
    backend = JSONFileBackend(temp_dir)
    state_manager = WorkflowStateManager(backend)
    return WorkflowEngine(state_manager)


@pytest.fixture
def sample_workflow_steps() -> list:
    """示例工作流步骤"""
    return test_data_generator.generate_workflow_steps(5)


@pytest.fixture
def sample_workflow_context() -> Dict[str, Any]:
    """示例工作流上下文"""
    return test_data_generator.generate_workflow_context()


# 数据fixtures
@pytest.fixture
def sample_text_request():
    """示例文本生成请求"""
    return test_data_generator.generate_gemini_text_request()


@pytest.fixture
def sample_chat_request():
    """示例对话请求"""
    return test_data_generator.generate_gemini_chat_request()


@pytest.fixture
def sample_image_request():
    """示例图像请求"""
    return test_data_generator.generate_image_request()


@pytest.fixture
def sample_video_request():
    """示例视频请求"""
    return test_data_generator.generate_video_request()


@pytest.fixture
def sample_api_response():
    """示例API响应"""
    return test_data_generator.generate_api_response("text")


@pytest.fixture
def sample_error_response():
    """示例错误响应"""
    return test_data_generator.generate_error_response(400)


# 性能测试fixtures
@pytest.fixture
def performance_metrics():
    """性能指标"""
    return test_data_generator.generate_performance_metrics()


@pytest.fixture
def batch_test_data():
    """批量测试数据"""
    return test_data_generator.generate_batch_test_data(10)


# Mock网络请求fixtures
@pytest.fixture
def mock_http_responses():
    """Mock HTTP响应"""
    with patch('aiohttp.ClientSession') as mock_session:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=test_data_generator.generate_api_response("text"))
        mock_response.text = AsyncMock(return_value='{"success": true}')
        
        mock_session.return_value.__aenter__.return_value.request.return_value.__aenter__.return_value = mock_response
        yield mock_session


@pytest.fixture
def mock_file_operations():
    """Mock文件操作"""
    with patch('builtins.open'), \
         patch('os.makedirs'), \
         patch('os.path.exists', return_value=True), \
         patch('shutil.rmtree'):
        yield


# 测试环境清理fixtures
@pytest.fixture(autouse=True)
def reset_test_environment():
    """重置测试环境"""
    # 测试前设置
    yield
    # 测试后清理
    test_data_generator.fake.seed_instance(42)  # 重置随机种子


# 错误模拟fixtures
@pytest.fixture
def simulate_network_error():
    """模拟网络错误"""
    def _simulate_error(error_type="timeout", rate=1.0):
        def side_effect(*args, **kwargs):
            import random
            if random.random() < rate:
                if error_type == "timeout":
                    raise asyncio.TimeoutError("Simulated timeout")
                elif error_type == "connection":
                    raise ConnectionError("Simulated connection error")
                else:
                    raise Exception(f"Simulated {error_type} error")
            return AsyncMock()
        return side_effect
    
    return _simulate_error


# 数据库fixtures（如果需要）
@pytest.fixture
def mock_database():
    """Mock数据库连接"""
    with patch('sqlite3.connect') as mock_conn:
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.fetchall.return_value = []
        mock_cursor.execute.return_value = None
        
        mock_conn.return_value.cursor.return_value = mock_cursor
        mock_conn.return_value.commit.return_value = None
        mock_conn.return_value.close.return_value = None
        
        yield mock_conn


# 日志fixtures
@pytest.fixture
def capture_logs():
    """捕获日志输出"""
    import logging
    from io import StringIO
    
    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.DEBUG)
    
    # 获取根logger
    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    
    yield log_capture
    
    logger.removeHandler(handler)


# 时间Mock fixtures
@pytest.fixture
def mock_time():
    """Mock时间函数"""
    with patch('time.time', return_value=1640995200.0), \
         patch('time.sleep'):
        yield


@pytest.fixture
def mock_datetime():
    """Mock datetime"""
    from datetime import datetime, timezone
    fixed_time = datetime(2022, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    
    with patch('datetime.datetime') as mock_dt:
        mock_dt.now.return_value = fixed_time
        mock_dt.utcnow.return_value = fixed_time
        yield mock_dt


# 并发测试fixtures
@pytest.fixture
def concurrency_limit():
    """并发限制"""
    return asyncio.Semaphore(5)


# 测试工具fixtures
@pytest.fixture
def assert_helpers():
    """断言辅助函数"""
    class AssertHelpers:
        @staticmethod
        def assert_valid_response(response, expected_keys=None):
            """验证响应格式"""
            assert isinstance(response, dict)
            assert "success" in response
            if expected_keys:
                for key in expected_keys:
                    assert key in response
        
        @staticmethod
        def assert_error_response(response, expected_error_code=None):
            """验证错误响应格式"""
            assert isinstance(response, dict)
            assert "error" in response or "success" in response
            if response.get("success") is not False:
                assert "error" in response
        
        @staticmethod
        def assert_performance_within_limits(duration, max_duration):
            """验证性能在限制内"""
            assert duration <= max_duration, f"执行时间 {duration}s 超过限制 {max_duration}s"
    
    return AssertHelpers()


# 参数化测试数据
@pytest.fixture(params=["text", "image", "video"])
def content_type(request):
    """内容类型参数化"""
    return request.param


@pytest.fixture(params=[1, 3, 5])
def batch_size(request):
    """批量大小参数化"""
    return request.param


@pytest.fixture(params=[False, True])
def enable_errors(request):
    """是否启用错误参数化"""
    return request.param