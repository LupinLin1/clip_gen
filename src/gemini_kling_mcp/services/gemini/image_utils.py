"""
图像处理工具

提供图像格式转换、编码解码、压缩优化等功能。
"""

import base64
import hashlib
import io
import os
import tempfile
from pathlib import Path
from typing import Tuple, Optional, Union, Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import ImageData
import mimetypes

try:
    from PIL import Image, ImageOps, ImageEnhance
    HAS_PIL = True
except ImportError:
    Image = None
    ImageOps = None
    ImageEnhance = None
    HAS_PIL = False

from ...logger import get_logger
from ...exceptions import ValidationError, ToolExecutionError
from .models import ImageFormat

logger = get_logger(__name__)

class ImageProcessingError(ToolExecutionError):
    """图像处理错误"""
    pass

class ImageProcessor:
    """图像处理器"""
    
    def __init__(self):
        self.logger = get_logger("image_processor")
        
        if not HAS_PIL:
            self.logger.warning("PIL/Pillow未安装，图像处理功能将受限")
            
        # 支持的格式映射
        self.format_mapping = {
            ImageFormat.PNG: "PNG",
            ImageFormat.JPEG: "JPEG", 
            ImageFormat.JPG: "JPEG",
            ImageFormat.WEBP: "WEBP",
            ImageFormat.GIF: "GIF"
        }
        
        # 质量设置
        self.quality_settings = {
            "low": 60,
            "medium": 80,
            "high": 95,
            "max": 100
        }
    
    def validate_image_format(self, format_str: str) -> ImageFormat:
        """验证并标准化图像格式
        
        Args:
            format_str: 格式字符串
            
        Returns:
            标准化的图像格式枚举
            
        Raises:
            ValidationError: 不支持的格式
        """
        format_lower = format_str.lower().lstrip('.')
        
        try:
            return ImageFormat(format_lower)
        except ValueError:
            supported = [f.value for f in ImageFormat]
            raise ValidationError(
                f"不支持的图像格式: {format_str}，支持的格式: {', '.join(supported)}"
            )
    
    def get_image_info(self, image_data: bytes) -> Dict[str, Any]:
        """获取图像信息
        
        Args:
            image_data: 图像二进制数据
            
        Returns:
            图像信息字典
        """
        try:
            if not HAS_PIL:
                # 基本信息
                return {
                    "size": len(image_data),
                    "format": "unknown",
                    "width": 0,
                    "height": 0,
                    "mode": "unknown",
                    "has_transparency": False
                }
            
            with Image.open(io.BytesIO(image_data)) as img:
                return {
                    "size": len(image_data),
                    "format": img.format or "unknown",
                    "width": img.width,
                    "height": img.height,
                    "mode": img.mode,
                    "has_transparency": img.mode in ('RGBA', 'LA') or 'transparency' in img.info
                }
                
        except Exception as e:
            self.logger.error(f"获取图像信息失败: {e}")
            return {
                "size": len(image_data),
                "format": "unknown",
                "width": 0,
                "height": 0,
                "mode": "unknown", 
                "has_transparency": False,
                "error": str(e)
            }
    
    def convert_format(self, image_data: bytes, target_format: ImageFormat, 
                      quality: Optional[int] = None) -> bytes:
        """转换图像格式
        
        Args:
            image_data: 原始图像数据
            target_format: 目标格式
            quality: 质量设置(1-100)，仅对JPEG有效
            
        Returns:
            转换后的图像数据
            
        Raises:
            ImageProcessingError: 转换失败
        """
        if not HAS_PIL:
            raise ImageProcessingError("PIL/Pillow未安装，无法进行格式转换")
        
        try:
            with Image.open(io.BytesIO(image_data)) as img:
                # 处理透明度
                if target_format in [ImageFormat.JPEG, ImageFormat.JPG] and img.mode in ('RGBA', 'LA'):
                    # JPEG不支持透明度，转换为RGB
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'LA':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1])  # 使用alpha通道作为mask
                    img = background
                elif target_format == ImageFormat.PNG and img.mode != 'RGBA':
                    img = img.convert('RGBA')
                
                # 输出设置
                output = io.BytesIO()
                pil_format = self.format_mapping[target_format]
                
                save_kwargs = {"format": pil_format}
                if target_format in [ImageFormat.JPEG, ImageFormat.JPG]:
                    save_kwargs["quality"] = quality or 95
                    save_kwargs["optimize"] = True
                elif target_format == ImageFormat.PNG:
                    save_kwargs["optimize"] = True
                elif target_format == ImageFormat.WEBP:
                    save_kwargs["quality"] = quality or 95
                    save_kwargs["optimize"] = True
                
                img.save(output, **save_kwargs)
                return output.getvalue()
                
        except Exception as e:
            self.logger.error(f"图像格式转换失败: {e}")
            raise ImageProcessingError(f"格式转换失败: {e}")
    
    def resize_image(self, image_data: bytes, width: int, height: int, 
                    maintain_aspect_ratio: bool = True) -> bytes:
        """调整图像尺寸
        
        Args:
            image_data: 图像数据
            width: 目标宽度
            height: 目标高度
            maintain_aspect_ratio: 是否保持宽高比
            
        Returns:
            调整后的图像数据
        """
        if not HAS_PIL:
            raise ImageProcessingError("PIL/Pillow未安装，无法进行尺寸调整")
        
        try:
            with Image.open(io.BytesIO(image_data)) as img:
                if maintain_aspect_ratio:
                    img.thumbnail((width, height), Image.Resampling.LANCZOS)
                else:
                    img = img.resize((width, height), Image.Resampling.LANCZOS)
                
                output = io.BytesIO()
                img.save(output, format=img.format or 'PNG')
                return output.getvalue()
                
        except Exception as e:
            self.logger.error(f"图像尺寸调整失败: {e}")
            raise ImageProcessingError(f"尺寸调整失败: {e}")
    
    def compress_image(self, image_data: bytes, quality: Union[int, str] = "medium",
                      max_size: Optional[int] = None) -> bytes:
        """压缩图像
        
        Args:
            image_data: 图像数据
            quality: 质量设置（数字1-100或预设字符串）
            max_size: 最大文件大小（字节）
            
        Returns:
            压缩后的图像数据
        """
        if not HAS_PIL:
            raise ImageProcessingError("PIL/Pillow未安装，无法进行图像压缩")
        
        try:
            # 解析质量参数
            if isinstance(quality, str):
                quality_int = self.quality_settings.get(quality, 80)
            else:
                quality_int = max(1, min(100, quality))
            
            with Image.open(io.BytesIO(image_data)) as img:
                output = io.BytesIO()
                
                # 优化设置
                save_kwargs = {
                    "format": img.format or 'JPEG',
                    "optimize": True
                }
                
                if img.format in ['JPEG', 'WEBP']:
                    save_kwargs["quality"] = quality_int
                
                img.save(output, **save_kwargs)
                compressed_data = output.getvalue()
                
                # 如果指定了最大大小且超出，进一步压缩
                if max_size and len(compressed_data) > max_size:
                    compressed_data = self._compress_to_size(img, max_size, quality_int)
                
                return compressed_data
                
        except Exception as e:
            self.logger.error(f"图像压缩失败: {e}")
            raise ImageProcessingError(f"图像压缩失败: {e}")
    
    def _compress_to_size(self, img: Image.Image, max_size: int, 
                         initial_quality: int) -> bytes:
        """压缩图像到指定大小"""
        quality = initial_quality
        
        while quality > 10:
            output = io.BytesIO()
            save_kwargs = {
                "format": img.format or 'JPEG',
                "quality": quality,
                "optimize": True
            }
            
            img.save(output, **save_kwargs)
            compressed_data = output.getvalue()
            
            if len(compressed_data) <= max_size:
                return compressed_data
            
            quality -= 10
        
        # 如果质量降到最低仍然过大，尝试缩小尺寸
        scale_factor = 0.9
        current_img = img.copy()
        
        while scale_factor > 0.5:
            new_size = (int(img.width * scale_factor), int(img.height * scale_factor))
            current_img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            output = io.BytesIO()
            current_img.save(output, format=img.format or 'JPEG', quality=20, optimize=True)
            compressed_data = output.getvalue()
            
            if len(compressed_data) <= max_size:
                return compressed_data
            
            scale_factor -= 0.1
        
        # 返回最小压缩结果
        output = io.BytesIO()
        current_img.save(output, format=img.format or 'JPEG', quality=10, optimize=True)
        return output.getvalue()

