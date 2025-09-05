"""
多媒体内容创作工具

使用工作流引擎实现多媒体内容的自动化创作。
"""

import asyncio
from typing import Dict, Any, Optional, List

from ...logger import get_logger
from ...exceptions import ToolExecutionError
from ...workflow import WorkflowEngine, template_library
from ...tools.registry import tool


@tool(
    name="create_multimedia_content",
    description="Create comprehensive multimedia content for a given topic"
)
async def create_multimedia_content(
    topic: str,
    content_type: str = "article",
    target_audience: str = "general",
    language: str = "zh",
    output_mode: str = "file"
) -> Dict[str, Any]:
    """
    创建多媒体内容
    
    Args:
        topic: 内容主题
        content_type: 内容类型 (article, blog, social_post, etc.)
        target_audience: 目标受众
        language: 语言代码
        output_mode: 输出模式
    
    Returns:
        包含多媒体内容的字典
    """
    logger = get_logger("multimedia_creator")
    
    try:
        # 创建工作流引擎
        engine = WorkflowEngine()
        
        # 获取多媒体内容创作模板
        template = template_library.get_template("multimedia_content_creation")
        
        # 定制模板配置
        customized_steps = template.steps.copy()
        
        # 根据内容类型调整提示词
        content_type_prompts = {
            "article": "请为主题 '{{topic}}' 写一篇深度分析文章",
            "blog": "请为主题 '{{topic}}' 写一篇轻松有趣的博客文章",
            "social_post": "请为主题 '{{topic}}' 写一篇适合社交媒体分享的内容",
            "tutorial": "请为主题 '{{topic}}' 写一篇详细的教程文章",
            "news": "请为主题 '{{topic}}' 写一篇新闻报道"
        }
        
        # 更新文本生成步骤
        for step in customized_steps:
            if step["id"] == "generate_article":
                base_prompt = content_type_prompts.get(content_type, content_type_prompts["article"])
                step["config"]["prompt"] = f"{base_prompt}。文章应该面向{target_audience}，语言为{language}。"
                step["config"]["output_mode"] = output_mode
            elif step["type"] == "image_generation":
                step["config"]["output_mode"] = output_mode
            elif step["type"] == "video_generation":
                step["config"]["output_mode"] = output_mode
        
        # 创建工作流
        workflow_id = await engine.create_workflow(
            config=template.config,
            steps_config=customized_steps,
            initial_context={
                "topic": topic,
                "content_type": content_type,
                "target_audience": target_audience,
                "language": language
            }
        )
        
        logger.info(f"开始创建多媒体内容，工作流ID: {workflow_id}")
        
        # 启动工作流
        await engine.start_workflow(workflow_id)
        
        # 等待完成（最多20分钟）
        success = await engine.wait_for_completion(workflow_id, timeout=1200)
        
        if not success:
            raise ToolExecutionError(
                "多媒体内容创作超时",
                tool_name="create_multimedia_content",
                details={"workflow_id": workflow_id}
            )
        
        # 获取最终状态
        status = await engine.get_workflow_status(workflow_id)
        
        if status["status"] != "completed":
            logs = await engine.get_workflow_logs(workflow_id)
            raise ToolExecutionError(
                f"多媒体内容创作失败: {status.get('error', 'Unknown error')}",
                tool_name="create_multimedia_content",
                details={"workflow_id": workflow_id, "logs": logs}
            )
        
        # 加载工作流结果
        workflow_data = await engine.state_manager.load_workflow(workflow_id)
        if not workflow_data:
            raise ToolExecutionError(
                "无法加载工作流结果",
                tool_name="create_multimedia_content"
            )
        
        dag, context, _, metadata = workflow_data
        
        # 提取结果
        result = {
            "success": True,
            "workflow_id": workflow_id,
            "article": context.get("text", ""),
            "summary": context.get("analysis", ""),
            "feature_images": context.get("images", []),
            "promotional_video": context.get("video_url", ""),
            "file_paths": {
                "images": context.get("file_paths", []),
                "video": context.get("file_path", "")
            },
            "metadata": {
                "topic": topic,
                "content_type": content_type,
                "target_audience": target_audience,
                "language": language,
                "execution_time": metadata.get("execution_time", 0),
                "word_count": len(context.get("text", "")),
                "image_count": len(context.get("images", []))
            }
        }
        
        logger.info(f"多媒体内容创作完成: {workflow_id}")
        return result
        
    except ToolExecutionError:
        raise
    except Exception as e:
        logger.error(f"多媒体内容创作异常: {e}")
        raise ToolExecutionError(
            f"多媒体内容创作失败: {str(e)}",
            tool_name="create_multimedia_content",
            details={"error": str(e)}
        )


