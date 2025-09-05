"""
Gemini 图像处理 MCP 工具

提供图像生成、编辑、分析功能的 MCP 工具实现。
"""

from typing import Dict, Any, List, Optional, Union
import asyncio

from ..config import get_config
from ..logger import get_logger
from ..exceptions import ToolExecutionError, ValidationError
from ..file_manager.core import FileManager
from ..services.gemini.image_service import GeminiImageService
from ..services.gemini.models import (
    ImageModel, ImageFormat, ImageResolution, ImageEditMode, GeminiModel
)
from .registry import tool

logger = get_logger(__name__)

@tool(
    name="gemini_generate_image",
    description="使用Gemini AI生成图像",
    parameters={
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "图像生成提示词（必需）"
            },
            "model": {
                "type": "string",
                "description": "使用的图像模型",
                "enum": [model.value for model in ImageModel],
                "default": ImageModel.get_default().value
            },
            "num_images": {
                "type": "integer",
                "description": "生成图像数量",
                "minimum": 1,
                "maximum": 8,
                "default": 1
            },
            "resolution": {
                "type": "string",
                "description": "图像分辨率",
                "enum": [res.value for res in ImageResolution],
                "default": ImageResolution.RESOLUTION_1024x1024.value
            },
            "style": {
                "type": "string",
                "description": "艺术风格（可选）"
            },
            "negative_prompt": {
                "type": "string",
                "description": "负面提示词（不希望出现的内容）"
            },
            "seed": {
                "type": "integer",
                "description": "随机种子（用于生成一致的结果）",
                "minimum": 0,
                "maximum": 2147483647
            },
            "output_format": {
                "type": "string", 
                "description": "输出图像格式",
                "enum": [fmt.value for fmt in ImageFormat],
                "default": ImageFormat.PNG.value
            },
            "quality": {
                "type": "integer",
                "description": "图像质量（1-100）",
                "minimum": 1,
                "maximum": 100,
                "default": 100
            },
            "save_to_file": {
                "type": "boolean",
                "description": "是否保存生成的图像到文件",
                "default": True
            },
            "filename_prefix": {
                "type": "string",
                "description": "文件名前缀",
                "default": "generated_image"
            }
        },
        "required": ["prompt"]
    }
)
async def generate_image(arguments: Dict[str, Any]) -> str:
    """生成图像"""
    try:
        # 验证参数
        prompt = arguments.get("prompt")
        if not prompt or not isinstance(prompt, str):
            raise ValidationError("prompt参数是必需的且必须是字符串")
        
        # 解析参数
        model_str = arguments.get("model", ImageModel.get_default().value)
        try:
            model = ImageModel(model_str)
        except ValueError:
            raise ValidationError(f"不支持的图像模型: {model_str}")
        
        num_images = arguments.get("num_images", 1)
        if not isinstance(num_images, int) or num_images < 1 or num_images > 8:
            raise ValidationError("num_images必须是1-8之间的整数")
        
        resolution_str = arguments.get("resolution", ImageResolution.RESOLUTION_1024x1024.value)
        try:
            resolution = ImageResolution(resolution_str)
        except ValueError:
            raise ValidationError(f"不支持的分辨率: {resolution_str}")
        
        output_format_str = arguments.get("output_format", ImageFormat.PNG.value)
        try:
            output_format = ImageFormat(output_format_str)
        except ValueError:
            raise ValidationError(f"不支持的输出格式: {output_format_str}")
        
        quality = arguments.get("quality", 100)
        if not isinstance(quality, int) or quality < 1 or quality > 100:
            raise ValidationError("quality必须是1-100之间的整数")
        
        seed = arguments.get("seed")
        if seed is not None and (not isinstance(seed, int) or seed < 0):
            raise ValidationError("seed必须是非负整数")
        
        logger.info(
            f"开始执行图像生成",
            prompt=prompt[:100],
            model=model.value,
            num_images=num_images,
            resolution=resolution.value
        )
        
        # 获取服务组件
        config = get_config()
        file_manager = FileManager()
        
        # 创建并执行图像生成服务
        async with GeminiImageService(config, file_manager) as image_service:
            response = await image_service.generate_image(
                prompt=prompt,
                model=model,
                num_images=num_images,
                resolution=resolution,
                style=arguments.get("style"),
                negative_prompt=arguments.get("negative_prompt"),
                seed=seed,
                output_format=output_format,
                quality=quality,
                save_to_file=arguments.get("save_to_file", True),
                filename_prefix=arguments.get("filename_prefix", "generated_image")
            )
        
        # 构建结果
        result_text = f"成功生成 {len(response.images)} 张图像\n"
        result_text += f"模型: {response.model}\n"
        result_text += f"分辨率: {response.resolution}\n"
        result_text += f"提示词: {response.prompt[:200]}\n"
        
        if response.seed:
            result_text += f"随机种子: {response.seed}\n"
        
        if response.usage:
            result_text += f"令牌使用: {response.usage}\n"
        
        result_text += "\n生成的图像:\n"
        for i, image in enumerate(response.images):
            result_text += f"图像 {i+1}:\n"
            result_text += f"  格式: {image.format.value}\n"
            result_text += f"  尺寸: {image.width}x{image.height}\n"
            result_text += f"  大小: {image.size} 字节\n"
            result_text += f"  校验和: {image.checksum[:16]}...\n"
        
        logger.info(
            f"图像生成完成",
            generated_count=len(response.images),
            total_size=sum(img.size for img in response.images)
        )
        
        return result_text
        
    except ValidationError as e:
        logger.error(f"参数验证失败: {e}")
        return f"参数错误: {e}"
    except Exception as e:
        logger.error(f"图像生成失败: {e}")
        return f"图像生成失败: {e}"

