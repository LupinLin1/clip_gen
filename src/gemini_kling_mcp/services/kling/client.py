"""
Kling HTTP 客户端

提供与 Kling AI API 的 HTTP 通信功能，包括重试机制和错误处理。
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional, Union, List
from urllib.parse import urljoin
import aiohttp
from aiohttp import ClientSession, ClientTimeout, ClientError

from ...config import Config
from ...logger import get_logger
from ...exceptions import NetworkError, ValidationError
from .models import (
    KlingVideoRequest, 
    KlingVideoResponse, 
    KlingTaskStatus,
    KlingError,
    KlingValidationError,
    KlingTaskError,
    KlingQuotaError
)

class KlingHTTPError(NetworkError):
    """Kling HTTP 错误"""
    
    def __init__(self, message: str, status_code: Optional[int] = None, 
                 response_data: Optional[Dict[str, Any]] = None, 
                 error_code: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.status_code = status_code
        self.response_data = response_data or {}
        self.error_code = error_code

class KlingClient:
    """Kling API HTTP 客户端"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.minimax.chat"):
        """
        初始化 Kling 客户端
        
        Args:
            api_key: Kling API 密钥
            base_url: API 基础 URL
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.logger = get_logger("kling_client")
        self.session: Optional[ClientSession] = None
        
        # 请求配置
        self.timeout = 300  # 5分钟超时
        self.max_retries = 3
        
        # API 端点
        self.endpoints = {
            "text_to_video": "/v1/video_generation",
            "image_to_video": "/v1/video_generation",
            "task_status": "/v1/query/{task_id}",
            "task_list": "/v1/query",
        }
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        await self.close()
    
    async def _ensure_session(self) -> None:
        """确保会话已创建"""
        if self.session is None or self.session.closed:
            timeout = ClientTimeout(total=self.timeout)
            
            # 设置请求头
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "gemini-kling-mcp-service/0.1.0",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            self.session = ClientSession(
                timeout=timeout,
                headers=headers,
                connector=aiohttp.TCPConnector(limit=10)
            )
            
            self.logger.debug("已创建 HTTP 会话")
    
    async def close(self) -> None:
        """关闭客户端"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.logger.debug("已关闭 HTTP 会话")
    
    def _get_endpoint_url(self, endpoint_key: str, **kwargs) -> str:
        """获取端点URL"""
        endpoint = self.endpoints[endpoint_key].format(**kwargs)
        return urljoin(self.base_url, endpoint)
    
    async def _make_request(
        self,
        method: str,
        url: str, 
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """执行HTTP请求"""
        await self._ensure_session()
        
        try:
            # 记录请求开始
            request_id = f"req_{int(time.time() * 1000)}"
            self.logger.debug(
                f"发送 {method} 请求",
                request_id=request_id,
                url=url,
                data_size=len(json.dumps(json_data) if json_data else "{}"),
                retry_count=retry_count
            )
            
            start_time = time.time()
            
            async with self.session.request(
                method=method,
                url=url,
                json=json_data,
                params=params
            ) as response:
                duration = time.time() - start_time
                response_text = await response.text()
                
                # 记录响应
                self.logger.debug(
                    f"收到响应",
                    request_id=request_id,
                    status_code=response.status,
                    duration=duration,
                    response_size=len(response_text)
                )
                
                # 处理响应
                if response.status in (200, 201, 202):
                    try:
                        response_data = json.loads(response_text)
                        return response_data
                    except json.JSONDecodeError as e:
                        self.logger.error(f"响应JSON解析失败: {e}", response_text=response_text[:500])
                        raise KlingHTTPError(
                            f"响应格式错误: {e}",
                            status_code=response.status,
                            response_data={"raw_response": response_text[:500]}
                        )
                
                # 处理错误响应
                try:
                    error_data = json.loads(response_text)
                except json.JSONDecodeError:
                    error_data = {"message": response_text}
                
                error_message, error_code = self._extract_error_info(error_data, response.status)
                
                # 检查是否需要重试
                if self._should_retry(response.status, retry_count):
                    await self._wait_before_retry(retry_count)
                    return await self._make_request(
                        method, url, json_data, params, retry_count + 1
                    )
                
                # 抛出特定错误类型
                exception_class = self._get_exception_class(response.status, error_code)
                raise exception_class(
                    error_message,
                    status_code=response.status,
                    response_data=error_data,
                    error_code=error_code
                )
        
        except ClientError as e:
            # 网络错误处理
            error_message = f"网络请求失败: {str(e)}"
            self.logger.error(error_message, exception=str(e))
            
            # 检查是否需要重试
            if retry_count < self.max_retries:
                await self._wait_before_retry(retry_count)
                return await self._make_request(
                    method, url, json_data, params, retry_count + 1
                )
            
            raise KlingHTTPError(error_message, details={"original_error": str(e)})
        
        except asyncio.TimeoutError:
            error_message = f"请求超时 (超过 {self.timeout}s)"
            self.logger.error(error_message)
            
            # 超时也可以重试
            if retry_count < self.max_retries:
                await self._wait_before_retry(retry_count)
                return await self._make_request(
                    method, url, json_data, params, retry_count + 1
                )
            
            raise KlingHTTPError(error_message)
    
    def _extract_error_info(self, error_data: Dict[str, Any], status_code: int) -> tuple[str, Optional[str]]:
        """提取错误信息和错误代码"""
        error_message = f"API错误 (状态码: {status_code})"
        error_code = None
        
        if "error" in error_data:
            error_info = error_data["error"]
            if isinstance(error_info, dict):
                error_message = error_info.get("message", error_message)
                error_code = error_info.get("code")
            else:
                error_message = str(error_info)
        elif "message" in error_data:
            error_message = error_data["message"]
            error_code = error_data.get("code")
        elif "base_resp" in error_data:
            # MiniMax API 格式
            base_resp = error_data["base_resp"]
            error_message = base_resp.get("status_msg", error_message)
            error_code = str(base_resp.get("status_code", ""))
        
        return error_message, error_code
    
    def _get_exception_class(self, status_code: int, error_code: Optional[str]):
        """根据状态码和错误代码选择异常类型"""
        if status_code == 400:
            return KlingValidationError
        elif status_code in (402, 429):
            return KlingQuotaError
        elif status_code >= 500:
            return KlingTaskError
        else:
            return KlingHTTPError
    
    def _should_retry(self, status_code: int, retry_count: int) -> bool:
        """判断是否应该重试"""
        if retry_count >= self.max_retries:
            return False
        
        # 可重试的状态码
        retryable_status = {
            429,  # Too Many Requests
            500,  # Internal Server Error
            502,  # Bad Gateway
            503,  # Service Unavailable
            504,  # Gateway Timeout
        }
        
        return status_code in retryable_status
    
    async def _wait_before_retry(self, retry_count: int) -> None:
        """重试前等待（指数退避）"""
        wait_time = min(2 ** retry_count, 60)  # 最大等待60秒
        self.logger.info(f"等待 {wait_time}s 后重试 (第 {retry_count + 1} 次)")
        await asyncio.sleep(wait_time)
    
    async def text_to_video(self, request: KlingVideoRequest) -> KlingVideoResponse:
        """
        文本生成视频
        
        Args:
            request: 视频生成请求
            
        Returns:
            KlingVideoResponse: 视频生成响应
        """
        url = self._get_endpoint_url("text_to_video")
        request_data = request.to_dict()
        
        # 移除图像相关字段
        request_data.pop("image", None)
        request_data.pop("image_url", None)
        
        self.logger.info(
            "发起文本生成视频请求",
            prompt=request.prompt[:100] + "..." if len(request.prompt) > 100 else request.prompt,
            model=request.config.model.value,
            duration=request.config.duration.value
        )
        
        response_data = await self._make_request("POST", url, json_data=request_data)
        return KlingVideoResponse.from_api_response(response_data)
    
    async def image_to_video(self, request: KlingVideoRequest) -> KlingVideoResponse:
        """
        图像生成视频
        
        Args:
            request: 视频生成请求（必须包含图像数据）
            
        Returns:
            KlingVideoResponse: 视频生成响应
        """
        if not request.image and not request.image_url:
            raise KlingValidationError("图像生成视频需要提供图像数据或图像URL")
        
        url = self._get_endpoint_url("image_to_video")
        request_data = request.to_dict()
        
        self.logger.info(
            "发起图像生成视频请求",
            prompt=request.prompt[:100] + "..." if len(request.prompt) > 100 else request.prompt,
            has_image=bool(request.image),
            has_image_url=bool(request.image_url),
            model=request.config.model.value
        )
        
        response_data = await self._make_request("POST", url, json_data=request_data)
        return KlingVideoResponse.from_api_response(response_data)
    
    async def get_task_status(self, task_id: str) -> KlingVideoResponse:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            KlingVideoResponse: 任务状态响应
        """
        url = self._get_endpoint_url("task_status", task_id=task_id)
        
        self.logger.debug(f"查询任务状态: {task_id}")
        
        response_data = await self._make_request("GET", url)
        return KlingVideoResponse.from_api_response(response_data)
    
    async def list_tasks(
        self, 
        limit: int = 20, 
        status: Optional[KlingTaskStatus] = None
    ) -> List[KlingVideoResponse]:
        """
        获取任务列表
        
        Args:
            limit: 返回任务数量限制
            status: 过滤任务状态
            
        Returns:
            List[KlingVideoResponse]: 任务列表
        """
        url = self._get_endpoint_url("task_list")
        params = {"limit": limit}
        
        if status:
            params["status"] = status.value
        
        self.logger.debug(f"获取任务列表, limit={limit}, status={status}")
        
        response_data = await self._make_request("GET", url, params=params)
        
        tasks = []
        if "tasks" in response_data:
            for task_data in response_data["tasks"]:
                tasks.append(KlingVideoResponse.from_api_response(task_data))
        
        return tasks
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功取消
        """
        url = self._get_endpoint_url("task_status", task_id=task_id)
        
        self.logger.info(f"取消任务: {task_id}")
        
        try:
            await self._make_request("DELETE", url)
            return True
        except KlingHTTPError as e:
            if e.status_code == 404:
                self.logger.warning(f"任务不存在: {task_id}")
                return False
            raise