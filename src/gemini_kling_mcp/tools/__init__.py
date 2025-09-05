"""
工具模块

提供 Gemini-Kling MCP 服务的所有工具实现。
"""

# 导入所有工具模块以注册工具
from . import text_generation
from . import chat_completion
from . import text_analysis

# 导出注册表
from .registry import default_registry, get_registry, tool, register_tool

# 清理函数
async def cleanup_all_tools():
    """清理所有工具的资源"""
    await text_generation.cleanup_text_generation()
    await chat_completion.cleanup_chat_completion() 
    await text_analysis.cleanup_text_analysis()

__all__ = [
    "default_registry",
    "get_registry",
    "tool",
    "register_tool",
    "cleanup_all_tools"
]