@tool(
    name="gemini_edit_image",
    description="使用Gemini AI编辑图像",
    parameters={
        "type": "object",
        "properties": {
            "image_input": {
                "type": "string",
                "description": "输入图像（文件路径或base64编码的图像数据）"
            },
            "prompt": {
                "type": "string",
                "description": "编辑指令描述"
            },
            "model": {
                "type": "string",
                "description": "使用的图像模型",
                "enum": [model.value for model in ImageModel],
                "default": ImageModel.get_default().value
            },
            "edit_mode": {
                "type": "string",
                "description": "编辑模式",
                "enum": ["generate", "edit", "inpaint", "outpaint", "upscale"],
                "default": "edit"
            },
            "mask_input": {
                "type": "string",
                "description": "遮罩图像（用于inpaint模式，文件路径或base64数据）"
            },
            "strength": {
                "type": "number",
                "description": "编辑强度（0.1-1.0）",
                "minimum": 0.1,
                "maximum": 1.0,
                "default": 0.8
            },
            "num_inference_steps": {
                "type": "integer", 
                "description": "推理步数（10-100）",
                "minimum": 10,
                "maximum": 100,
                "default": 50
            },
            "seed": {
                "type": "integer",
                "description": "随机种子",
                "minimum": 0,
                "maximum": 2147483647
            },
            "output_format": {
                "type": "string",
                "description": "输出图像格式",
                "enum": [fmt.value for fmt in ImageFormat],
                "default": ImageFormat.PNG.value
            },
            "quality": {
                "type": "integer",
                "description": "图像质量（1-100）",
                "minimum": 1,
                "maximum": 100,
                "default": 100
            },
            "save_to_file": {
                "type": "boolean",
                "description": "是否保存编辑后的图像到文件",
                "default": True
            },
            "filename_prefix": {
                "type": "string",
                "description": "文件名前缀",
                "default": "edited_image"
            }
        },
        "required": ["image_input", "prompt"]
    }
)
async def edit_image(arguments: Dict[str, Any]) -> str:
    """编辑图像"""
    try:
        # 验证参数
        image_input = arguments.get("image_input")
        if not image_input:
            raise ValidationError("image_input参数是必需的")
        
        prompt = arguments.get("prompt")
        if not prompt or not isinstance(prompt, str):
            raise ValidationError("prompt参数是必需的且必须是字符串")
        
        # 解析参数
        model_str = arguments.get("model", ImageModel.get_default().value)
        try:
            model = ImageModel(model_str)
        except ValueError:
            raise ValidationError(f"不支持的图像模型: {model_str}")
        
        edit_mode_str = arguments.get("edit_mode", "edit")
        try:
            edit_mode = ImageEditMode(edit_mode_str)
        except ValueError:
            raise ValidationError(f"不支持的编辑模式: {edit_mode_str}")
        
        strength = arguments.get("strength", 0.8)
        if not isinstance(strength, (int, float)) or strength < 0.1 or strength > 1.0:
            raise ValidationError("strength必须是0.1-1.0之间的数值")
        
        output_format_str = arguments.get("output_format", ImageFormat.PNG.value)
        try:
            output_format = ImageFormat(output_format_str)
        except ValueError:
            raise ValidationError(f"不支持的输出格式: {output_format_str}")
        
        logger.info(
            f"开始执行图像编辑",
            prompt=prompt[:100],
            model=model.value,
            edit_mode=edit_mode.value,
            strength=strength
        )
        
        # 获取服务组件
        config = get_config()
        file_manager = FileManager()
        
        # 创建并执行图像编辑服务
        async with GeminiImageService(config, file_manager) as image_service:
            response = await image_service.edit_image(
                image_input=image_input,
                prompt=prompt,
                model=model,
                edit_mode=edit_mode,
                mask_input=arguments.get("mask_input"),
                strength=strength,
                num_inference_steps=arguments.get("num_inference_steps", 50),
                seed=arguments.get("seed"),
                output_format=output_format,
                quality=arguments.get("quality", 100),
                save_to_file=arguments.get("save_to_file", True),
                filename_prefix=arguments.get("filename_prefix", "edited_image")
            )
        
        # 构建结果
        result_text = f"图像编辑完成\n"
        result_text += f"模型: {response.model}\n"
        result_text += f"编辑模式: {response.edit_mode}\n"
        result_text += f"编辑强度: {response.strength}\n"
        result_text += f"编辑指令: {response.prompt[:200]}\n"
        
        if response.usage:
            result_text += f"令牌使用: {response.usage}\n"
        
        result_text += f"\n编辑后图像:\n"
        result_text += f"  格式: {response.image.format.value}\n"
        result_text += f"  尺寸: {response.image.width}x{response.image.height}\n"
        result_text += f"  大小: {response.image.size} 字节\n"
        result_text += f"  校验和: {response.image.checksum[:16]}...\n"
        
        logger.info(f"图像编辑完成", output_size=response.image.size)
        
        return result_text
        
    except ValidationError as e:
        logger.error(f"参数验证失败: {e}")
        return f"参数错误: {e}"
    except Exception as e:
        logger.error(f"图像编辑失败: {e}")
        return f"图像编辑失败: {e}"

