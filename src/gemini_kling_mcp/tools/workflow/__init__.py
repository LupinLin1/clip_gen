"""
工作流工具模块

提供基于工作流引擎的高级AI工具，包括故事视频生成、多媒体创作等复杂流程。
"""

from .story_video_generator import generate_story_video, generate_story_video_batch
from .multimedia_creator import (
    create_multimedia_content, 
    create_product_introduction,
    create_educational_content
)
from .workflow_manager import (
    create_custom_workflow,
    execute_workflow,
    get_workflow_status,
    list_workflows,
    cancel_workflow,
    list_workflow_templates,
    create_workflow_from_template
)

__all__ = [
    # 故事视频生成
    "generate_story_video",
    "generate_story_video_batch",
    
    # 多媒体创作
    "create_multimedia_content",
    "create_product_introduction", 
    "create_educational_content",
    
    # 工作流管理
    "create_custom_workflow",
    "execute_workflow",
    "get_workflow_status",
    "list_workflows",
    "cancel_workflow",
    "list_workflow_templates",
    "create_workflow_from_template"
]