class ImageCodec:
    """图像编解码器"""
    
    def __init__(self):
        self.logger = get_logger("image_codec")
    
    def encode_to_base64(self, image_data: bytes) -> str:
        """将图像数据编码为base64
        
        Args:
            image_data: 图像二进制数据
            
        Returns:
            base64编码的字符串
        """
        try:
            return base64.b64encode(image_data).decode('utf-8')
        except Exception as e:
            self.logger.error(f"base64编码失败: {e}")
            raise ImageProcessingError(f"base64编码失败: {e}")
    
    def decode_from_base64(self, base64_str: str) -> bytes:
        """从base64解码图像数据
        
        Args:
            base64_str: base64编码的字符串
            
        Returns:
            图像二进制数据
        """
        try:
            # 清理base64字符串
            clean_str = base64_str.strip()
            if clean_str.startswith('data:'):
                # 移除data URL前缀
                clean_str = clean_str.split(',', 1)[1]
            
            return base64.b64decode(clean_str)
        except Exception as e:
            self.logger.error(f"base64解码失败: {e}")
            raise ImageProcessingError(f"base64解码失败: {e}")
    
    def create_data_url(self, image_data: bytes, format: ImageFormat) -> str:
        """创建图像的data URL
        
        Args:
            image_data: 图像数据
            format: 图像格式
            
        Returns:
            data URL字符串
        """
        mime_type = f"image/{format.value}"
        base64_str = self.encode_to_base64(image_data)
        return f"data:{mime_type};base64,{base64_str}"
    
    def calculate_checksum(self, image_data: bytes, algorithm: str = "sha256") -> str:
        """计算图像数据的校验和
        
        Args:
            image_data: 图像数据
            algorithm: 哈希算法
            
        Returns:
            校验和字符串
        """
        try:
            hash_algo = hashlib.new(algorithm)
            hash_algo.update(image_data)
            return hash_algo.hexdigest()
        except Exception as e:
            self.logger.error(f"计算校验和失败: {e}")
            return ""