@tool(
    name="gemini_analyze_image",
    description="使用Gemini AI分析图像内容",
    parameters={
        "type": "object",
        "properties": {
            "image_input": {
                "type": "string",
                "description": "输入图像（文件路径或base64编码的图像数据）"
            },
            "model": {
                "type": "string",
                "description": "使用的分析模型",
                "enum": ["gemini-1.5-pro-002", "gemini-1.5-flash-002"],
                "default": "gemini-1.5-flash-002"
            },
            "analysis_type": {
                "type": "string",
                "description": "分析类型",
                "enum": ["general", "detailed", "objects", "text", "faces", "colors", "style"],
                "default": "general"
            },
            "prompt": {
                "type": "string",
                "description": "自定义分析提示（可选）"
            },
            "language": {
                "type": "string",
                "description": "输出语言",
                "enum": ["zh", "en", "auto"],
                "default": "zh"
            },
            "max_tokens": {
                "type": "integer",
                "description": "最大令牌数",
                "minimum": 100,
                "maximum": 8192,
                "default": 1000
            },
            "temperature": {
                "type": "number",
                "description": "生成温度",
                "minimum": 0.0,
                "maximum": 2.0,
                "default": 0.3
            }
        },
        "required": ["image_input"]
    }
)
async def analyze_image(arguments: Dict[str, Any]) -> str:
    """分析图像"""
    try:
        # 验证参数
        image_input = arguments.get("image_input")
        if not image_input:
            raise ValidationError("image_input参数是必需的")
        
        # 解析参数
        model_str = arguments.get("model", "gemini-1.5-flash-002")
        try:
            model = GeminiModel(model_str)
        except ValueError:
            raise ValidationError(f"不支持的分析模型: {model_str}")
        
        analysis_type = arguments.get("analysis_type", "general")
        language = arguments.get("language", "zh")
        max_tokens = arguments.get("max_tokens", 1000)
        temperature = arguments.get("temperature", 0.3)
        
        if not isinstance(max_tokens, int) or max_tokens < 100 or max_tokens > 8192:
            raise ValidationError("max_tokens必须是100-8192之间的整数")
        
        if not isinstance(temperature, (int, float)) or temperature < 0.0 or temperature > 2.0:
            raise ValidationError("temperature必须是0.0-2.0之间的数值")
        
        logger.info(
            f"开始执行图像分析",
            analysis_type=analysis_type,
            model=model.value,
            language=language
        )
        
        # 获取服务组件
        config = get_config()
        file_manager = FileManager()
        
        # 创建并执行图像分析服务
        async with GeminiImageService(config, file_manager) as image_service:
            response = await image_service.analyze_image(
                image_input=image_input,
                model=model,
                analysis_type=analysis_type,
                prompt=arguments.get("prompt"),
                language=language,
                max_tokens=max_tokens,
                temperature=temperature
            )
        
        # 构建结果
        result_text = f"图像分析完成\n"
        result_text += f"模型: {response.model}\n"
        result_text += f"分析类型: {response.analysis_type}\n"
        
        if response.confidence:
            result_text += f"置信度: {response.confidence:.2f}\n"
        
        if response.usage:
            result_text += f"令牌使用: {response.usage}\n"
        
        result_text += f"\n分析结果:\n{response.analysis}\n"
        
        # 添加额外分析信息
        if response.objects:
            result_text += f"\n检测到的对象: {len(response.objects)} 个\n"
        
        if response.text:
            result_text += f"\n图像中的文本:\n{response.text}\n"
        
        if response.faces:
            result_text += f"\n检测到的人脸: {len(response.faces)} 个\n"
        
        if response.colors:
            result_text += f"\n主要颜色: {', '.join(response.colors)}\n"
        
        if response.tags:
            result_text += f"\n图像标签: {', '.join(response.tags)}\n"
        
        logger.info(
            f"图像分析完成",
            analysis_length=len(response.analysis),
            analysis_type=analysis_type
        )
        
        return result_text
        
    except ValidationError as e:
        logger.error(f"参数验证失败: {e}")
        return f"参数错误: {e}"
    except Exception as e:
        logger.error(f"图像分析失败: {e}")
        return f"图像分析失败: {e}"