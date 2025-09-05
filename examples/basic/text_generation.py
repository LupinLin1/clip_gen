#!/usr/bin/env python3
"""
文本生成基础示例

这个示例演示如何使用 Gemini MCP 服务进行文本生成。
包括不同类型的文本生成：创作、翻译、摘要等。

运行示例:
    python examples/basic/text_generation.py

环境变量:
    GEMINI_API_KEY: Gemini API密钥 (必需)
    OUTPUT_DIR: 输出目录 (可选，默认: ./output)
    LOG_LEVEL: 日志级别 (可选，默认: info)
"""

import asyncio
import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.gemini_kling_mcp.tools.text_generation import generate_text
from src.gemini_kling_mcp.services.gemini.models import GeminiModel

# 配置日志
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_output_directory() -> Path:
    """设置输出目录"""
    output_dir = Path(os.getenv('OUTPUT_DIR', './output'))
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


async def creative_writing_example():
    """创意写作示例"""
    logger.info("开始创意写作示例...")
    
    prompts = [
        {
            "name": "科幻小故事",
            "prompt": "写一个200字左右的科幻小故事，关于一个机器人发现了情感的故事。",
            "max_tokens": 300,
            "temperature": 0.8
        },
        {
            "name": "诗歌创作",
            "prompt": "创作一首关于春天的现代诗，表达对自然的赞美。",
            "max_tokens": 200,
            "temperature": 0.9
        },
        {
            "name": "产品描述",
            "prompt": "为一款智能手表写一段有吸引力的产品描述，突出其健康监测功能。",
            "max_tokens": 150,
            "temperature": 0.7
        }
    ]
    
    results = []
    for prompt_info in prompts:
        try:
            logger.info(f"生成: {prompt_info['name']}")
            
            result = await generate_text(
                prompt=prompt_info["prompt"],
                model=GeminiModel.GEMINI_15_FLASH,
                max_tokens=prompt_info["max_tokens"],
                temperature=prompt_info["temperature"]
            )
            
            if result["success"]:
                results.append({
                    "name": prompt_info["name"],
                    "prompt": prompt_info["prompt"],
                    "response": result["text"],
                    "model": result["model"]
                })
                logger.info(f"✅ {prompt_info['name']} 生成成功")
            else:
                logger.error(f"❌ {prompt_info['name']} 生成失败: {result.get('error', '未知错误')}")
                
        except Exception as e:
            logger.error(f"❌ {prompt_info['name']} 生成异常: {e}")
    
    return results


async def text_processing_example():
    """文本处理示例"""
    logger.info("开始文本处理示例...")
    
    source_text = """
    人工智能(Artificial Intelligence，AI)是一门极富挑战性的科学，从事这项工作的人必须懂得计算机知识、
    心理学和哲学。人工智能是包括十分广泛的科学，它由不同的领域组成，如机器学习、计算机视觉等等，
    总的说来，人工智能研究的一个主要目标是使机器能够胜任一些通常需要人类智能才能完成的复杂工作。
    """
    
    tasks = [
        {
            "name": "文本摘要",
            "prompt": f"请为以下文本生成一个简洁的摘要（50字以内）：\n\n{source_text}",
            "max_tokens": 100
        },
        {
            "name": "关键词提取",
            "prompt": f"从以下文本中提取5个最重要的关键词：\n\n{source_text}",
            "max_tokens": 50
        },
        {
            "name": "文本翻译",
            "prompt": f"将以下中文文本翻译成英文：\n\n{source_text.strip()}",
            "max_tokens": 200
        }
    ]
    
    results = []
    for task in tasks:
        try:
            logger.info(f"处理: {task['name']}")
            
            result = await generate_text(
                prompt=task["prompt"],
                model=GeminiModel.GEMINI_15_FLASH,
                max_tokens=task["max_tokens"],
                temperature=0.3  # 低温度确保准确性
            )
            
            if result["success"]:
                results.append({
                    "name": task["name"],
                    "response": result["text"]
                })
                logger.info(f"✅ {task['name']} 处理成功")
            else:
                logger.error(f"❌ {task['name']} 处理失败: {result.get('error', '未知错误')}")
                
        except Exception as e:
            logger.error(f"❌ {task['name']} 处理异常: {e}")
    
    return results