class ImageIO:
    """图像输入输出处理器"""
    
    def __init__(self, temp_dir: Optional[Path] = None):
        self.logger = get_logger("image_io")
        self.temp_dir = temp_dir or Path(tempfile.gettempdir())
        self.processor = ImageProcessor()
        self.codec = ImageCodec()
    
    def load_from_file(self, file_path: Union[str, Path]) -> "ImageData":
        """从文件加载图像
        
        Args:
            file_path: 文件路径
            
        Returns:
            ImageData对象
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"图像文件不存在: {path}")
        
        try:
            with open(path, 'rb') as f:
                image_data = f.read()
            
            info = self.processor.get_image_info(image_data)
            format_str = path.suffix.lower().lstrip('.')
            
            try:
                image_format = self.processor.validate_image_format(format_str)
            except ValidationError:
                # 使用PIL检测到的格式
                if info.get("format"):
                    image_format = self.processor.validate_image_format(info["format"])
                else:
                    image_format = ImageFormat.PNG  # 默认格式
            
            checksum = self.codec.calculate_checksum(image_data)
            
            from .models import ImageData
            return ImageData(
                data=image_data,
                format=image_format,
                width=info["width"],
                height=info["height"],
                size=info["size"],
                checksum=checksum
            )
            
        except Exception as e:
            self.logger.error(f"加载图像文件失败: {e}", file_path=str(path))
            raise ImageProcessingError(f"加载图像失败: {e}")
    
    def save_to_file(self, image_data: "ImageData", file_path: Union[str, Path], 
                    overwrite: bool = False) -> Path:
        """保存图像到文件
        
        Args:
            image_data: 图像数据对象
            file_path: 目标文件路径
            overwrite: 是否覆盖已存在的文件
            
        Returns:
            保存的文件路径
        """
        path = Path(file_path)
        
        if path.exists() and not overwrite:
            raise FileExistsError(f"文件已存在: {path}")
        
        try:
            # 确保目录存在
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'wb') as f:
                f.write(image_data.data)
            
            self.logger.info("图像保存成功", file_path=str(path), size=len(image_data.data))
            return path
            
        except Exception as e:
            self.logger.error(f"保存图像文件失败: {e}", file_path=str(path))
            raise ImageProcessingError(f"保存图像失败: {e}")
    
    def create_temp_file(self, image_data: "ImageData", prefix: str = "tmp_img_") -> Path:
        """创建临时图像文件
        
        Args:
            image_data: 图像数据对象
            prefix: 文件名前缀
            
        Returns:
            临时文件路径
        """
        try:
            suffix = f".{image_data.format.value}"
            with tempfile.NamedTemporaryFile(
                suffix=suffix, prefix=prefix, dir=self.temp_dir, delete=False
            ) as temp_file:
                temp_file.write(image_data.data)
                temp_path = Path(temp_file.name)
            
            self.logger.debug("临时图像文件创建成功", file_path=str(temp_path))
            return temp_path
            
        except Exception as e:
            self.logger.error(f"创建临时图像文件失败: {e}")
            raise ImageProcessingError(f"创建临时文件失败: {e}")
    
    def load_from_base64(self, base64_str: str, format: Optional[ImageFormat] = None) -> "ImageData":
        """从base64字符串加载图像
        
        Args:
            base64_str: base64编码的图像数据
            format: 图像格式（可选，如果不提供会尝试自动检测）
            
        Returns:
            ImageData对象
        """
        try:
            image_data = self.codec.decode_from_base64(base64_str)
            info = self.processor.get_image_info(image_data)
            
            if format is None:
                # 尝试从信息中获取格式
                if info.get("format"):
                    format = self.processor.validate_image_format(info["format"])
                else:
                    format = ImageFormat.PNG  # 默认格式
            
            checksum = self.codec.calculate_checksum(image_data)
            
            from .models import ImageData
            return ImageData(
                data=image_data,
                format=format,
                width=info["width"],
                height=info["height"],
                size=info["size"],
                checksum=checksum
            )
            
        except Exception as e:
            self.logger.error(f"从base64加载图像失败: {e}")
            raise ImageProcessingError(f"从base64加载图像失败: {e}")

# 便捷函数
def create_image_processor() -> ImageProcessor:
    """创建图像处理器实例"""
    return ImageProcessor()

def create_image_codec() -> ImageCodec:
    """创建图像编解码器实例"""
    return ImageCodec()

def create_image_io(temp_dir: Optional[Path] = None) -> ImageIO:
    """创建图像IO处理器实例"""
    return ImageIO(temp_dir)