@tool(
    name="create_product_introduction",
    description="Create comprehensive product introduction materials"
)
async def create_product_introduction(
    product_description: str,
    brand_style: str = "professional",
    target_market: str = "consumer",
    language: str = "zh",
    output_mode: str = "file"
) -> Dict[str, Any]:
    """
    创建产品介绍材料
    
    Args:
        product_description: 产品描述
        brand_style: 品牌风格 (professional, casual, luxury, tech, etc.)
        target_market: 目标市场
        language: 语言代码
        output_mode: 输出模式
    
    Returns:
        包含产品介绍材料的字典
    """
    logger = get_logger("product_introduction_creator")
    
    try:
        # 创建工作流引擎
        engine = WorkflowEngine()
        
        # 获取产品介绍生成模板
        template = template_library.get_template("product_introduction")
        
        # 定制模板配置
        customized_steps = template.steps.copy()
        
        # 根据品牌风格调整内容
        style_modifiers = {
            "professional": "专业商务",
            "casual": "轻松友好",
            "luxury": "奢华精致", 
            "tech": "科技现代",
            "eco": "环保自然",
            "youthful": "年轻活力"
        }
        
        style_desc = style_modifiers.get(brand_style, "专业")
        
        # 更新步骤配置
        for step in customized_steps:
            if step["id"] == "generate_marketing_copy":
                step["config"]["prompt"] += f" 品牌风格：{style_desc}，目标市场：{target_market}。"
            elif step["type"] == "parallel":
                for substep in step["config"]["steps"]:
                    if substep["type"] == "image_generation":
                        substep["config"]["prompt"] += f"，品牌风格{style_desc}"
                        substep["config"]["output_mode"] = output_mode
            elif step["type"] == "video_generation":
                step["config"]["output_mode"] = output_mode
        
        # 创建工作流
        workflow_id = await engine.create_workflow(
            config=template.config,
            steps_config=customized_steps,
            initial_context={
                "product_description": product_description,
                "brand_style": brand_style,
                "target_market": target_market,
                "language": language
            }
        )
        
        logger.info(f"开始创建产品介绍，工作流ID: {workflow_id}")
        
        # 启动工作流
        await engine.start_workflow(workflow_id)
        
        # 等待完成（最多15分钟）
        success = await engine.wait_for_completion(workflow_id, timeout=900)
        
        if not success:
            raise ToolExecutionError(
                "产品介绍创建超时",
                tool_name="create_product_introduction",
                details={"workflow_id": workflow_id}
            )
        
        # 获取最终状态
        status = await engine.get_workflow_status(workflow_id)
        
        if status["status"] != "completed":
            logs = await engine.get_workflow_logs(workflow_id)
            raise ToolExecutionError(
                f"产品介绍创建失败: {status.get('error', 'Unknown error')}",
                tool_name="create_product_introduction", 
                details={"workflow_id": workflow_id, "logs": logs}
            )
        
        # 加载工作流结果
        workflow_data = await engine.state_manager.load_workflow(workflow_id)
        if not workflow_data:
            raise ToolExecutionError(
                "无法加载工作流结果",
                tool_name="create_product_introduction"
            )
        
        dag, context, _, metadata = workflow_data
        
        # 提取结果
        result = {
            "success": True,
            "workflow_id": workflow_id,
            "marketing_copy": context.get("text", ""),
            "product_images": context.get("images", []),
            "demo_video": context.get("video_url", ""),
            "file_paths": {
                "images": context.get("file_paths", []),
                "video": context.get("file_path", "")
            },
            "metadata": {
                "product_description": product_description,
                "brand_style": brand_style,
                "target_market": target_market,
                "language": language,
                "execution_time": metadata.get("execution_time", 0),
                "copy_length": len(context.get("text", "")),
                "visual_assets": len(context.get("images", []))
            }
        }
        
        logger.info(f"产品介绍创建完成: {workflow_id}")
        return result
        
    except ToolExecutionError:
        raise
    except Exception as e:
        logger.error(f"产品介绍创建异常: {e}")
        raise ToolExecutionError(
            f"产品介绍创建失败: {str(e)}",
            tool_name="create_product_introduction",
            details={"error": str(e)}
        )


