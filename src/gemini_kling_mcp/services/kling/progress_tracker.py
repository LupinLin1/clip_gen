"""
Kling 进度跟踪器

提供异步任务进度跟踪功能，包括轮询状态、进度回调等。
"""

import asyncio
from typing import Dict, Any, Optional, Callable, Awaitable
from datetime import datetime, timedelta
import time

from ...logger import get_logger
from .models import KlingVideoResponse, KlingTaskStatus
from .client import KlingClient, KlingHTTPError

# 进度回调函数类型
ProgressCallback = Callable[[KlingVideoResponse], Awaitable[None]]

class KlingProgressTracker:
    """Kling 任务进度跟踪器"""
    
    def __init__(self, client: KlingClient):
        """
        初始化进度跟踪器
        
        Args:
            client: Kling API 客户端
        """
        self.client = client
        self.logger = get_logger("kling_progress_tracker")
        
        # 跟踪配置
        self.poll_interval = 5  # 轮询间隔（秒）
        self.max_wait_time = 1800  # 最大等待时间（30分钟）
        
        # 活动任务跟踪
        self._tracking_tasks: Dict[str, asyncio.Task] = {}
        self._task_callbacks: Dict[str, ProgressCallback] = {}
    
    async def track_task(
        self, 
        task_id: str,
        progress_callback: Optional[ProgressCallback] = None,
        timeout: Optional[int] = None
    ) -> KlingVideoResponse:
        """
        跟踪单个任务直到完成
        
        Args:
            task_id: 任务ID
            progress_callback: 进度回调函数
            timeout: 超时时间（秒）
            
        Returns:
            KlingVideoResponse: 最终任务结果
        """
        timeout = timeout or self.max_wait_time
        start_time = time.time()
        
        self.logger.info(f"开始跟踪任务: {task_id}")
        
        while True:
            try:
                # 获取任务状态
                response = await self.client.get_task_status(task_id)
                
                # 调用进度回调
                if progress_callback:
                    try:
                        await progress_callback(response)
                    except Exception as e:
                        self.logger.error(f"进度回调执行失败: {e}", task_id=task_id)
                
                # 记录进度
                if response.task_info:
                    self.logger.debug(
                        f"任务进度更新",
                        task_id=task_id,
                        status=response.status.value,
                        progress=response.task_info.progress,
                        estimated_time=response.task_info.estimated_time
                    )
                
                # 检查任务状态
                if response.status == KlingTaskStatus.COMPLETED:
                    self.logger.info(f"任务完成: {task_id}")
                    return response
                    
                elif response.status == KlingTaskStatus.FAILED:
                    error_msg = "任务失败"
                    if response.task_info and response.task_info.error_message:
                        error_msg += f": {response.task_info.error_message}"
                    
                    self.logger.error(error_msg, task_id=task_id)
                    return response
                    
                elif response.status == KlingTaskStatus.CANCELLED:
                    self.logger.warning(f"任务已取消: {task_id}")
                    return response
                
                # 检查超时
                if time.time() - start_time > timeout:
                    self.logger.error(f"任务跟踪超时: {task_id}")
                    raise asyncio.TimeoutError(f"任务 {task_id} 跟踪超时")
                
                # 等待下次轮询
                await asyncio.sleep(self.poll_interval)
                
            except KlingHTTPError as e:
                if e.status_code == 404:
                    self.logger.error(f"任务不存在: {task_id}")
                    raise
                else:
                    self.logger.warning(f"获取任务状态失败，将重试: {e}", task_id=task_id)
                    await asyncio.sleep(self.poll_interval)
            
            except Exception as e:
                self.logger.error(f"跟踪任务时发生未知错误: {e}", task_id=task_id)
                raise
    
    async def start_background_tracking(
        self, 
        task_id: str,
        progress_callback: Optional[ProgressCallback] = None
    ) -> None:
        """
        启动后台任务跟踪
        
        Args:
            task_id: 任务ID
            progress_callback: 进度回调函数
        """
        if task_id in self._tracking_tasks:
            self.logger.warning(f"任务已在跟踪中: {task_id}")
            return
        
        if progress_callback:
            self._task_callbacks[task_id] = progress_callback
        
        # 创建后台任务
        task = asyncio.create_task(self._background_track(task_id))
        self._tracking_tasks[task_id] = task
        
        self.logger.info(f"启动后台跟踪: {task_id}")
    
    async def _background_track(self, task_id: str) -> None:
        """后台跟踪任务"""
        try:
            callback = self._task_callbacks.get(task_id)
            await self.track_task(task_id, callback)
        except Exception as e:
            self.logger.error(f"后台跟踪任务失败: {e}", task_id=task_id)
        finally:
            # 清理资源
            self._tracking_tasks.pop(task_id, None)
            self._task_callbacks.pop(task_id, None)
    
    async def stop_tracking(self, task_id: str) -> None:
        """
        停止跟踪指定任务
        
        Args:
            task_id: 任务ID
        """
        if task_id in self._tracking_tasks:
            task = self._tracking_tasks[task_id]
            task.cancel()
            
            try:
                await task
            except asyncio.CancelledError:
                pass
            
            # 清理资源
            self._tracking_tasks.pop(task_id, None)
            self._task_callbacks.pop(task_id, None)
            
            self.logger.info(f"停止跟踪任务: {task_id}")
    
    async def stop_all_tracking(self) -> None:
        """停止所有跟踪任务"""
        task_ids = list(self._tracking_tasks.keys())
        
        for task_id in task_ids:
            await self.stop_tracking(task_id)
        
        self.logger.info("已停止所有跟踪任务")
    
    def get_tracking_status(self) -> Dict[str, Dict[str, Any]]:
        """
        获取当前跟踪状态
        
        Returns:
            Dict[str, Dict[str, Any]]: 跟踪状态信息
        """
        status = {}
        
        for task_id, task in self._tracking_tasks.items():
            status[task_id] = {
                "is_running": not task.done(),
                "is_cancelled": task.cancelled(),
                "has_callback": task_id in self._task_callbacks
            }
            
            if task.done() and not task.cancelled():
                try:
                    task.result()
                    status[task_id]["completed"] = True
                except Exception as e:
                    status[task_id]["error"] = str(e)
        
        return status
    
    async def wait_for_completion(
        self, 
        task_ids: list[str],
        timeout: Optional[int] = None
    ) -> Dict[str, KlingVideoResponse]:
        """
        等待多个任务完成
        
        Args:
            task_ids: 任务ID列表
            timeout: 超时时间（秒）
            
        Returns:
            Dict[str, KlingVideoResponse]: 任务结果映射
        """
        timeout = timeout or self.max_wait_time
        
        self.logger.info(f"等待 {len(task_ids)} 个任务完成")
        
        # 创建跟踪任务
        tracking_tasks = {}
        for task_id in task_ids:
            tracking_tasks[task_id] = asyncio.create_task(
                self.track_task(task_id)
            )
        
        results = {}
        
        try:
            # 等待所有任务完成
            done, pending = await asyncio.wait(
                tracking_tasks.values(),
                timeout=timeout,
                return_when=asyncio.ALL_COMPLETED
            )
            
            # 收集结果
            for task_id, task in tracking_tasks.items():
                if task in done:
                    try:
                        results[task_id] = await task
                    except Exception as e:
                        self.logger.error(f"任务 {task_id} 执行失败: {e}")
                        # 创建失败响应
                        results[task_id] = KlingVideoResponse(
                            task_id=task_id,
                            status=KlingTaskStatus.FAILED
                        )
                else:
                    self.logger.warning(f"任务 {task_id} 未完成")
            
            # 取消未完成的任务
            for task in pending:
                task.cancel()
                
        except asyncio.TimeoutError:
            self.logger.error(f"等待任务完成超时")
            # 取消所有任务
            for task in tracking_tasks.values():
                task.cancel()
            raise
        
        self.logger.info(f"完成 {len(results)} 个任务的等待")
        
        return results

