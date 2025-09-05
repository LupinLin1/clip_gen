# 示例项目

这个目录包含了 Gemini Kling MCP 服务的各种使用示例，帮助你快速上手和理解系统功能。

## 📁 示例结构

```
examples/
├── README.md                   # 本文件
├── basic/                      # 基础功能示例
│   ├── text_generation.py     # 文本生成示例
│   ├── image_generation.py    # 图像生成示例
│   ├── video_generation.py    # 视频生成示例
│   └── chat_completion.py     # 对话完成示例
├── workflows/                  # 工作流示例
│   ├── story_video.py         # 故事视频生成示例
│   ├── multimedia_content.py  # 多媒体内容创作示例
│   ├── custom_workflow.py     # 自定义工作流示例
│   └── batch_workflow.py      # 批量工作流示例
├── batch/                      # 批量处理示例
│   ├── batch_text.py          # 批量文本生成
│   ├── batch_images.py        # 批量图像生成
│   ├── batch_videos.py        # 批量视频生成
│   └── concurrent_processing.py # 并发处理示例
├── advanced/                   # 高级功能示例
│   ├── custom_tools.py        # 自定义工具示例
│   ├── state_management.py    # 状态管理示例
│   ├── error_handling.py      # 错误处理示例
│   └── performance_optimization.py # 性能优化示例
├── integration/               # 集成示例
│   ├── mcp_client.py         # MCP客户端集成
│   ├── web_api.py            # Web API集成
│   └── database_integration.py # 数据库集成
└── deployment/               # 部署示例
    ├── docker/               # Docker部署示例
    ├── kubernetes/           # Kubernetes部署示例
    └── cloud/               # 云端部署示例
```

## 🚀 快速开始

### 1. 环境准备

确保你已经完成了基本的环境设置：

```bash
# 克隆项目
git clone <repository-url>
cd clip_gen

# 安装依赖
pip install -e .

# 设置环境变量
export GEMINI_API_KEY="your-gemini-api-key"
export KLING_API_KEY="your-kling-api-key"
```

### 2. 运行基础示例

```bash
# 运行文本生成示例
python examples/basic/text_generation.py

# 运行图像生成示例
python examples/basic/image_generation.py

# 运行视频生成示例
python examples/basic/video_generation.py
```

### 3. 尝试工作流示例

```bash
# 运行故事视频生成示例
python examples/workflows/story_video.py

# 运行多媒体内容创作示例
python examples/workflows/multimedia_content.py
```

## 📖 示例分类

### 🔰 基础示例 (basic/)
适合初学者，演示单一功能的使用方法：
- **文本生成**: 使用 Gemini 生成各种类型的文本内容
- **图像生成**: 从文本描述生成图像
- **视频生成**: 使用 Kling 生成视频内容
- **对话完成**: 实现多轮对话功能

### 🔄 工作流示例 (workflows/)
演示复杂的端到端工作流：
- **故事视频生成**: 从故事主题到完整视频的全流程
- **多媒体内容创作**: 综合使用文本、图像、视频生成
- **自定义工作流**: 创建和使用自定义工作流
- **批量工作流**: 大规模批量内容生成

### ⚡ 批量处理示例 (batch/)
展示高效的批量处理技术：
- **批量文本生成**: 并发生成大量文本内容
- **批量图像生成**: 高效处理图像生成任务
- **批量视频生成**: 管理视频生成队列
- **并发处理**: 优化并发性能的最佳实践

### 🎯 高级功能示例 (advanced/)
深入的高级用法和优化技巧：
- **自定义工具**: 扩展系统功能的方法
- **状态管理**: 复杂状态的管理和持久化
- **错误处理**: 健壮的错误处理策略
- **性能优化**: 系统性能调优技术

### 🔗 集成示例 (integration/)
与其他系统的集成方案：
- **MCP客户端**: 如何创建MCP客户端
- **Web API**: 包装为Web服务
- **数据库集成**: 与数据库系统集成

### 🚀 部署示例 (deployment/)
生产环境部署的完整示例：
- **Docker部署**: 容器化部署方案
- **Kubernetes部署**: 微服务架构部署
- **云端部署**: 云平台部署配置

## 💡 使用建议

### 学习路径
1. **新手**: basic/ → workflows/ → batch/
2. **开发者**: advanced/ → integration/ → deployment/
3. **架构师**: integration/ → deployment/ → advanced/

### 最佳实践
- 每个示例都包含详细的注释说明
- 示例代码遵循项目的编码规范
- 包含错误处理和日志记录
- 提供性能优化的建议

### 自定义示例
你可以基于这些示例创建自己的用例：

```python
# 从基础示例开始
from examples.basic.text_generation import generate_text_example

# 修改参数适应你的需求
result = await generate_text_example(
    prompt="你的自定义提示",
    style="你的风格"
)
```

## 🔧 示例配置

大多数示例支持通过环境变量进行配置：

```bash
# 基础配置
export GEMINI_API_KEY="your-key"
export KLING_API_KEY="your-key"

# 输出配置
export OUTPUT_DIR="./output"
export OUTPUT_MODE="file"  # or "base64"

# 性能配置
export CONCURRENT_LIMIT="3"
export TIMEOUT="300"

# 调试配置
export LOG_LEVEL="debug"
export ENABLE_VERBOSE="true"
```

## 🐛 故障排除

### 常见问题

**Q: 示例运行失败**
```bash
# 检查环境变量
echo $GEMINI_API_KEY
echo $KLING_API_KEY

# 检查依赖安装
pip list | grep gemini
```

**Q: 输出文件找不到**
```bash
# 检查输出目录权限
ls -la ./output/

# 检查磁盘空间
df -h
```

**Q: 性能问题**
```bash
# 减少并发数量
export CONCURRENT_LIMIT="1"

# 启用详细日志查看瓶颈
export LOG_LEVEL="debug"
```

## 📞 获取帮助

如果示例运行遇到问题：

1. 查看示例代码中的注释和文档字符串
2. 检查 [故障排除指南](../docs/troubleshooting/)
3. 在 [Issues](https://github.com/your-repo/issues) 中搜索相关问题
4. 创建新的问题报告并标记 `example` 标签

## 🤝 贡献示例

欢迎贡献新的示例！请遵循以下准则：

1. 确保示例代码可以正常运行
2. 添加详细的注释和文档字符串
3. 包含适当的错误处理
4. 更新相关的README文件
5. 提交Pull Request

详情请参阅 [贡献指南](../docs/contributing/CONTRIBUTING.md)。

---

**🎯 开始探索**: 选择一个适合你技能水平的示例开始体验！