"""
Kling 服务数据模型

定义 Kling API 相关的数据结构和枚举类型。
"""

from typing import Dict, Any, Optional, List, Union
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import json

class KlingModel(Enum):
    """Kling 模型类型"""
    KLING_V1 = "kling-v1"
    KLING_V1_5 = "kling-v1-5"
    KLING_PRO = "kling-pro"

class KlingVideoMode(Enum):
    """视频生成模式"""
    STANDARD = "standard"
    PRO = "pro"
    ULTRA = "ultra"

class KlingAspectRatio(Enum):
    """视频宽高比"""
    SQUARE = "1:1"           # 1024x1024
    PORTRAIT = "9:16"        # 608x1080
    LANDSCAPE = "16:9"       # 1360x768
    CINEMA = "21:9"          # 1792x768
    VERTICAL = "3:4"         # 768x1024
    HORIZONTAL = "4:3"       # 1024x768

class KlingDuration(Enum):
    """视频时长"""
    SHORT = "5s"
    MEDIUM = "10s"
    LONG = "15s"

class KlingTaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class KlingVideoConfig:
    """Kling 视频生成配置"""
    model: KlingModel = KlingModel.KLING_V1_5
    mode: KlingVideoMode = KlingVideoMode.STANDARD
    aspect_ratio: KlingAspectRatio = KlingAspectRatio.LANDSCAPE
    duration: KlingDuration = KlingDuration.SHORT
    fps: int = 25
    negative_prompt: Optional[str] = None
    cfg_scale: float = 0.5
    seed: Optional[int] = None

@dataclass
class KlingVideoRequest:
    """Kling 视频生成请求"""
    prompt: str
    config: KlingVideoConfig = field(default_factory=KlingVideoConfig)
    
    # 图像生成视频相关
    image: Optional[str] = None  # base64 编码的图像
    image_url: Optional[str] = None
    
    # 关键帧控制
    keyframes: Optional[List[Dict[str, Any]]] = None
    
    # 运动强度 (0.0-1.0)
    motion_strength: float = 0.8
    
    # 是否循环
    loop: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为 API 请求格式"""
        request_data = {
            "prompt": self.prompt,
            "model": self.config.model.value,
            "mode": self.config.mode.value,
            "aspect_ratio": self.config.aspect_ratio.value,
            "duration": self.config.duration.value,
            "fps": self.config.fps,
            "cfg_scale": self.config.cfg_scale,
            "motion_strength": self.motion_strength,
            "loop": self.loop
        }
        
        # 添加可选参数
        if self.config.negative_prompt:
            request_data["negative_prompt"] = self.config.negative_prompt
            
        if self.config.seed is not None:
            request_data["seed"] = self.config.seed
            
        if self.image:
            request_data["image"] = self.image
            
        if self.image_url:
            request_data["image_url"] = self.image_url
            
        if self.keyframes:
            request_data["keyframes"] = self.keyframes
        
        return request_data

@dataclass
class KlingTaskInfo:
    """任务信息"""
    task_id: str
    status: KlingTaskStatus
    progress: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    estimated_time: Optional[int] = None  # 预估剩余时间（秒）
    error_message: Optional[str] = None

@dataclass 
class KlingVideoResult:
    """视频生成结果"""
    video_url: str
    thumbnail_url: Optional[str] = None
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    file_size: Optional[int] = None
    format: Optional[str] = None

@dataclass
class KlingVideoResponse:
    """Kling 视频生成响应"""
    task_id: str
    status: KlingTaskStatus
    request: Optional[KlingVideoRequest] = None
    result: Optional[KlingVideoResult] = None
    task_info: Optional[KlingTaskInfo] = None
    usage: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_api_response(cls, response_data: Dict[str, Any]) -> "KlingVideoResponse":
        """从 API 响应创建对象"""
        task_id = response_data.get("task_id", "")
        status_str = response_data.get("status", "pending")
        
        try:
            status = KlingTaskStatus(status_str)
        except ValueError:
            status = KlingTaskStatus.PENDING
        
        # 解析任务信息
        task_info = None
        if "task_info" in response_data:
            task_data = response_data["task_info"]
            task_info = KlingTaskInfo(
                task_id=task_id,
                status=status,
                progress=task_data.get("progress", 0),
                created_at=cls._parse_datetime(task_data.get("created_at")),
                updated_at=cls._parse_datetime(task_data.get("updated_at")),
                estimated_time=task_data.get("estimated_time"),
                error_message=task_data.get("error_message")
            )
        
        # 解析结果
        result = None
        if status == KlingTaskStatus.COMPLETED and "result" in response_data:
            result_data = response_data["result"]
            result = KlingVideoResult(
                video_url=result_data.get("video_url", ""),
                thumbnail_url=result_data.get("thumbnail_url"),
                duration=result_data.get("duration"),
                width=result_data.get("width"),
                height=result_data.get("height"),
                file_size=result_data.get("file_size"),
                format=result_data.get("format")
            )
        
        return cls(
            task_id=task_id,
            status=status,
            result=result,
            task_info=task_info,
            usage=response_data.get("usage")
        )
    
    @staticmethod
    def _parse_datetime(datetime_str: Optional[str]) -> Optional[datetime]:
        """解析日期时间字符串"""
        if not datetime_str:
            return None
        
        try:
            # 尝试多种格式
            for fmt in [
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d %H:%M:%S",
            ]:
                try:
                    return datetime.strptime(datetime_str, fmt)
                except ValueError:
                    continue
            return None
        except Exception:
            return None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {
            "task_id": self.task_id,
            "status": self.status.value
        }
        
        if self.result:
            result["result"] = {
                "video_url": self.result.video_url,
                "thumbnail_url": self.result.thumbnail_url,
                "duration": self.result.duration,
                "width": self.result.width,
                "height": self.result.height,
                "file_size": self.result.file_size,
                "format": self.result.format
            }
        
        if self.task_info:
            result["task_info"] = {
                "progress": self.task_info.progress,
                "created_at": self.task_info.created_at.isoformat() if self.task_info.created_at else None,
                "updated_at": self.task_info.updated_at.isoformat() if self.task_info.updated_at else None,
                "estimated_time": self.task_info.estimated_time,
                "error_message": self.task_info.error_message
            }
        
        if self.usage:
            result["usage"] = self.usage
        
        return result

# 错误类型
class KlingError(Exception):
    """Kling API 基础错误"""
    def __init__(self, message: str, error_code: Optional[str] = None, **kwargs):
        super().__init__(message)
        self.error_code = error_code
        self.details = kwargs

class KlingValidationError(KlingError):
    """参数验证错误"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, **kwargs)
        # 支持额外的参数如status_code, response_data等
        for key, value in kwargs.items():
            setattr(self, key, value)

class KlingTaskError(KlingError):
    """任务处理错误"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, **kwargs)
        # 支持额外的参数如status_code, response_data等
        for key, value in kwargs.items():
            setattr(self, key, value)

class KlingQuotaError(KlingError):
    """配额限制错误"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, **kwargs)
        # 支持额外的参数如status_code, response_data等
        for key, value in kwargs.items():
            setattr(self, key, value)