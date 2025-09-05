"""
Kling 视频处理工具

提供视频格式转换、处理和优化功能。
"""

import asyncio
import base64
import os
import tempfile
from typing import Dict, Any, Optional, Union, Tuple
from pathlib import Path
import mimetypes
import hashlib

from PIL import Image
import aiohttp

from ...logger import get_logger
from ...file_manager import FileManager
from ...exceptions import ValidationError, FileOperationError

class VideoFormatConverter:
    """视频格式转换器"""
    
    def __init__(self):
        self.logger = get_logger("video_format_converter")
        
        # 支持的视频格式
        self.supported_formats = {
            "mp4": "video/mp4",
            "mov": "video/quicktime", 
            "avi": "video/x-msvideo",
            "webm": "video/webm",
            "mkv": "video/x-matroska"
        }
        
        # 支持的图像格式（用于image-to-video）
        self.supported_image_formats = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
            "bmp": "image/bmp"
        }
    
    def get_video_info(self, file_path: str) -> Dict[str, Any]:
        """
        获取视频文件信息
        
        Args:
            file_path: 视频文件路径
            
        Returns:
            Dict[str, Any]: 视频信息
        """
        if not os.path.exists(file_path):
            raise FileOperationError(f"视频文件不存在: {file_path}")
        
        file_size = os.path.getsize(file_path)
        file_ext = Path(file_path).suffix.lower().lstrip('.')
        
        info = {
            "path": file_path,
            "size": file_size,
            "format": file_ext,
            "mime_type": self.supported_formats.get(file_ext, "application/octet-stream")
        }
        
        # 尝试获取更详细信息（需要安装ffmpeg等工具）
        try:
            # 这里可以集成ffprobe等工具获取详细信息
            # 暂时提供基础信息
            info.update({
                "width": None,
                "height": None,
                "duration": None,
                "fps": None,
                "bitrate": None
            })
        except Exception as e:
            self.logger.debug(f"无法获取视频详细信息: {e}")
        
        return info
    
    def validate_video_file(self, file_path: str, max_size_mb: int = 500) -> bool:
        """
        验证视频文件
        
        Args:
            file_path: 视频文件路径
            max_size_mb: 最大文件大小（MB）
            
        Returns:
            bool: 是否有效
        """
        try:
            if not os.path.exists(file_path):
                raise ValidationError(f"视频文件不存在: {file_path}")
            
            # 检查文件大小
            file_size = os.path.getsize(file_path)
            max_size_bytes = max_size_mb * 1024 * 1024
            
            if file_size > max_size_bytes:
                raise ValidationError(
                    f"视频文件过大: {file_size / 1024 / 1024:.2f}MB > {max_size_mb}MB"
                )
            
            # 检查文件格式
            file_ext = Path(file_path).suffix.lower().lstrip('.')
            if file_ext not in self.supported_formats:
                raise ValidationError(
                    f"不支持的视频格式: {file_ext}. "
                    f"支持格式: {', '.join(self.supported_formats.keys())}"
                )
            
            return True
            
        except ValidationError:
            raise
        except Exception as e:
            self.logger.error(f"验证视频文件失败: {e}")
            return False

