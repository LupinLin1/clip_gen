"""
Kling 视频生成 MCP 工具

提供 Kling AI 视频生成功能的 MCP 工具接口。
"""

import asyncio
from typing import Dict, Any, Optional, List, Union

from mcp.types import Tool

from ..logger import get_logger
from ..config import Config
from ..exceptions import ConfigurationError, ValidationError, ServiceError
from ..services.kling import (
    KlingVideoService,
    KlingVideoConfig,
    KlingModel,
    KlingVideoMode,
    KlingAspectRatio,
    KlingDuration,
    KlingTaskStatus
)

class KlingVideoTools:
    """Kling 视频生成工具集"""
    
    def __init__(self, config: Config):
        """
        初始化 Kling 视频工具
        
        Args:
            config: 应用配置
        """
        self.config = config
        self.logger = get_logger("kling_video_tools")
        self.service: Optional[KlingVideoService] = None
        
        # 检查配置
        if not hasattr(config, 'kling') or not config.kling:
            raise ConfigurationError("Kling 配置未找到")
        
        if not config.kling.api_key:
            raise ConfigurationError("Kling API 密钥未配置")
    
    async def _get_service(self) -> KlingVideoService:
        """获取或创建 Kling 服务实例"""
        if self.service is None:
            self.service = KlingVideoService(
                api_key=self.config.kling.api_key,
                base_url=getattr(self.config.kling, 'base_url', "https://api.minimax.chat"),
                file_manager=getattr(self.config, 'file_manager', None)
            )
            await self.service.__aenter__()
        
        return self.service
    
    async def close(self) -> None:
        """关闭服务"""
        if self.service:
            await self.service.close()
            self.service = None
    
    def get_tools(self) -> List[Tool]:
        """获取所有 MCP 工具"""
        return [
            Tool(
                name="kling_text_to_video",
                description="使用 Kling AI 从文本提示生成视频",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "视频生成提示文本"
                        },
                        "model": {
                            "type": "string",
                            "enum": ["kling-v1", "kling-v1-5", "kling-pro"],
                            "description": "使用的 Kling 模型",
                            "default": "kling-v1-5"
                        },
                        "mode": {
                            "type": "string", 
                            "enum": ["standard", "pro", "ultra"],
                            "description": "生成模式",
                            "default": "standard"
                        },
                        "aspect_ratio": {
                            "type": "string",
                            "enum": ["1:1", "9:16", "16:9", "21:9", "3:4", "4:3"],
                            "description": "视频宽高比",
                            "default": "16:9"
                        },
                        "duration": {
                            "type": "string",
                            "enum": ["5s", "10s", "15s"],
                            "description": "视频时长",
                            "default": "5s"
                        },
                        "fps": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 60,
                            "description": "帧率",
                            "default": 25
                        },
                        "motion_strength": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "description": "运动强度",
                            "default": 0.8
                        },
                        "cfg_scale": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "description": "CFG 缩放",
                            "default": 0.5
                        },
                        "negative_prompt": {
                            "type": "string",
                            "description": "负面提示（可选）"
                        },
                        "loop": {
                            "type": "boolean",
                            "description": "是否循环播放",
                            "default": False
                        },
                        "seed": {
                            "type": "integer",
                            "description": "随机种子（可选）"
                        },
                        "wait_for_completion": {
                            "type": "boolean",
                            "description": "是否等待任务完成",
                            "default": False
                        }
                    },
                    "required": ["prompt"]
                }
            ),
            Tool(
                name="kling_image_to_video",
                description="使用 Kling AI 从图像和提示生成视频",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "视频生成提示文本"
                        },
                        "image_path": {
                            "type": "string",
                            "description": "输入图像文件路径"
                        },
                        "image_url": {
                            "type": "string",
                            "description": "输入图像 URL（与 image_path 二选一）"
                        },
                        "model": {
                            "type": "string",
                            "enum": ["kling-v1", "kling-v1-5", "kling-pro"],
                            "description": "使用的 Kling 模型",
                            "default": "kling-v1-5"
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["standard", "pro", "ultra"],
                            "description": "生成模式",
                            "default": "standard"
                        },
                        "aspect_ratio": {
                            "type": "string",
                            "enum": ["1:1", "9:16", "16:9", "21:9", "3:4", "4:3"],
                            "description": "视频宽高比",
                            "default": "16:9"
                        },
                        "duration": {
                            "type": "string",
                            "enum": ["5s", "10s", "15s"],
                            "description": "视频时长",
                            "default": "5s"
                        },
                        "motion_strength": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "description": "运动强度",
                            "default": 0.8
                        },
                        "wait_for_completion": {
                            "type": "boolean",
                            "description": "是否等待任务完成",
                            "default": False
                        }
                    },
                    "required": ["prompt"]
                }
            ),
            Tool(
                name="kling_get_task_status",
                description="获取 Kling 视频生成任务状态",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "任务 ID"
                        }
                    },
                    "required": ["task_id"]
                }
            ),
            Tool(
                name="kling_list_tasks",
                description="获取 Kling 视频生成任务列表",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 100,
                            "description": "返回任务数量限制",
                            "default": 20
                        },
                        "status": {
                            "type": "string",
                            "enum": ["pending", "processing", "completed", "failed", "cancelled"],
                            "description": "过滤任务状态（可选）"
                        }
                    }
                }
            ),
            Tool(
                name="kling_cancel_task",
                description="取消 Kling 视频生成任务",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "要取消的任务 ID"
                        }
                    },
                    "required": ["task_id"]
                }
            ),
            Tool(
                name="kling_download_video",
                description="下载 Kling 生成的视频",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "video_url": {
                            "type": "string",
                            "description": "视频下载 URL"
                        },
                        "save_path": {
                            "type": "string",
                            "description": "保存路径（可选，默认为临时文件）"
                        }
                    },
                    "required": ["video_url"]
                }
            ),
            Tool(
                name="kling_wait_for_tasks",
                description="等待多个 Kling 任务完成",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "要等待的任务 ID 列表"
                        },
                        "timeout": {
                            "type": "integer",
                            "minimum": 60,
                            "maximum": 3600,
                            "description": "超时时间（秒）",
                            "default": 1800
                        }
                    },
                    "required": ["task_ids"]
                }
            ),
            Tool(
                name="kling_service_info",
                description="获取 Kling 服务信息和状态",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            )
        ]
    
    async def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """处理工具调用"""
        try:
            service = await self._get_service()
            
            if tool_name == "kling_text_to_video":
                return await self._handle_text_to_video(service, arguments)
            elif tool_name == "kling_image_to_video":
                return await self._handle_image_to_video(service, arguments)
            elif tool_name == "kling_get_task_status":
                return await self._handle_get_task_status(service, arguments)
            elif tool_name == "kling_list_tasks":
                return await self._handle_list_tasks(service, arguments)
            elif tool_name == "kling_cancel_task":
                return await self._handle_cancel_task(service, arguments)
            elif tool_name == "kling_download_video":
                return await self._handle_download_video(service, arguments)
            elif tool_name == "kling_wait_for_tasks":
                return await self._handle_wait_for_tasks(service, arguments)
            elif tool_name == "kling_service_info":
                return await self._handle_service_info(service, arguments)
            else:
                raise ValueError(f"未知工具: {tool_name}")
                
        except Exception as e:
            self.logger.error(f"工具调用失败: {e}", tool_name=tool_name)
            return {
                "success": False,
                "error": str(e),
                "tool_name": tool_name
            }
    
    async def _handle_text_to_video(self, service: KlingVideoService, args: Dict[str, Any]) -> Dict[str, Any]:
        """处理文本生成视频"""
        # 构建配置
        config = KlingVideoConfig(
            model=KlingModel(args.get("model", "kling-v1-5")),
            mode=KlingVideoMode(args.get("mode", "standard")),
            aspect_ratio=KlingAspectRatio(args.get("aspect_ratio", "16:9")),
            duration=KlingDuration(args.get("duration", "5s")),
            fps=args.get("fps", 25),
            cfg_scale=args.get("cfg_scale", 0.5),
            negative_prompt=args.get("negative_prompt"),
            seed=args.get("seed")
        )
        
        response = await service.text_to_video(
            prompt=args["prompt"],
            config=config,
            motion_strength=args.get("motion_strength", 0.8),
            loop=args.get("loop", False),
            wait_for_completion=args.get("wait_for_completion", False)
        )
        
        return {
            "success": True,
            "task_id": response.task_id,
            "status": response.status.value,
            "result": response.result.to_dict() if response.result else None,
            "task_info": {
                "progress": response.task_info.progress if response.task_info else 0,
                "estimated_time": response.task_info.estimated_time if response.task_info else None
            } if response.task_info else None
        }
    
    async def _handle_image_to_video(self, service: KlingVideoService, args: Dict[str, Any]) -> Dict[str, Any]:
        """处理图像生成视频"""
        # 构建配置
        config = KlingVideoConfig(
            model=KlingModel(args.get("model", "kling-v1-5")),
            mode=KlingVideoMode(args.get("mode", "standard")),
            aspect_ratio=KlingAspectRatio(args.get("aspect_ratio", "16:9")),
            duration=KlingDuration(args.get("duration", "5s"))
        )
        
        response = await service.image_to_video(
            prompt=args["prompt"],
            image_path=args.get("image_path"),
            image_url=args.get("image_url"),
            config=config,
            motion_strength=args.get("motion_strength", 0.8),
            wait_for_completion=args.get("wait_for_completion", False)
        )
        
        return {
            "success": True,
            "task_id": response.task_id,
            "status": response.status.value,
            "result": response.result.to_dict() if response.result else None,
            "task_info": {
                "progress": response.task_info.progress if response.task_info else 0,
                "estimated_time": response.task_info.estimated_time if response.task_info else None
            } if response.task_info else None
        }
    
    async def _handle_get_task_status(self, service: KlingVideoService, args: Dict[str, Any]) -> Dict[str, Any]:
        """处理获取任务状态"""
        response = await service.get_task_status(args["task_id"])
        
        return {
            "success": True,
            "task_id": response.task_id,
            "status": response.status.value,
            "result": response.result.to_dict() if response.result else None,
            "task_info": {
                "progress": response.task_info.progress if response.task_info else 0,
                "estimated_time": response.task_info.estimated_time if response.task_info else None,
                "error_message": response.task_info.error_message if response.task_info else None
            } if response.task_info else None
        }
    
    async def _handle_list_tasks(self, service: KlingVideoService, args: Dict[str, Any]) -> Dict[str, Any]:
        """处理获取任务列表"""
        status = None
        if args.get("status"):
            status = KlingTaskStatus(args["status"])
        
        tasks = await service.list_tasks(
            limit=args.get("limit", 20),
            status=status
        )
        
        return {
            "success": True,
            "tasks": [
                {
                    "task_id": task.task_id,
                    "status": task.status.value,
                    "result": task.result.to_dict() if task.result else None,
                    "task_info": {
                        "progress": task.task_info.progress if task.task_info else 0,
                        "created_at": task.task_info.created_at.isoformat() if task.task_info and task.task_info.created_at else None,
                        "updated_at": task.task_info.updated_at.isoformat() if task.task_info and task.task_info.updated_at else None
                    } if task.task_info else None
                }
                for task in tasks
            ]
        }
    
    async def _handle_cancel_task(self, service: KlingVideoService, args: Dict[str, Any]) -> Dict[str, Any]:
        """处理取消任务"""
        success = await service.cancel_task(args["task_id"])
        
        return {
            "success": success,
            "task_id": args["task_id"],
            "message": "任务已取消" if success else "取消任务失败或任务不存在"
        }
    
    async def _handle_download_video(self, service: KlingVideoService, args: Dict[str, Any]) -> Dict[str, Any]:
        """处理下载视频"""
        local_path = await service.download_video(
            video_url=args["video_url"],
            save_path=args.get("save_path")
        )
        
        return {
            "success": True,
            "video_url": args["video_url"],
            "local_path": local_path,
            "message": f"视频已下载到: {local_path}"
        }
    
    async def _handle_wait_for_tasks(self, service: KlingVideoService, args: Dict[str, Any]) -> Dict[str, Any]:
        """处理等待任务完成"""
        results = await service.wait_for_tasks(
            task_ids=args["task_ids"],
            timeout=args.get("timeout", 1800)
        )
        
        return {
            "success": True,
            "results": {
                task_id: {
                    "status": response.status.value,
                    "result": response.result.to_dict() if response.result else None,
                    "error": response.task_info.error_message if response.task_info else None
                }
                for task_id, response in results.items()
            },
            "summary": {
                "total": len(results),
                "completed": sum(1 for r in results.values() if r.status == KlingTaskStatus.COMPLETED),
                "failed": sum(1 for r in results.values() if r.status == KlingTaskStatus.FAILED)
            }
        }
    
    async def _handle_service_info(self, service: KlingVideoService, args: Dict[str, Any]) -> Dict[str, Any]:
        """处理获取服务信息"""
        info = service.get_service_info()
        
        return {
            "success": True,
            **info
        }