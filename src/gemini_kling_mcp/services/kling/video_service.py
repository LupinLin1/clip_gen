"""
Kling 视频生成服务

提供完整的 Kling 视频生成功能，包括文本生成视频、图像生成视频等。
"""

import asyncio
from typing import Dict, Any, Optional, List, Union
from datetime import datetime

from ...logger import get_logger
from ...exceptions import ValidationError, ServiceError
from ...file_manager import FileManager
from .client import KlingClient, KlingHTTPError
from .models import (
    KlingVideoRequest,
    KlingVideoResponse, 
    KlingVideoConfig,
    KlingModel,
    KlingVideoMode,
    KlingAspectRatio,
    KlingDuration,
    KlingTaskStatus,
    KlingError,
    KlingValidationError
)
from .progress_tracker import KlingProgressTracker, ProgressCallback
from .video_utils import KlingVideoUtils

class KlingVideoService:
    """Kling 视频生成服务"""
    
    def __init__(
        self, 
        api_key: str,
        base_url: str = "https://api.minimax.chat",
        file_manager: Optional[FileManager] = None
    ):
        """
        初始化 Kling 视频服务
        
        Args:
            api_key: Kling API 密钥
            base_url: API 基础 URL
            file_manager: 文件管理器
        """
        self.api_key = api_key
        self.base_url = base_url
        self.file_manager = file_manager
        self.logger = get_logger("kling_video_service")
        
        # 初始化组件
        self.client = KlingClient(api_key, base_url)
        self.progress_tracker = KlingProgressTracker(self.client)
        self.video_utils = KlingVideoUtils(file_manager)
        
        # 服务状态
        self._is_initialized = True
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        await self.close()
    
    async def close(self) -> None:
        """关闭服务"""
        try:
            await self.progress_tracker.stop_all_tracking()
            await self.client.close()
            self.logger.info("Kling 视频服务已关闭")
        except Exception as e:
            self.logger.error(f"关闭服务时发生错误: {e}")
    
    def _validate_config(self, config: KlingVideoConfig) -> None:
        """验证配置参数"""
        if not isinstance(config.model, KlingModel):
            raise KlingValidationError(f"不支持的模型: {config.model}")
        
        if not isinstance(config.mode, KlingVideoMode):
            raise KlingValidationError(f"不支持的生成模式: {config.mode}")
        
        if not isinstance(config.aspect_ratio, KlingAspectRatio):
            raise KlingValidationError(f"不支持的宽高比: {config.aspect_ratio}")
        
        if not isinstance(config.duration, KlingDuration):
            raise KlingValidationError(f"不支持的时长: {config.duration}")
        
        if not 1 <= config.fps <= 60:
            raise KlingValidationError(f"帧率必须在1-60之间: {config.fps}")
        
        if not 0.0 <= config.cfg_scale <= 1.0:
            raise KlingValidationError(f"CFG scale必须在0.0-1.0之间: {config.cfg_scale}")
    
    async def text_to_video(
        self,
        prompt: str,
        config: Optional[KlingVideoConfig] = None,
        motion_strength: float = 0.8,
        loop: bool = False,
        wait_for_completion: bool = False,
        progress_callback: Optional[ProgressCallback] = None
    ) -> KlingVideoResponse:
        """
        文本生成视频
        
        Args:
            prompt: 提示文本
            config: 视频生成配置
            motion_strength: 运动强度 (0.0-1.0)
            loop: 是否循环
            wait_for_completion: 是否等待任务完成
            progress_callback: 进度回调函数
            
        Returns:
            KlingVideoResponse: 视频生成响应
        """
        try:
            # 使用默认配置
            if config is None:
                config = KlingVideoConfig()
            
            # 验证参数
            self._validate_config(config)
            
            if not prompt or not prompt.strip():
                raise KlingValidationError("提示文本不能为空")
            
            if not 0.0 <= motion_strength <= 1.0:
                raise KlingValidationError(f"运动强度必须在0.0-1.0之间: {motion_strength}")
            
            # 创建请求
            request = KlingVideoRequest(
                prompt=prompt.strip(),
                config=config,
                motion_strength=motion_strength,
                loop=loop
            )
            
            self.logger.info(
                "开始文本生成视频",
                prompt=prompt[:100] + "..." if len(prompt) > 100 else prompt,
                model=config.model.value,
                mode=config.mode.value,
                duration=config.duration.value,
                aspect_ratio=config.aspect_ratio.value
            )
            
            # 发送请求
            response = await self.client.text_to_video(request)
            
            if wait_for_completion:
                # 等待任务完成
                response = await self.progress_tracker.track_task(
                    response.task_id, 
                    progress_callback
                )
            elif progress_callback:
                # 启动后台跟踪
                await self.progress_tracker.start_background_tracking(
                    response.task_id,
                    progress_callback
                )
            
            self.logger.info(f"文本生成视频请求已提交: {response.task_id}")
            return response
            
        except KlingError:
            raise
        except Exception as e:
            self.logger.error(f"文本生成视频失败: {e}")
            raise ServiceError(f"文本生成视频失败: {e}")
    
    async def image_to_video(
        self,
        prompt: str,
        image_path: Optional[str] = None,
        image_url: Optional[str] = None,
        config: Optional[KlingVideoConfig] = None,
        motion_strength: float = 0.8,
        loop: bool = False,
        wait_for_completion: bool = False,
        progress_callback: Optional[ProgressCallback] = None
    ) -> KlingVideoResponse:
        """
        图像生成视频
        
        Args:
            prompt: 提示文本
            image_path: 图像文件路径
            image_url: 图像URL
            config: 视频生成配置
            motion_strength: 运动强度 (0.0-1.0)
            loop: 是否循环
            wait_for_completion: 是否等待任务完成
            progress_callback: 进度回调函数
            
        Returns:
            KlingVideoResponse: 视频生成响应
        """
        try:
            # 验证参数
            if not image_path and not image_url:
                raise KlingValidationError("必须提供图像文件路径或图像URL")
            
            if image_path and image_url:
                raise KlingValidationError("不能同时提供图像文件路径和URL")
            
            # 使用默认配置
            if config is None:
                config = KlingVideoConfig()
            
            # 验证配置
            self._validate_config(config)
            
            if not prompt or not prompt.strip():
                raise KlingValidationError("提示文本不能为空")
            
            if not 0.0 <= motion_strength <= 1.0:
                raise KlingValidationError(f"运动强度必须在0.0-1.0之间: {motion_strength}")
            
            # 准备输入数据
            input_data = await self.video_utils.validate_and_prepare_inputs(
                prompt.strip(), image_path, image_url
            )
            
            # 创建请求
            request = KlingVideoRequest(
                prompt=input_data["prompt"],
                config=config,
                image=input_data.get("image"),
                image_url=input_data.get("image_url"),
                motion_strength=motion_strength,
                loop=loop
            )
            
            self.logger.info(
                "开始图像生成视频",
                prompt=prompt[:100] + "..." if len(prompt) > 100 else prompt,
                has_image_path=bool(image_path),
                has_image_url=bool(image_url),
                model=config.model.value,
                mode=config.mode.value
            )
            
            # 发送请求
            response = await self.client.image_to_video(request)
            
            if wait_for_completion:
                # 等待任务完成
                response = await self.progress_tracker.track_task(
                    response.task_id, 
                    progress_callback
                )
            elif progress_callback:
                # 启动后台跟踪
                await self.progress_tracker.start_background_tracking(
                    response.task_id,
                    progress_callback
                )
            
            self.logger.info(f"图像生成视频请求已提交: {response.task_id}")
            return response
            
        except KlingError:
            raise
        except Exception as e:
            self.logger.error(f"图像生成视频失败: {e}")
            raise ServiceError(f"图像生成视频失败: {e}")
    
    async def keyframe_video_generation(
        self,
        prompt: str,
        keyframes: List[Dict[str, Any]],
        config: Optional[KlingVideoConfig] = None,
        motion_strength: float = 0.8,
        wait_for_completion: bool = False,
        progress_callback: Optional[ProgressCallback] = None
    ) -> KlingVideoResponse:
        """
        关键帧控制视频生成
        
        Args:
            prompt: 提示文本
            keyframes: 关键帧列表
            config: 视频生成配置
            motion_strength: 运动强度
            wait_for_completion: 是否等待完成
            progress_callback: 进度回调
            
        Returns:
            KlingVideoResponse: 视频生成响应
        """
        try:
            # 验证参数
            if not keyframes or len(keyframes) == 0:
                raise KlingValidationError("关键帧列表不能为空")
            
            # 使用默认配置
            if config is None:
                config = KlingVideoConfig()
            
            # 验证配置
            self._validate_config(config)
            
            # 验证关键帧格式
            for i, keyframe in enumerate(keyframes):
                if not isinstance(keyframe, dict):
                    raise KlingValidationError(f"关键帧 {i} 必须是字典格式")
                
                if "time" not in keyframe:
                    raise KlingValidationError(f"关键帧 {i} 缺少时间信息")
                
                if "image" not in keyframe and "image_url" not in keyframe:
                    raise KlingValidationError(f"关键帧 {i} 缺少图像信息")
            
            # 创建请求
            request = KlingVideoRequest(
                prompt=prompt.strip(),
                config=config,
                keyframes=keyframes,
                motion_strength=motion_strength,
                loop=False  # 关键帧控制通常不循环
            )
            
            self.logger.info(
                "开始关键帧控制视频生成",
                prompt=prompt[:100] + "..." if len(prompt) > 100 else prompt,
                keyframe_count=len(keyframes),
                model=config.model.value
            )
            
            # 发送请求（使用image_to_video端点，因为包含图像数据）
            response = await self.client.image_to_video(request)
            
            if wait_for_completion:
                response = await self.progress_tracker.track_task(
                    response.task_id, 
                    progress_callback
                )
            elif progress_callback:
                await self.progress_tracker.start_background_tracking(
                    response.task_id,
                    progress_callback
                )
            
            self.logger.info(f"关键帧控制视频生成请求已提交: {response.task_id}")
            return response
            
        except KlingError:
            raise
        except Exception as e:
            self.logger.error(f"关键帧控制视频生成失败: {e}")
            raise ServiceError(f"关键帧控制视频生成失败: {e}")
    
    async def get_task_status(self, task_id: str) -> KlingVideoResponse:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            KlingVideoResponse: 任务状态
        """
        try:
            response = await self.client.get_task_status(task_id)
            
            self.logger.debug(
                f"获取任务状态",
                task_id=task_id,
                status=response.status.value,
                progress=response.task_info.progress if response.task_info else None
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"获取任务状态失败: {e}", task_id=task_id)
            raise ServiceError(f"获取任务状态失败: {e}")
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功取消
        """
        try:
            success = await self.client.cancel_task(task_id)
            
            if success:
                # 停止本地跟踪
                await self.progress_tracker.stop_tracking(task_id)
                self.logger.info(f"成功取消任务: {task_id}")
            else:
                self.logger.warning(f"取消任务失败或任务不存在: {task_id}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"取消任务失败: {e}", task_id=task_id)
            return False
    
    async def list_tasks(
        self, 
        limit: int = 20, 
        status: Optional[KlingTaskStatus] = None
    ) -> List[KlingVideoResponse]:
        """
        获取任务列表
        
        Args:
            limit: 返回数量限制
            status: 过滤状态
            
        Returns:
            List[KlingVideoResponse]: 任务列表
        """
        try:
            tasks = await self.client.list_tasks(limit, status)
            
            self.logger.info(
                f"获取任务列表",
                task_count=len(tasks),
                limit=limit,
                status=status.value if status else None
            )
            
            return tasks
            
        except Exception as e:
            self.logger.error(f"获取任务列表失败: {e}")
            raise ServiceError(f"获取任务列表失败: {e}")
    
    async def wait_for_tasks(
        self,
        task_ids: List[str],
        timeout: Optional[int] = None,
        progress_callback: Optional[ProgressCallback] = None
    ) -> Dict[str, KlingVideoResponse]:
        """
        等待多个任务完成
        
        Args:
            task_ids: 任务ID列表
            timeout: 超时时间
            progress_callback: 进度回调
            
        Returns:
            Dict[str, KlingVideoResponse]: 任务结果映射
        """
        try:
            self.logger.info(f"开始等待 {len(task_ids)} 个任务完成")
            
            results = await self.progress_tracker.wait_for_completion(
                task_ids, timeout
            )
            
            # 统计结果
            completed = sum(1 for r in results.values() if r.status == KlingTaskStatus.COMPLETED)
            failed = sum(1 for r in results.values() if r.status == KlingTaskStatus.FAILED)
            
            self.logger.info(
                f"任务批处理完成",
                total=len(task_ids),
                completed=completed,
                failed=failed
            )
            
            return results
            
        except Exception as e:
            self.logger.error(f"等待任务完成失败: {e}")
            raise ServiceError(f"等待任务完成失败: {e}")
    
    async def download_video(self, video_url: str, save_path: Optional[str] = None) -> str:
        """
        下载生成的视频
        
        Args:
            video_url: 视频URL
            save_path: 保存路径
            
        Returns:
            str: 本地保存路径
        """
        try:
            local_path = await self.video_utils.download_video_from_url(video_url, save_path)
            
            # 如果有文件管理器，保存到管理器中
            if self.file_manager:
                managed_path = await self.file_manager.save_file(
                    local_path, 
                    content_type="video",
                    metadata={"source_url": video_url}
                )
                self.logger.info(f"视频已保存到文件管理器: {managed_path}")
                return managed_path
            
            return local_path
            
        except Exception as e:
            self.logger.error(f"下载视频失败: {e}", video_url=video_url)
            raise ServiceError(f"下载视频失败: {e}")
    
    def get_service_info(self) -> Dict[str, Any]:
        """
        获取服务信息
        
        Returns:
            Dict[str, Any]: 服务信息
        """
        tracking_status = self.progress_tracker.get_tracking_status()
        
        return {
            "service_name": "Kling Video Service",
            "version": "0.1.0",
            "api_base_url": self.base_url,
            "is_initialized": self._is_initialized,
            "active_tasks": len(tracking_status),
            "tracking_tasks": list(tracking_status.keys()),
            "supported_models": [model.value for model in KlingModel],
            "supported_modes": [mode.value for mode in KlingVideoMode],
            "supported_aspect_ratios": [ratio.value for ratio in KlingAspectRatio],
            "supported_durations": [duration.value for duration in KlingDuration]
        }