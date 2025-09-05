# Gemini Kling MCP 服务

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-90%2B-green.svg)](htmlcov/index.html)

一个强大的模型上下文协议(MCP)服务，集成Gemini文本/图像生成和Kling视频生成功能，提供完整的多媒体内容创作工作流。

## 📋 功能特性

### 🎯 核心功能
- **🤖 Gemini AI服务**: 文本生成、对话完成、文本分析、图像生成
- **🎬 Kling视频服务**: 文本生成视频、图像生成视频、关键帧控制
- **🔄 智能工作流**: 预定义模板和自定义工作流支持
- **📁 文件管理**: 临时文件管理和自动清理
- **⚡ 异步处理**: 高性能并发处理
- **🔧 灵活配置**: 支持多种输出格式和参数配置

### 🚀 高级特性
- **故事视频生成**: 从主题到完整视频的端到端生成
- **批量处理**: 支持大规模批量内容生成
- **状态管理**: 工作流状态持久化和恢复
- **进度跟踪**: 实时任务进度监控
- **错误处理**: 完善的异常处理和重试机制
- **性能优化**: 内置缓存和资源管理

## 🚀 快速开始

### 安装要求
- Python 3.8+
- 必需的API密钥:
  - Gemini API密钥 (通过gptproto.com)
  - Kling API密钥

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd clip_gen
```

2. **安装依赖**
```bash
# 安装项目依赖
pip install -e .

# 安装开发依赖（可选）
pip install -r requirements-dev.txt
```

3. **设置环境变量**
```bash
export GEMINI_API_KEY="your-gemini-api-key"
export KLING_API_KEY="your-kling-api-key"
```

4. **启动服务**
```bash
# 生产环境
python -m src.gemini_kling_mcp.server

# 开发环境（带热重载和调试）
./scripts/dev_server.sh --debug --reload
```

### 快速示例

```python
import asyncio
from src.gemini_kling_mcp.tools.workflow.story_video_generator import generate_story_video

async def main():
    # 生成故事视频
    result = await generate_story_video(
        story_theme="勇敢的小兔子在魔法森林中的冒险",
        style="cartoon",
        duration=15,
        output_mode="file"
    )
    
    if result["success"]:
        print(f"视频生成成功: {result['video_url']}")
        print(f"故事脚本: {result['story_script']}")
        print(f"场景图像: {len(result['scene_images'])} 张")
    else:
        print(f"生成失败: {result['error']}")

asyncio.run(main())
```

## 📖 使用指南

### 基础使用

#### 文本生成
```python
from src.gemini_kling_mcp.tools.text_generation import generate_text

result = await generate_text(
    prompt="写一个关于人工智能的小故事",
    max_tokens=500,
    temperature=0.7
)
```

#### 图像生成
```python
from src.gemini_kling_mcp.tools.image_generation import generate_image

result = await generate_image(
    prompt="一只可爱的小猫坐在彩虹上",
    num_images=2,
    aspect_ratio="1:1",
    output_mode="file"
)
```

#### 视频生成
```python
from src.gemini_kling_mcp.tools.kling_video import generate_video

result = await generate_video(
    prompt="小猫在花园里玩耍",
    duration=10,
    aspect_ratio="16:9",
    wait_for_completion=True
)
```

### 高级工作流

#### 故事视频生成
```python
from src.gemini_kling_mcp.tools.workflow.story_video_generator import (
    generate_story_video, generate_story_video_batch
)

# 单个故事视频
result = await generate_story_video(
    story_theme="太空冒险故事",
    style="sci-fi",
    duration=30,
    language="zh",
    output_mode="file"
)

# 批量生成
stories = ["故事1", "故事2", "故事3"]
results = await generate_story_video_batch(
    story_themes=stories,
    concurrent_limit=2,
    style="cartoon"
)
```

#### 自定义工作流
```python
from src.gemini_kling_mcp.workflow.engine import WorkflowEngine
from src.gemini_kling_mcp.workflow.templates import template_library

# 创建工作流引擎
engine = WorkflowEngine()

# 使用预定义模板
template = template_library.get_template("multimedia_content_creation")
workflow_id = await engine.create_workflow(
    config=template.config,
    steps_config=template.steps,
    initial_context={
        "content_type": "educational",
        "target_audience": "children"
    }
)

# 执行工作流
result = await engine.execute_workflow(workflow_id)
```

## 🛠️ 开发

### 开发环境设置
```bash
# 克隆项目
git clone <repository-url>
cd clip_gen

# 设置开发环境
make dev-setup

# 启动开发服务器
make dev
```

### 测试
```bash
# 运行所有测试
make test

