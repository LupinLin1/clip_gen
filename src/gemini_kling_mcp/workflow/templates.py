"""
工作流模板

提供预设的工作流模板，用于常见的创意工作场景。
"""

from typing import Dict, List, Any
from dataclasses import dataclass

from .engine import WorkflowConfig


@dataclass
class WorkflowTemplate:
    """工作流模板"""
    id: str
    name: str
    description: str
    config: WorkflowConfig
    steps: List[Dict[str, Any]]
    example_inputs: Dict[str, Any]
    expected_outputs: List[str]
    tags: List[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "config": self.config.to_dict(),
            "steps": self.steps,
            "example_inputs": self.example_inputs,
            "expected_outputs": self.expected_outputs,
            "tags": self.tags or []
        }


class WorkflowTemplateLibrary:
    """工作流模板库"""
    
    def __init__(self):
        self.templates = {}
        self._load_builtin_templates()
    
    def _load_builtin_templates(self):
        """加载内置模板"""
        # 故事视频生成工作流
        story_video_template = WorkflowTemplate(
            id="story_video_generation",
            name="故事视频生成",
            description="基于用户输入的故事主题，自动生成脚本、图像和视频的完整工作流",
            config=WorkflowConfig(
                name="故事视频生成",
                description="从故事概念到完整视频的自动化流程",
                max_concurrent_steps=2,
                retry_failed_steps=True,
                timeout_seconds=3600,  # 1小时
                save_intermediate_results=True
            ),
            steps=[
                {
                    "id": "generate_script",
                    "name": "生成故事脚本",
                    "type": "text_generation",
                    "config": {
                        "prompt": "请为以下故事主题创作一个简短但引人入胜的故事脚本：{{story_theme}}。脚本应该包含：1. 引人入胜的开头，2. 发展过程，3. 高潮，4. 结局。每个部分用换行符分隔，总长度控制在300字左右。",
                        "model": "gemini-1.5-flash-002",
                        "max_tokens": 800,
                        "temperature": 0.8
                    },
                    "dependencies": []
                },
                {
                    "id": "extract_scenes",
                    "name": "提取场景描述",
                    "type": "text_analysis",
                    "config": {
                        "text": "{{text}}",
                        "analysis_type": "keywords",
                        "language": "zh"
                    },
                    "dependencies": ["generate_script"]
                },
                {
                    "id": "generate_scene_images",
                    "name": "生成场景图像",
                    "type": "parallel",
                    "config": {
                        "steps": [
                            {
                                "type": "image_generation",
                                "config": {
                                    "prompt": "为故事脚本的开场部分创建一个视觉场景：{{text}}",
                                    "model": "imagen-3.0-generate-001",
                                    "num_images": 1,
                                    "aspect_ratio": "16:9",
                                    "output_mode": "file"
                                }
                            },
                            {
                                "type": "image_generation", 
                                "config": {
                                    "prompt": "为故事脚本的结尾部分创建一个视觉场景：{{text}}",
                                    "model": "imagen-3.0-generate-001",
                                    "num_images": 1,
                                    "aspect_ratio": "16:9",
                                    "output_mode": "file"
                                }
                            }
                        ],
                        "max_concurrency": 2
                    },
                    "dependencies": ["extract_scenes"]
                },
                {
                    "id": "create_story_video",
                    "name": "创建故事视频",
                    "type": "video_generation",
                    "config": {
                        "prompt": "基于这个故事创建一个引人入胜的短视频：{{text}}",
                        "duration": 10,
                        "aspect_ratio": "16:9",
                        "output_mode": "file"
                    },
                    "dependencies": ["generate_scene_images"]
                }
            ],
            example_inputs={
                "story_theme": "一只勇敢的小猫在城市中寻找失踪的主人"
            },
            expected_outputs=[
                "text",  # 生成的故事脚本
                "images",  # 场景图像
                "video_url"  # 最终视频
            ],
            tags=["故事", "视频", "创意", "自动化"]
        )
        
        # 多媒体内容创作工作流
        multimedia_content_template = WorkflowTemplate(
            id="multimedia_content_creation",
            name="多媒体内容创作",
            description="为给定主题创建包含文本、图像和视频的完整多媒体内容",
            config=WorkflowConfig(
                name="多媒体内容创作",
                description="从主题到多媒体内容的全流程创作",
                max_concurrent_steps=3,
                retry_failed_steps=True,
                save_intermediate_results=True
            ),
            steps=[
                {
                    "id": "generate_article",
                    "name": "生成文章内容",
                    "type": "text_generation",
                    "config": {
                        "prompt": "请为主题 '{{topic}}' 写一篇引人入胜的文章。文章应该包含：1. 吸引人的标题，2. 引言段落，3. 3-4个主要内容段落，4. 总结段落。总字数800-1000字。",
                        "model": "gemini-1.5-pro-002",
                        "max_tokens": 1500,
                        "temperature": 0.7
                    },
                    "dependencies": []
                },
                {
                    "id": "create_feature_image",
                    "name": "创建特色图像",
                    "type": "image_generation",
                    "config": {
                        "prompt": "为主题 '{{topic}}' 创建一个专业的特色图像，风格现代简约，适合作为文章配图",
                        "model": "imagen-3.0-generate-001",
                        "num_images": 2,
                        "aspect_ratio": "16:9",
                        "output_mode": "file"
                    },
                    "dependencies": []
                },
                {
                    "id": "generate_summary",
                    "name": "生成内容摘要",
                    "type": "text_analysis",
                    "config": {
                        "text": "{{text}}",
                        "analysis_type": "summarize",
                        "max_tokens": 300
                    },
                    "dependencies": ["generate_article"]
                },
                {
                    "id": "create_promotional_video",
                    "name": "创建推广视频",
                    "type": "video_generation",
                    "config": {
                        "prompt": "为主题 '{{topic}}' 创建一个30秒的推广视频，展示主要内容要点：{{analysis}}",
                        "duration": 5,
                        "aspect_ratio": "9:16",
                        "output_mode": "file"
                    },
                    "dependencies": ["generate_summary", "create_feature_image"]
                }
            ],
            example_inputs={
                "topic": "人工智能在教育中的应用前景"
            },
            expected_outputs=[
                "text",  # 文章内容
                "analysis",  # 摘要
                "images",  # 特色图像
                "video_url"  # 推广视频
            ],
            tags=["内容创作", "多媒体", "营销", "自动化"]
        )
        
        # 产品介绍生成工作流
        product_intro_template = WorkflowTemplate(
            id="product_introduction",
            name="产品介绍生成",
            description="为产品自动生成介绍文案、产品图片和演示视频",
            config=WorkflowConfig(
                name="产品介绍生成",
                description="全面的产品营销内容自动生成",
                max_concurrent_steps=2,
                retry_failed_steps=True,
                save_intermediate_results=True
            ),
            steps=[
                {
                    "id": "analyze_product_features",
                    "name": "分析产品特性",
                    "type": "text_analysis",
                    "config": {
                        "text": "{{product_description}}",
                        "analysis_type": "keywords",
                        "language": "zh"
                    },
                    "dependencies": []
                },
                {
                    "id": "generate_marketing_copy",
                    "name": "生成营销文案",
                    "type": "text_generation",
                    "config": {
                        "prompt": "基于以下产品信息：{{product_description}}，请生成一份专业的营销文案。包含：1. 吸引人的产品标题，2. 核心卖点（3-5个），3. 产品优势，4. 使用场景，5. 行动号召。",
                        "model": "gemini-1.5-flash-002",
                        "max_tokens": 1000,
                        "temperature": 0.6
                    },
                    "dependencies": ["analyze_product_features"]
                },
                {
                    "id": "create_product_visuals",
                    "name": "创建产品视觉",
                    "type": "parallel",
                    "config": {
                        "steps": [
                            {
                                "type": "image_generation",
                                "config": {
                                    "prompt": "为产品创建一个专业的展示图：{{product_description}}，风格简约现代，白色背景",
                                    "model": "imagen-3.0-generate-001",
                                    "num_images": 1,
                                    "aspect_ratio": "1:1"
                                }
                            },
                            {
                                "type": "image_generation",
                                "config": {
                                    "prompt": "为产品创建一个使用场景图：{{product_description}}，展示实际应用环境",
                                    "model": "imagen-3.0-generate-001", 
                                    "num_images": 1,
                                    "aspect_ratio": "16:9"
                                }
                            }
                        ]
                    },
                    "dependencies": ["analyze_product_features"]
                },
                {
                    "id": "create_demo_video",
                    "name": "创建演示视频",
                    "type": "video_generation",
                    "config": {
                        "prompt": "为产品创建一个演示视频：{{text}}。展示产品的主要功能和使用方法",
                        "duration": 15,
                        "aspect_ratio": "16:9",
                        "output_mode": "file"
                    },
                    "dependencies": ["generate_marketing_copy", "create_product_visuals"]
                }
            ],
            example_inputs={
                "product_description": "智能家居语音助手，支持语音控制家电、播放音乐、查询天气等功能"
            },
            expected_outputs=[
                "text",  # 营销文案
                "images",  # 产品图片
                "video_url"  # 演示视频
            ],
            tags=["产品", "营销", "演示", "自动化"]
        )
        
        # 教育内容生成工作流
        educational_content_template = WorkflowTemplate(
            id="educational_content",
            name="教育内容生成",
            description="为指定主题创建教育内容，包括讲义、插图和教学视频",
            config=WorkflowConfig(
                name="教育内容生成",
                description="完整的教学内容自动生成流程",
                max_concurrent_steps=2,
                retry_failed_steps=True,
                save_intermediate_results=True
            ),
            steps=[
                {
                    "id": "create_lesson_outline",
                    "name": "创建课程大纲",
                    "type": "text_generation",
                    "config": {
                        "prompt": "请为主题 '{{subject}}' 创建一个详细的教学大纲。包含：1. 学习目标（3-5个），2. 知识点结构（分为4-6个部分），3. 每个部分的要点，4. 实践练习建议。适合{{target_audience}}学习。",
                        "model": "gemini-1.5-pro-002",
                        "max_tokens": 1200,
                        "temperature": 0.3
                    },
                    "dependencies": []
                },
                {
                    "id": "generate_detailed_content",
                    "name": "生成详细内容",
                    "type": "text_generation",
                    "config": {
                        "prompt": "基于以下课程大纲：{{text}}，请为主题 '{{subject}}' 编写详细的教学内容。每个知识点都要有清晰的解释、例子和总结。",
                        "model": "gemini-1.5-flash-002",
                        "max_tokens": 2000,
                        "temperature": 0.4
                    },
                    "dependencies": ["create_lesson_outline"]
                },
                {
                    "id": "create_educational_diagrams",
                    "name": "创建教学图表",
                    "type": "parallel",
                    "config": {
                        "steps": [
                            {
                                "type": "image_generation",
                                "config": {
                                    "prompt": "为主题 '{{subject}}' 创建一个清晰的概念图解，风格简约教育性强",
                                    "model": "imagen-3.0-generate-001",
                                    "num_images": 1,
                                    "aspect_ratio": "4:3"
                                }
                            },
                            {
                                "type": "image_generation",
                                "config": {
                                    "prompt": "为主题 '{{subject}}' 创建一个实践应用的示意图，便于理解",
                                    "model": "imagen-3.0-generate-001",
                                    "num_images": 1,
                                    "aspect_ratio": "16:9"
                                }
                            }
                        ]
                    },
                    "dependencies": ["create_lesson_outline"]
                },
                {
                    "id": "create_teaching_video",
                    "name": "创建教学视频",
                    "type": "video_generation",
                    "config": {
                        "prompt": "为主题 '{{subject}}' 创建一个教学视频，结合以下内容：{{text}}。视频应该清晰易懂，适合{{target_audience}}观看。",
                        "duration": 30,
                        "aspect_ratio": "16:9",
                        "output_mode": "file"
                    },
                    "dependencies": ["generate_detailed_content", "create_educational_diagrams"]
                }
            ],
            example_inputs={
                "subject": "Python编程基础",
                "target_audience": "编程初学者"
            },
            expected_outputs=[
                "text",  # 课程内容
                "images",  # 教学图表
                "video_url"  # 教学视频
            ],
            tags=["教育", "教学", "编程", "自动化"]
        )
        
        # 社交媒体内容工作流
        social_media_template = WorkflowTemplate(
            id="social_media_content",
            name="社交媒体内容生成",
            description="为社交媒体平台生成文案、配图和短视频内容",
            config=WorkflowConfig(
                name="社交媒体内容生成",
                description="适合多平台的社媒内容自动化生成",
                max_concurrent_steps=3,
                retry_failed_steps=True,
                save_intermediate_results=True
            ),
            steps=[
                {
                    "id": "generate_post_copy",
                    "name": "生成帖子文案",
                    "type": "text_generation",
                    "config": {
                        "prompt": "为主题 '{{topic}}' 创建吸引人的社交媒体文案。要求：1. 开头要有吸引力，2. 包含相关话题标签，3. 鼓励互动，4. 文案长度适中（100-200字），5. 语言轻松有趣。",
                        "model": "gemini-1.5-flash-002",
                        "max_tokens": 500,
                        "temperature": 0.8
                    },
                    "dependencies": []
                },
                {
                    "id": "create_social_images",
                    "name": "创建社媒配图",
                    "type": "parallel",
                    "config": {
                        "steps": [
                            {
                                "type": "image_generation",
                                "config": {
                                    "prompt": "为社交媒体创建一个吸引眼球的配图，主题：{{topic}}，风格年轻时尚",
                                    "model": "imagen-3.0-generate-001",
                                    "num_images": 1,
                                    "aspect_ratio": "1:1"
                                }
                            },
                            {
                                "type": "image_generation",
                                "config": {
                                    "prompt": "为Instagram故事创建一个竖屏配图，主题：{{topic}}，风格现代简约",
                                    "model": "imagen-3.0-generate-001",
                                    "num_images": 1,
                                    "aspect_ratio": "9:16"
                                }
                            }
                        ]
                    },
                    "dependencies": []
                },
                {
                    "id": "create_short_video",
                    "name": "创建短视频",
                    "type": "video_generation",
                    "config": {
                        "prompt": "为社交媒体创建一个引人入胜的短视频，主题：{{topic}}，文案：{{text}}。视频要有活力和吸引力。",
                        "duration": 10,
                        "aspect_ratio": "9:16",
                        "output_mode": "file"
                    },
                    "dependencies": ["generate_post_copy", "create_social_images"]
                }
            ],
            example_inputs={
                "topic": "健康生活小贴士"
            },
            expected_outputs=[
                "text",  # 帖子文案
                "images",  # 社媒配图
                "video_url"  # 短视频
            ],
            tags=["社交媒体", "内容营销", "短视频", "自动化"]
        )
        
        # 注册所有模板
        self.templates[story_video_template.id] = story_video_template
        self.templates[multimedia_content_template.id] = multimedia_content_template
        self.templates[product_intro_template.id] = product_intro_template
        self.templates[educational_content_template.id] = educational_content_template
        self.templates[social_media_template.id] = social_media_template
    
    def get_template(self, template_id: str) -> WorkflowTemplate:
        """获取模板"""
        template = self.templates.get(template_id)
        if not template:
            raise ValueError(f"模板 {template_id} 不存在")
        return template
    
    def list_templates(self, tag: str = None) -> List[WorkflowTemplate]:
        """列出所有模板，可按标签筛选"""
        templates = list(self.templates.values())
        
        if tag:
            templates = [t for t in templates if tag in (t.tags or [])]
        
        return templates
    
    def search_templates(self, keyword: str) -> List[WorkflowTemplate]:
        """搜索模板"""
        keyword = keyword.lower()
        results = []
        
        for template in self.templates.values():
            # 在名称、描述、标签中搜索
            if (keyword in template.name.lower() or 
                keyword in template.description.lower() or
                any(keyword in tag.lower() for tag in (template.tags or []))):
                results.append(template)
        
        return results
    
    def add_template(self, template: WorkflowTemplate) -> None:
        """添加自定义模板"""
        self.templates[template.id] = template
    
    def remove_template(self, template_id: str) -> None:
        """删除模板"""
        if template_id in self.templates:
            del self.templates[template_id]
    
    def export_template(self, template_id: str) -> Dict[str, Any]:
        """导出模板配置"""
        template = self.get_template(template_id)
        return template.to_dict()
    
    def import_template(self, template_data: Dict[str, Any]) -> WorkflowTemplate:
        """导入模板配置"""
        config = WorkflowConfig.from_dict(template_data["config"])
        
        template = WorkflowTemplate(
            id=template_data["id"],
            name=template_data["name"],
            description=template_data["description"],
            config=config,
            steps=template_data["steps"],
            example_inputs=template_data["example_inputs"],
            expected_outputs=template_data["expected_outputs"],
            tags=template_data.get("tags", [])
        )
        
        self.add_template(template)
        return template


# 全局模板库实例
template_library = WorkflowTemplateLibrary()