async def conversational_example():
    """对话式生成示例"""
    logger.info("开始对话式生成示例...")
    
    # 模拟多轮对话
    conversation_history = []
    
    conversation_turns = [
        "你好，我想了解人工智能的基础知识。",
        "机器学习和深度学习有什么区别？",
        "能给我推荐一些学习资源吗？",
        "谢谢你的建议！"
    ]
    
    results = []
    for i, user_input in enumerate(conversation_turns):
        try:
            logger.info(f"对话轮次 {i+1}: {user_input[:30]}...")
            
            # 构建包含历史的提示
            context = "\n".join([
                f"用户: {turn['user']}\n助手: {turn['assistant']}" 
                for turn in conversation_history
            ])
            
            prompt = f"""你是一个友好且知识渊博的AI助手。请根据对话历史回答用户的问题。

对话历史:
{context}

用户: {user_input}
助手:"""
            
            result = await generate_text(
                prompt=prompt,
                model=GeminiModel.GEMINI_15_FLASH,
                max_tokens=200,
                temperature=0.7
            )
            
            if result["success"]:
                assistant_response = result["text"].strip()
                
                # 更新对话历史
                conversation_history.append({
                    "user": user_input,
                    "assistant": assistant_response
                })
                
                results.append({
                    "turn": i + 1,
                    "user": user_input,
                    "assistant": assistant_response
                })
                
                logger.info(f"✅ 对话轮次 {i+1} 完成")
            else:
                logger.error(f"❌ 对话轮次 {i+1} 失败: {result.get('error', '未知错误')}")
                break
                
        except Exception as e:
            logger.error(f"❌ 对话轮次 {i+1} 异常: {e}")
            break
    
    return results


async def specialized_generation_example():
    """专业领域生成示例"""
    logger.info("开始专业领域生成示例...")
    
    specialized_tasks = [
        {
            "name": "代码生成",
            "prompt": "编写一个Python函数，实现二分查找算法，包含详细注释。",
            "max_tokens": 300,
            "temperature": 0.2
        },
        {
            "name": "技术文档",
            "prompt": "为REST API编写一个简单的使用文档，包括端点、参数和示例。",
            "max_tokens": 400,
            "temperature": 0.3
        },
        {
            "name": "商业提案",
            "prompt": "为一个在线教育平台写一段商业提案的执行摘要（200字以内）。",
            "max_tokens": 250,
            "temperature": 0.6
        },
        {
            "name": "学术写作",
            "prompt": "写一段关于机器学习在医疗诊断中应用的学术论文摘要。",
            "max_tokens": 200,
            "temperature": 0.4
        }
    ]
    
    results = []
    for task in specialized_tasks:
        try:
            logger.info(f"生成: {task['name']}")
            
            result = await generate_text(
                prompt=task["prompt"],
                model=GeminiModel.GEMINI_15_FLASH,
                max_tokens=task["max_tokens"],
                temperature=task["temperature"]
            )
            
            if result["success"]:
                results.append({
                    "name": task["name"],
                    "response": result["text"],
                    "tokens": result.get("token_count", 0),
                    "model": result["model"]
                })
                logger.info(f"✅ {task['name']} 生成成功")
            else:
                logger.error(f"❌ {task['name']} 生成失败: {result.get('error', '未知错误')}")
                
        except Exception as e:
            logger.error(f"❌ {task['name']} 生成异常: {e}")
    
    return results


def save_results_to_file(results: dict, output_dir: Path):
    """保存结果到文件"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"text_generation_results_{timestamp}.txt"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"文本生成示例结果\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 50 + "\n\n")
        
        for category, items in results.items():
            f.write(f"## {category}\n\n")
            
            if category == "对话式生成":
                for item in items:
                    f.write(f"轮次 {item['turn']}:\n")
                    f.write(f"用户: {item['user']}\n")
                    f.write(f"助手: {item['assistant']}\n\n")
            else:
                for item in items:
                    f.write(f"### {item['name']}\n")
                    if 'prompt' in item:
                        f.write(f"提示: {item['prompt'][:100]}...\n")
                    f.write(f"响应: {item['response']}\n")
                    if 'model' in item:
                        f.write(f"模型: {item['model']}\n")
                    f.write("\n" + "-" * 30 + "\n\n")
    
    logger.info(f"结果已保存到: {output_file}")


async def main():
    """主函数"""
    logger.info("🚀 开始文本生成示例...")
    
    # 检查环境变量
    if not os.getenv('GEMINI_API_KEY'):
        logger.error("❌ 请设置 GEMINI_API_KEY 环境变量")
        sys.exit(1)
    
    # 设置输出目录
    output_dir = setup_output_directory()
    logger.info(f"输出目录: {output_dir.absolute()}")
    
    try:
        # 运行所有示例
        results = {}
        
        # 创意写作示例
        creative_results = await creative_writing_example()
        if creative_results:
            results["创意写作"] = creative_results
        
        # 文本处理示例
        processing_results = await text_processing_example()
        if processing_results:
            results["文本处理"] = processing_results
        
        # 对话式生成示例
        conversation_results = await conversational_example()
        if conversation_results:
            results["对话式生成"] = conversation_results
        
        # 专业领域生成示例
        specialized_results = await specialized_generation_example()
        if specialized_results:
            results["专业领域生成"] = specialized_results
        
        # 保存结果
        if results:
            save_results_to_file(results, output_dir)
            
            # 打印摘要
            total_successful = sum(len(items) for items in results.values())
            logger.info(f"✅ 示例运行完成！成功生成 {total_successful} 个文本")
            logger.info("📁 查看详细结果，请打开输出文件")
        else:
            logger.warning("⚠️ 没有成功的生成结果")
    
    except KeyboardInterrupt:
        logger.info("⏹️ 用户中断执行")
    except Exception as e:
        logger.error(f"❌ 执行出错: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())