class KlingVideoUtils:
    """Kling 视频处理工具类"""
    
    def __init__(self, file_manager: Optional[FileManager] = None):
        """
        初始化视频工具
        
        Args:
            file_manager: 文件管理器实例
        """
        self.file_manager = file_manager
        self.logger = get_logger("kling_video_utils")
        self.format_converter = VideoFormatConverter()
    
    async def encode_image_to_base64(self, image_path: str) -> str:
        """
        将图像编码为Base64格式
        
        Args:
            image_path: 图像文件路径
            
        Returns:
            str: Base64编码的图像数据
        """
        try:
            # 验证图像文件
            if not os.path.exists(image_path):
                raise FileOperationError(f"图像文件不存在: {image_path}")
            
            # 检查文件格式
            file_ext = Path(image_path).suffix.lower().lstrip('.')
            if file_ext not in self.format_converter.supported_image_formats:
                raise ValidationError(f"不支持的图像格式: {file_ext}")
            
            # 读取并编码
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            # 获取MIME类型
            mime_type = self.format_converter.supported_image_formats[file_ext]
            
            # 编码为Base64
            base64_data = base64.b64encode(image_data).decode('utf-8')
            
            # 返回完整的data URL格式
            return f"data:{mime_type};base64,{base64_data}"
            
        except Exception as e:
            self.logger.error(f"图像编码失败: {e}", image_path=image_path)
            raise
    
    async def download_image_from_url(self, image_url: str, save_path: Optional[str] = None) -> str:
        """
        从URL下载图像
        
        Args:
            image_url: 图像URL
            save_path: 保存路径（可选）
            
        Returns:
            str: 本地保存路径
        """
        try:
            # 生成保存路径
            if not save_path:
                # 根据URL生成文件名
                url_hash = hashlib.md5(image_url.encode()).hexdigest()[:8]
                
                # 尝试从URL获取文件扩展名
                file_ext = "jpg"  # 默认扩展名
                try:
                    from urllib.parse import urlparse
                    parsed_url = urlparse(image_url)
                    if parsed_url.path:
                        path_ext = Path(parsed_url.path).suffix.lower().lstrip('.')
                        if path_ext in self.format_converter.supported_image_formats:
                            file_ext = path_ext
                except Exception:
                    pass
                
                save_path = os.path.join(tempfile.gettempdir(), f"kling_image_{url_hash}.{file_ext}")
            
            # 下载图像
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status != 200:
                        raise FileOperationError(f"下载图像失败: HTTP {response.status}")
                    
                    # 检查内容类型
                    content_type = response.headers.get('content-type', '')
                    if not content_type.startswith('image/'):
                        self.logger.warning(f"可能不是图像文件: {content_type}")
                    
                    # 保存文件
                    with open(save_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
            
            self.logger.info(f"成功下载图像: {image_url} -> {save_path}")
            return save_path
            
        except Exception as e:
            self.logger.error(f"下载图像失败: {e}", image_url=image_url)
            raise
    
    async def download_video_from_url(self, video_url: str, save_path: Optional[str] = None) -> str:
        """
        从URL下载视频
        
        Args:
            video_url: 视频URL
            save_path: 保存路径（可选）
            
        Returns:
            str: 本地保存路径
        """
        try:
            # 生成保存路径
            if not save_path:
                url_hash = hashlib.md5(video_url.encode()).hexdigest()[:8]
                
                # 尝试从URL获取文件扩展名
                file_ext = "mp4"  # 默认扩展名
                try:
                    from urllib.parse import urlparse
                    parsed_url = urlparse(video_url)
                    if parsed_url.path:
                        path_ext = Path(parsed_url.path).suffix.lower().lstrip('.')
                        if path_ext in self.format_converter.supported_formats:
                            file_ext = path_ext
                except Exception:
                    pass
                
                save_path = os.path.join(tempfile.gettempdir(), f"kling_video_{url_hash}.{file_ext}")
            
            # 下载视频
            self.logger.info(f"开始下载视频: {video_url}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(video_url) as response:
                    if response.status != 200:
                        raise FileOperationError(f"下载视频失败: HTTP {response.status}")
                    
                    # 检查内容类型
                    content_type = response.headers.get('content-type', '')
                    if not content_type.startswith('video/'):
                        self.logger.warning(f"可能不是视频文件: {content_type}")
                    
                    # 获取文件大小
                    content_length = response.headers.get('content-length')
                    if content_length:
                        file_size = int(content_length)
                        self.logger.info(f"视频文件大小: {file_size / 1024 / 1024:.2f}MB")
                    
                    # 保存文件（带进度显示）
                    downloaded = 0
                    with open(save_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            # 显示进度（每1MB显示一次）
                            if content_length and downloaded % (1024 * 1024) == 0:
                                progress = (downloaded / file_size) * 100
                                self.logger.debug(f"下载进度: {progress:.1f}%")
            
            self.logger.info(f"成功下载视频: {video_url} -> {save_path}")
            return save_path
            
        except Exception as e:
            self.logger.error(f"下载视频失败: {e}", video_url=video_url)
            raise
    
    def optimize_image_for_video(
        self, 
        image_path: str,
        target_width: int = 1024,
        target_height: int = 1024,
        quality: int = 85
    ) -> str:
        """
        优化图像用于视频生成
        
        Args:
            image_path: 原始图像路径
            target_width: 目标宽度
            target_height: 目标高度
            quality: JPEG质量
            
        Returns:
            str: 优化后的图像路径
        """
        try:
            with Image.open(image_path) as img:
                # 转换为RGB模式
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 计算缩放比例
                original_width, original_height = img.size
                width_ratio = target_width / original_width
                height_ratio = target_height / original_height
                
                # 使用较小的比例保持宽高比
                scale_ratio = min(width_ratio, height_ratio)
                
                if scale_ratio < 1:
                    # 需要缩放
                    new_width = int(original_width * scale_ratio)
                    new_height = int(original_height * scale_ratio)
                    
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    
                    # 居中填充到目标大小
                    optimized_img = Image.new('RGB', (target_width, target_height), (0, 0, 0))
                    paste_x = (target_width - new_width) // 2
                    paste_y = (target_height - new_height) // 2
                    optimized_img.paste(img, (paste_x, paste_y))
                else:
                    # 不需要缩放，但可能需要裁剪
                    if original_width > target_width or original_height > target_height:
                        # 居中裁剪
                        left = (original_width - target_width) // 2
                        top = (original_height - target_height) // 2
                        right = left + target_width
                        bottom = top + target_height
                        
                        optimized_img = img.crop((left, top, right, bottom))
                    else:
                        optimized_img = img
                
                # 生成优化后的文件名
                path_obj = Path(image_path)
                # 在文件名后面（扩展名前面）添加 '_optimized'
                optimized_path = str(path_obj.with_stem(path_obj.stem + '_optimized'))
                
                # 保存优化后的图像
                optimized_img.save(optimized_path, 'JPEG', quality=quality, optimize=True)
                
                self.logger.info(
                    f"图像优化完成: {image_path} -> {optimized_path}",
                    original_size=f"{original_width}x{original_height}",
                    optimized_size=f"{target_width}x{target_height}"
                )
                
                return optimized_path
                
        except Exception as e:
            self.logger.error(f"图像优化失败: {e}", image_path=image_path)
            raise
    
    def get_aspect_ratio_dimensions(self, aspect_ratio: str) -> Tuple[int, int]:
        """
        根据宽高比获取推荐尺寸
        
        Args:
            aspect_ratio: 宽高比字符串 (如 "16:9")
            
        Returns:
            Tuple[int, int]: (宽度, 高度)
        """
        aspect_ratio_map = {
            "1:1": (1024, 1024),
            "9:16": (608, 1080),
            "16:9": (1360, 768),
            "21:9": (1792, 768),
            "3:4": (768, 1024),
            "4:3": (1024, 768)
        }
        
        return aspect_ratio_map.get(aspect_ratio, (1024, 1024))
    
    async def validate_and_prepare_inputs(
        self, 
        prompt: str,
        image_path: Optional[str] = None,
        image_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        验证和准备输入参数
        
        Args:
            prompt: 提示文本
            image_path: 图像文件路径
            image_url: 图像URL
            
        Returns:
            Dict[str, Any]: 准备好的输入数据
        """
        result = {"prompt": prompt}
        
        # 验证提示文本
        if not prompt or not prompt.strip():
            raise ValidationError("提示文本不能为空")
        
        if len(prompt.strip()) < 5:
            raise ValidationError("提示文本过短，至少需要5个字符")
        
        # 处理图像输入
        if image_path or image_url:
            if image_path and image_url:
                raise ValidationError("不能同时提供图像文件路径和URL")
            
            if image_path:
                # 本地图像文件
                if not os.path.exists(image_path):
                    raise FileOperationError(f"图像文件不存在: {image_path}")
                
                # 编码为Base64
                result["image"] = await self.encode_image_to_base64(image_path)
                
            elif image_url:
                # 远程图像URL
                # 这里可以选择下载后编码，或直接传递URL
                result["image_url"] = image_url
        
        return result