class ProgressReporter:
    """进度报告器 - 提供标准的进度回调实现"""
    
    def __init__(self, logger_name: str = "kling_progress"):
        self.logger = get_logger(logger_name)
    
    async def log_progress(self, response: KlingVideoResponse) -> None:
        """记录进度日志"""
        task_info = response.task_info
        
        log_data = {
            "task_id": response.task_id,
            "status": response.status.value
        }
        
        if task_info:
            log_data.update({
                "progress": task_info.progress,
                "estimated_time": task_info.estimated_time
            })
        
        if response.status == KlingTaskStatus.COMPLETED:
            self.logger.info("任务完成", **log_data)
        elif response.status == KlingTaskStatus.FAILED:
            log_data["error"] = task_info.error_message if task_info else "未知错误"
            self.logger.error("任务失败", **log_data)
        else:
            self.logger.info("任务进度", **log_data)
    
    async def print_progress(self, response: KlingVideoResponse) -> None:
        """打印进度信息到控制台"""
        task_info = response.task_info
        
        if response.status == KlingTaskStatus.PROCESSING and task_info:
            progress = task_info.progress
            estimated_time = task_info.estimated_time
            
            print(f"任务 {response.task_id}: {progress}% 完成", end="")
            if estimated_time:
                print(f", 预计还需 {estimated_time}s")
            else:
                print()
                
        elif response.status == KlingTaskStatus.COMPLETED:
            print(f"任务 {response.task_id}: 已完成")
            
        elif response.status == KlingTaskStatus.FAILED:
            error_msg = task_info.error_message if task_info else "未知错误"
            print(f"任务 {response.task_id}: 失败 - {error_msg}")
    
    async def combined_callback(self, response: KlingVideoResponse) -> None:
        """组合回调 - 同时记录日志和打印进度"""
        await asyncio.gather(
            self.log_progress(response),
            self.print_progress(response),
            return_exceptions=True
        )