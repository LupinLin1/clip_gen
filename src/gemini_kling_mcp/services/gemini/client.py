"""
Gemini HTTP 客户端

提供与 Google Gemini API 的 HTTP 通信功能，包括重试机制和错误处理。
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional, Union, List
from urllib.parse import urljoin
import aiohttp
import httpx
from aiohttp import ClientSession, ClientTimeout, ClientError

from ...config import GeminiConfig
from ...logger import get_logger
from ...exceptions import NetworkError, ValidationError
from .models import GeminiApiResponse, GeminiError, GeminiModel, ImageModel

class GeminiHTTPError(NetworkError):
    """Gemini HTTP 错误"""
    
    def __init__(self, message: str, status_code: Optional[int] = None, 
                 response_data: Optional[Dict[str, Any]] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.status_code = status_code
        self.response_data = response_data or {}

class GeminiClient:
    """Gemini API HTTP 客户端"""
    
    def __init__(self, config: GeminiConfig):
        self.config = config
        self.logger = get_logger("gemini_client")
        self.base_url = config.base_url.rstrip('/')
        self.session: Optional[ClientSession] = None
        
        # API 端点（gptproto.com 格式）
        self.endpoints = {
            "generate": "/v1/chat/completions",
            "chat": "/v1/chat/completions", 
            "analyze": "/v1/chat/completions",
            # 图像API端点
            "image_generate": "/v1/images/generations",
            "image_edit": "/v1/images/edits",
            "image_analyze": "/v1/chat/completions"
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
            timeout = ClientTimeout(total=self.config.timeout)
            
            # 设置请求头
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "gemini-kling-mcp-service/0.1.0",
                "X-Goog-Api-Key": self.config.api_key
            }
            
            self.session = ClientSession(
                timeout=timeout,
                headers=headers,
                connector=aiohttp.TCPConnector(limit=100)
            )
            
            self.logger.debug("已创建 HTTP 会话")
    
    async def close(self) -> None:
        """关闭客户端"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.logger.debug("已关闭 HTTP 会话")
    
    def _get_endpoint_url(self, endpoint_key: str, model: Union[str, GeminiModel, ImageModel]) -> str:
        """获取端点URL（gptproto.com 格式，模型在请求体中指定）"""
        endpoint = self.endpoints[endpoint_key]
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
                if response.status == 200:
                    try:
                        response_data = json.loads(response_text)
                        return response_data
                    except json.JSONDecodeError as e:
                        self.logger.error(f"响应JSON解析失败: {e}", response_text=response_text[:500])
                        raise GeminiHTTPError(
                            f"响应格式错误: {e}",
                            status_code=response.status,
                            response_data={"raw_response": response_text[:500]}
                        )
                
                # 处理错误响应
                try:
                    error_data = json.loads(response_text)
                except json.JSONDecodeError:
                    error_data = {"message": response_text}
                
                error_message = self._extract_error_message(error_data, response.status)
                
                # 检查是否需要重试
                if self._should_retry(response.status, retry_count):
                    await self._wait_before_retry(retry_count)
                    return await self._make_request(
                        method, url, json_data, params, retry_count + 1
                    )
                
                # 抛出错误
                raise GeminiHTTPError(
                    error_message,
                    status_code=response.status,
                    response_data=error_data
                )
        
        except ClientError as e:
            # 网络错误处理
            error_message = f"网络请求失败: {str(e)}"
            self.logger.error(error_message, exception=str(e))
            
            # 检查是否需要重试
            if retry_count < self.config.max_retries:
                await self._wait_before_retry(retry_count)
                return await self._make_request(
                    method, url, json_data, params, retry_count + 1
                )
            
            raise GeminiHTTPError(error_message, details={"original_error": str(e)})
        
        except asyncio.TimeoutError:
            error_message = f"请求超时 (超过 {self.config.timeout}s)"
            self.logger.error(error_message)
            
            # 超时也可以重试
            if retry_count < self.config.max_retries:
                await self._wait_before_retry(retry_count)
                return await self._make_request(
                    method, url, json_data, params, retry_count + 1
                )
            
            raise GeminiHTTPError(error_message)
    
    def _extract_error_message(self, error_data: Dict[str, Any], status_code: int) -> str:
        """提取错误消息"""
        if "error" in error_data:
            error_info = error_data["error"]
            if isinstance(error_info, dict):
                return error_info.get("message", f"API错误 (状态码: {status_code})")
            else:
                return str(error_info)
        elif "message" in error_data:
            return error_data["message"]
        else:
            return f"未知API错误 (状态码: {status_code})"
    
    def _should_retry(self, status_code: int, retry_count: int) -> bool:
        """判断是否应该重试"""
        if retry_count >= self.config.max_retries:
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
    
    async def generate_content(
        self, 
        model: Union[str, GeminiModel],
        request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """生成内容"""
        url = self._get_endpoint_url("generate", model)
        return await self._make_request("POST", url, json_data=request_data)
    
    async def chat_completion(
        self,
        model: Union[str, GeminiModel], 
        request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """对话完成（实际上与 generate_content 使用相同的端点）"""
        url = self._get_endpoint_url("chat", model)
        return await self._make_request("POST", url, json_data=request_data)
    
    async def analyze_text(
        self,
        model: Union[str, GeminiModel],
        request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """文本分析（使用相同的生成端点）"""
        url = self._get_endpoint_url("analyze", model)
        return await self._make_request("POST", url, json_data=request_data)
    
    def parse_response(self, response: Dict[str, Any]) -> GeminiApiResponse:
        """解析API响应"""
        try:
            return GeminiApiResponse(**response)
        except Exception as e:
            self.logger.error(f"响应解析失败: {e}", response_data=response)
            raise ValidationError(f"响应格式错误: {e}", details={"response": response})
    
    def extract_generated_text(self, response: Dict[str, Any]) -> str:
        """从响应中提取生成的文本（支持OpenAI和Gemini格式）"""
        try:
            # 优先检查 OpenAI 格式 (gptproto.com)
            if "choices" in response and response["choices"]:
                choice = response["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    return choice["message"]["content"]
                elif "text" in choice:  # completion 格式
                    return choice["text"]
            
            # 检查 Gemini 原生格式
            if "candidates" in response and response["candidates"]:
                candidate = response["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    parts = candidate["content"]["parts"]
                    if parts and "text" in parts[0]:
                        return parts[0]["text"]
                        
            # 尝试其他格式
            if "text" in response:
                return response["text"]
                
            self.logger.warning("无法从响应中提取文本", response_keys=list(response.keys()))
            return ""
            
        except Exception as e:
            self.logger.error(f"提取文本失败: {e}", response_data=response)
            return ""
    
    def extract_usage_info(self, response: Dict[str, Any]) -> Optional[Dict[str, int]]:
        """从响应中提取使用信息（支持OpenAI和Gemini格式）"""
        try:
            # 优先检查 OpenAI 格式 (gptproto.com)
            if "usage" in response:
                usage_data = response["usage"]
                return {
                    "prompt_tokens": usage_data.get("prompt_tokens", 0),
                    "completion_tokens": usage_data.get("completion_tokens", 0), 
                    "total_tokens": usage_data.get("total_tokens", 0)
                }
            
            # 检查 Gemini 原生格式
            if "usageMetadata" in response:
                usage_data = response["usageMetadata"]
                return {
                    "prompt_tokens": usage_data.get("promptTokenCount", 0),
                    "completion_tokens": usage_data.get("candidatesTokenCount", 0), 
                    "total_tokens": usage_data.get("totalTokenCount", 0)
                }
            return None
        except Exception as e:
            self.logger.error(f"提取使用信息失败: {e}", response_data=response)
            return None
    
    def extract_safety_ratings(self, response: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """从响应中提取安全评级"""
        try:
            if "candidates" in response and response["candidates"]:
                candidate = response["candidates"][0]
                return candidate.get("safetyRatings", [])
            return None
        except Exception as e:
            self.logger.error(f"提取安全评级失败: {e}", response_data=response)
            return None
    
    # 图像相关方法
    async def generate_image(
        self, 
        model: Union[str, ImageModel],
        request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """生成图像"""
        url = self._get_endpoint_url("image_generate", model)
        return await self._make_request("POST", url, json_data=request_data)
    
    async def edit_image(
        self,
        model: Union[str, ImageModel],
        request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """编辑图像"""
        url = self._get_endpoint_url("image_edit", model)
        return await self._make_request("POST", url, json_data=request_data)
    
    async def analyze_image(
        self,
        model: Union[str, GeminiModel],
        request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """分析图像（使用multimodal生成端点）"""
        url = self._get_endpoint_url("image_analyze", model)
        return await self._make_request("POST", url, json_data=request_data)
    
    def extract_image_data(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从响应中提取图像数据"""
        try:
            images = []
            
            # 检查不同的响应格式
            if "images" in response:
                # 直接图像列表
                for img_data in response["images"]:
                    if "data" in img_data:
                        images.append(img_data)
            
            elif "candidates" in response and response["candidates"]:
                # Gemini格式响应
                candidate = response["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    for part in candidate["content"]["parts"]:
                        if "inlineData" in part:
                            images.append(part["inlineData"])
            
            # 兼容其他格式
            if not images and "data" in response:
                images.append(response)
            
            return images
            
        except Exception as e:
            self.logger.error(f"提取图像数据失败: {e}", response_data=response)
            return []
    
    def extract_image_analysis(self, response: Dict[str, Any]) -> str:
        """从响应中提取图像分析结果"""
        try:
            # 优先使用text提取方法
            analysis = self.extract_generated_text(response)
            if analysis:
                return analysis
            
            # 检查其他格式
            if "analysis" in response:
                return response["analysis"]
            
            if "description" in response:
                return response["description"]
            
            self.logger.warning("无法从响应中提取图像分析", response_keys=list(response.keys()))
            return ""
            
        except Exception as e:
            self.logger.error(f"提取图像分析失败: {e}", response_data=response)
            return ""