@tool(
    name="create_educational_content", 
    description="Create comprehensive educational content including lessons, diagrams, and videos"
)
async def create_educational_content(
    subject: str,
    target_audience: str = "学生",
    difficulty_level: str = "beginner",
    language: str = "zh",
    output_mode: str = "file"
) -> Dict[str, Any]:
    """
    创建教育内容
    
    Args:
        subject: 学科主题
        target_audience: 目标受众
        difficulty_level: 难度级别 (beginner, intermediate, advanced)
        language: 语言代码
        output_mode: 输出模式
    
    Returns:
        包含教育内容的字典
    """
    logger = get_logger("educational_content_creator")
    
    try:
        # 创建工作流引擎
        engine = WorkflowEngine()
        
        # 获取教育内容生成模板
        template = template_library.get_template("educational_content")
        
        # 定制模板配置
        customized_steps = template.steps.copy()
        
        # 根据难度级别调整内容深度
        difficulty_modifiers = {
            "beginner": "基础入门",
            "intermediate": "进阶提高", 
            "advanced": "高级深入"
        }
        
        difficulty_desc = difficulty_modifiers.get(difficulty_level, "基础")
        
        # 更新步骤配置
        for step in customized_steps:
            if "prompt" in step.get("config", {}):
                step["config"]["prompt"] = step["config"]["prompt"].replace(
                    "{{target_audience}}", f"{target_audience}（{difficulty_desc}级别）"
                )
            elif step["type"] == "parallel":
                for substep in step["config"]["steps"]:
                    if substep["type"] == "image_generation":
                        substep["config"]["output_mode"] = output_mode
            elif step["type"] == "video_generation":
                step["config"]["output_mode"] = output_mode
        
        # 创建工作流
        workflow_id = await engine.create_workflow(
            config=template.config,
            steps_config=customized_steps,
            initial_context={
                "subject": subject,
                "target_audience": target_audience,
                "difficulty_level": difficulty_level,
                "language": language
            }
        )
        
        logger.info(f"开始创建教育内容，工作流ID: {workflow_id}")
        
        # 启动工作流
        await engine.start_workflow(workflow_id)
        
        # 等待完成（最多25分钟）
        success = await engine.wait_for_completion(workflow_id, timeout=1500)
        
        if not success:
            raise ToolExecutionError(
                "教育内容创建超时",
                tool_name="create_educational_content",
                details={"workflow_id": workflow_id}
            )
        
        # 获取最终状态
        status = await engine.get_workflow_status(workflow_id)
        
        if status["status"] != "completed":
            logs = await engine.get_workflow_logs(workflow_id)
            raise ToolExecutionError(
                f"教育内容创建失败: {status.get('error', 'Unknown error')}",
                tool_name="create_educational_content",
                details={"workflow_id": workflow_id, "logs": logs}
            )
        
        # 加载工作流结果
        workflow_data = await engine.state_manager.load_workflow(workflow_id)
        if not workflow_data:
            raise ToolExecutionError(
                "无法加载工作流结果",
                tool_name="create_educational_content"
            )
        
        dag, context, _, metadata = workflow_data
        
        # 提取结果
        result = {
            "success": True,
            "workflow_id": workflow_id,
            "lesson_content": context.get("text", ""),
            "educational_diagrams": context.get("images", []),
            "teaching_video": context.get("video_url", ""),
            "file_paths": {
                "images": context.get("file_paths", []),
                "video": context.get("file_path", "")
            },
            "metadata": {
                "subject": subject,
                "target_audience": target_audience,
                "difficulty_level": difficulty_level,
                "language": language,
                "execution_time": metadata.get("execution_time", 0),
                "content_length": len(context.get("text", "")),
                "visual_aids": len(context.get("images", []))
            }
        }
        
        logger.info(f"教育内容创建完成: {workflow_id}")
        return result
        
    except ToolExecutionError:
        raise
    except Exception as e:
        logger.error(f"教育内容创建异常: {e}")
        raise ToolExecutionError(
            f"教育内容创建失败: {str(e)}",
            tool_name="create_educational_content", 
            details={"error": str(e)}
        )