# 运行特定类型测试
make test-unit          # 单元测试
make test-integration   # 集成测试
make test-e2e          # 端到端测试
make test-performance  # 性能测试

# 生成覆盖率报告
make coverage
```

### 代码质量
```bash
# 格式化代码
make format

# 代码检查
make lint

# 类型检查
make typecheck

# 综合质量检查
make quality
```

## 📁 项目结构

```
clip_gen/
├── src/gemini_kling_mcp/          # 主要源代码
│   ├── config/                    # 配置管理
│   ├── services/                  # 外部服务集成
│   │   ├── gemini/               # Gemini API服务
│   │   └── kling/                # Kling API服务
│   ├── tools/                    # MCP工具实现
│   ├── workflow/                 # 工作流引擎
│   ├── file_manager/             # 文件管理
│   └── server.py                 # MCP服务器入口
├── tests/                        # 测试代码
│   ├── unit/                     # 单元测试
│   ├── integration/              # 集成测试
│   ├── e2e/                      # 端到端测试
│   ├── performance/              # 性能测试
│   └── utils/                    # 测试工具
├── docs/                         # 文档
├── scripts/                      # 构建和部署脚本
├── examples/                     # 示例代码
└── Makefile                      # 构建配置
```

## 🔧 配置

### 环境变量
| 变量名 | 必需 | 默认值 | 描述 |
|--------|------|--------|------|
| `GEMINI_API_KEY` | 是 | - | Gemini API密钥 |
| `KLING_API_KEY` | 是 | - | Kling API密钥 |
| `GEMINI_BASE_URL` | 否 | `https://gptproto.com` | Gemini API基础URL |
| `KLING_BASE_URL` | 否 | `https://api.minimax.chat` | Kling API基础URL |
| `FILE_TEMP_DIR` | 否 | `/tmp` | 临时文件目录 |
| `LOG_LEVEL` | 否 | `info` | 日志级别 |

### 配置文件
服务支持通过配置文件进行详细配置：

```python
# config.py
from src.gemini_kling_mcp.config import Config, GeminiConfig, KlingConfig

config = Config(
    gemini=GeminiConfig(
        api_key="your-key",
        base_url="https://gptproto.com",
        timeout=30,
        max_retries=3
    ),
    kling=KlingConfig(
        api_key="your-key",
        timeout=300,
        max_retries=3
    )
)
```

## 📊 性能

### 基准测试结果
- **单个故事视频生成**: ~3-5秒
- **图像生成**: ~1-2秒
- **文本生成**: ~0.5-1秒
- **批量处理吞吐量**: ~2-5任务/秒
- **并发支持**: 支持高并发处理

### 性能优化建议
1. 使用批量处理提高吞吐量
2. 合理设置并发限制避免API限流
3. 启用文件缓存减少重复处理
4. 监控内存使用情况
5. 定期清理临时文件

## 🚨 故障排除

### 常见问题

**Q: API密钥错误**
```
错误: Authentication failed
解决: 检查GEMINI_API_KEY和KLING_API_KEY环境变量
```

**Q: 生成超时**
```
错误: Request timeout
解决: 增加timeout配置或检查网络连接
```

**Q: 文件不存在**
```
错误: File not found
解决: 检查FILE_TEMP_DIR权限和磁盘空间
```

**Q: 内存不足**
```
错误: Out of memory
解决: 减少并发数量或增加系统内存
```

### 调试模式
```bash
# 启用详细日志
export LOG_LEVEL=debug

# 启用调试模式
./scripts/dev_server.sh --debug
```

## 🤝 贡献

我们欢迎社区贡献！请查看 [贡献指南](docs/contributing/CONTRIBUTING.md) 了解详情。

### 开发流程
1. Fork 项目
2. 创建特性分支
3. 编写代码和测试
4. 确保所有测试通过
5. 提交Pull Request

### 代码风格
- 遵循 PEP 8 Python 代码规范
- 使用类型注解
- 编写完整的文档字符串
- 保持测试覆盖率 > 80%

## 📄 许可证

本项目采用 MIT 许可证。详情请见 [LICENSE](LICENSE) 文件。

## 🔗 相关链接

- [API 参考文档](docs/api/)
- [使用指南](docs/guides/)
- [架构设计](docs/architecture/)
- [示例项目](examples/)
- [更新日志](CHANGELOG.md)

## 💬 支持

- 🐛 [问题反馈](https://github.com/your-repo/issues)
- 💡 [功能建议](https://github.com/your-repo/discussions)
- 📧 邮件支持: support@example.com

---

**⭐ 如果这个项目对你有帮助，请给我们一个Star！**