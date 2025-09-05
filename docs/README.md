# Gemini Kling MCP 服务文档

欢迎查看 Gemini Kling MCP 服务的完整文档！本文档提供了详细的使用指南、API 参考和最佳实践。

## 📚 文档导航

### 🚀 [快速开始](guides/quick-start.md)
- 安装和配置
- 第一个示例
- 常见问题解答

### 📖 [用户指南](guides/)
- [基础使用指南](guides/basic-usage.md)
- [工作流使用指南](guides/workflow-guide.md)
- [配置管理](guides/configuration.md)
- [批量处理指南](guides/batch-processing.md)
- [错误处理和调试](guides/debugging.md)

### 🔧 [API 参考](api/)
- [MCP 工具 API](api/tools.md)
- [Gemini 服务 API](api/gemini.md)
- [Kling 服务 API](api/kling.md)
- [工作流引擎 API](api/workflow.md)
- [文件管理 API](api/file-manager.md)

### 🏗️ [架构设计](architecture/)
- [系统架构概览](architecture/overview.md)
- [组件设计](architecture/components.md)
- [工作流引擎设计](architecture/workflow-engine.md)
- [数据流和状态管理](architecture/data-flow.md)
- [扩展性设计](architecture/extensibility.md)

### 📦 [部署指南](deployment/)
- [本地部署](deployment/local.md)
- [Docker 部署](deployment/docker.md)
- [云端部署](deployment/cloud.md)
- [监控和日志](deployment/monitoring.md)
- [性能调优](deployment/performance.md)

### 💡 [示例项目](../examples/)
- [基础示例](../examples/basic/)
- [工作流示例](../examples/workflows/)
- [批量处理示例](../examples/batch/)
- [自定义工具示例](../examples/custom-tools/)

### 🧪 [开发者指南](contributing/)
- [贡献指南](contributing/CONTRIBUTING.md)
- [开发环境设置](contributing/development.md)
- [测试指南](contributing/testing.md)
- [代码规范](contributing/coding-standards.md)
- [发布流程](contributing/release-process.md)

### ❓ [故障排除](troubleshooting/)
- [常见问题](troubleshooting/faq.md)
- [错误诊断](troubleshooting/diagnostics.md)
- [性能问题](troubleshooting/performance.md)
- [配置问题](troubleshooting/configuration.md)

## 🔍 搜索和导航提示

### 按功能查找
- **文本生成**: [Gemini API](api/gemini.md#文本生成) | [示例](../examples/basic/text_generation.py)
- **图像生成**: [Gemini API](api/gemini.md#图像生成) | [示例](../examples/basic/image_generation.py)
- **视频生成**: [Kling API](api/kling.md#视频生成) | [示例](../examples/basic/video_generation.py)
- **故事视频**: [工作流指南](guides/workflow-guide.md#故事视频生成) | [示例](../examples/workflows/story_video.py)
- **批量处理**: [批量处理指南](guides/batch-processing.md) | [示例](../examples/batch/)

### 按角色查找
- **初学者**: [快速开始](guides/quick-start.md) → [基础使用](guides/basic-usage.md) → [示例项目](../examples/basic/)
- **开发者**: [API 参考](api/) → [架构设计](architecture/) → [开发者指南](contributing/)
- **运维人员**: [部署指南](deployment/) → [监控指南](deployment/monitoring.md) → [故障排除](troubleshooting/)
- **架构师**: [系统架构](architecture/overview.md) → [组件设计](architecture/components.md) → [扩展性设计](architecture/extensibility.md)

## 📝 文档约定

### 代码示例
所有代码示例都经过测试，并包含完整的运行环境。

### 版本标记
- 🆕 **新功能** - 最新版本添加的功能
- ⚠️ **注意** - 重要的使用注意事项
- 🔧 **配置** - 需要特殊配置的功能
- 🚀 **性能** - 性能相关的建议

### 链接约定
- **内部链接**: 相对路径链接到其他文档
- **外部链接**: 直接链接到外部资源
- **代码链接**: 链接到源代码文件的具体行

## 🔄 文档更新

本文档随代码同步更新。如果发现文档问题或有改进建议：

1. 查看 [已知问题](https://github.com/your-repo/issues?q=label%3Adocumentation)
2. 创建 [文档问题报告](https://github.com/your-repo/issues/new?template=documentation.md)
3. 提交文档改进的 Pull Request

## 📞 获取帮助

- 💬 [讨论区](https://github.com/your-repo/discussions) - 提问和讨论
- 🐛 [问题报告](https://github.com/your-repo/issues) - Bug 报告和功能请求
- 📧 [邮件支持](mailto:support@example.com) - 直接联系支持团队

---

**📖 开始阅读**: 如果你是新用户，建议从 [快速开始指南](guides/quick-start.md) 开始！