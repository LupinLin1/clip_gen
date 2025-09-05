"""
故事视频生成工具

使用工作流引擎实现完整的故事视频生成流程。
"""

import asyncio
from typing import Dict, Any, Optional, List

from ...logger import get_logger
from ...exceptions import ToolExecutionError
from ...workflow import WorkflowEngine, template_library
from ...tools.registry import tool


@tool(
    name="generate_story_video",
    description="Generate a complete story video from a theme using AI workflow"
)
async def generate_story_video(
    story_theme: str,
    style: str = "realistic",
    duration: int = 10,
    language: str = "zh",
    output_mode: str = "file"
) -> Dict[str, Any]:
    """
    生成故事视频
    
    Args:
        story_theme: 故事主题
        style: 视觉风格 (realistic, cartoon, anime, etc.)
        duration: 视频时长（秒）
        language: 语言代码
        output_mode: 输出模式 (file, base64)
    
    Returns:
        包含生成内容的字典
    """
    logger = get_logger("story_video_generator")
    
    try:
        # 创建工作流引擎
        engine = WorkflowEngine()
        
        # 获取故事视频生成模板
        template = template_library.get_template("story_video_generation")
        
        # 定制模板配置
        customized_steps = template.steps.copy()
        
        # 更新图像生成步骤的风格
        for step in customized_steps:
            if step["type"] == "parallel":
                for substep in step["config"]["steps"]:
                    if substep["type"] == "image_generation":
                        prompt = substep["config"]["prompt"]
                        substep["config"]["prompt"] = f"{prompt}，风格：{style}"
                        substep["config"]["output_mode"] = output_mode
            elif step["type"] == "video_generation":
                step["config"]["duration"] = duration
                step["config"]["output_mode"] = output_mode
        
        # 创建工作流
        workflow_id = await engine.create_workflow(
            config=template.config,
            steps_config=customized_steps,
            initial_context={
                "story_theme": story_theme,
                "style": style,
                "duration": duration,
                "language": language
            }
        )
        
        logger.info(f"开始生成故事视频，工作流ID: {workflow_id}")
        
        # 启动工作流
        await engine.start_workflow(workflow_id)
        
        # 等待完成（最多30分钟）
        success = await engine.wait_for_completion(workflow_id, timeout=1800)
        
        if not success:
            raise ToolExecutionError(
                "故事视频生成超时",
                tool_name="generate_story_video",
                details={"workflow_id": workflow_id}
            )
        
        # 获取最终状态
        status = await engine.get_workflow_status(workflow_id)
        
        if status["status"] != "completed":
            logs = await engine.get_workflow_logs(workflow_id)
            raise ToolExecutionError(
                f"故事视频生成失败: {status.get('error', 'Unknown error')}",
                tool_name="generate_story_video",
                details={"workflow_id": workflow_id, "logs": logs}
            )
        
        # 加载工作流结果
        workflow_data = await engine.state_manager.load_workflow(workflow_id)
        if not workflow_data:
            raise ToolExecutionError(
                "无法加载工作流结果",
                tool_name="generate_story_video"
            )
        
        dag, context, _, metadata = workflow_data
        
        # 提取结果
        result = {
            "success": True,
            "workflow_id": workflow_id,
            "story_script": context.get("text", ""),
            "scene_images": context.get("images", []),
            "video_url": context.get("video_url", ""),
            "file_paths": {
                "images": context.get("file_paths", []),
                "video": context.get("file_path", "")
            },
            "metadata": {
                "theme": story_theme,
                "style": style,
                "duration": duration,
                "language": language,
                "execution_time": metadata.get("execution_time", 0),
                "steps_completed": len([n for n in dag.get_all_nodes() if n.status.value == "completed"])
            }
        }
        
        logger.info(f"故事视频生成完成: {workflow_id}")
        return result
        
    except ToolExecutionError:
        raise
    except Exception as e:
        logger.error(f"故事视频生成异常: {e}")
        raise ToolExecutionError(
            f"故事视频生成失败: {str(e)}",
            tool_name="generate_story_video",
            details={"error": str(e)}
        )


@tool(
    name="generate_story_video_batch",
    description="Generate multiple story videos in batch"
)
async def generate_story_video_batch(
    story_themes: List[str],
    style: str = "realistic",
    duration: int = 10,
    language: str = "zh",
    output_mode: str = "file",
    concurrent_limit: int = 2
) -> Dict[str, Any]:
    """
    批量生成故事视频
    
    Args:
        story_themes: 故事主题列表
        style: 视觉风格
        duration: 视频时长（秒）
        language: 语言代码
        output_mode: 输出模式
        concurrent_limit: 并发限制
    
    Returns:
        批量生成结果
    """
    logger = get_logger("story_video_batch_generator")
    
    try:
        logger.info(f"开始批量生成 {len(story_themes)} 个故事视频")
        
        # 创建信号量限制并发
        semaphore = asyncio.Semaphore(concurrent_limit)
        
        async def generate_single_story(theme: str, index: int) -> Dict[str, Any]:
            async with semaphore:
                try:
                    result = await generate_story_video(
                        story_theme=theme,
                        style=style,
                        duration=duration,
                        language=language,
                        output_mode=output_mode
                    )
                    return {
                        "index": index,
                        "theme": theme,
                        "success": True,
                        "result": result
                    }
                except Exception as e:
                    logger.error(f"主题 '{theme}' 生成失败: {e}")
                    return {
                        "index": index,
                        "theme": theme,
                        "success": False,
                        "error": str(e)
                    }
        
        # 并发执行
        tasks = [
            generate_single_story(theme, i) 
            for i, theme in enumerate(story_themes)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # 统计结果
        successful = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]
        
        batch_result = {
            "success": True,
            "summary": {
                "total": len(story_themes),
                "successful": len(successful),
                "failed": len(failed),
                "success_rate": len(successful) / len(story_themes) * 100
            },
            "results": results,
            "successful_videos": [r["result"] for r in successful],
            "errors": [{"theme": r["theme"], "error": r["error"]} for r in failed]
        }
        
        logger.info(f"批量生成完成: {len(successful)}/{len(story_themes)} 成功")
        return batch_result
        
    except Exception as e:
        logger.error(f"批量故事视频生成异常: {e}")
        raise ToolExecutionError(
            f"批量故事视频生成失败: {str(e)}",
            tool_name="generate_story_video_batch",
            details={"error": str(e)}
        )