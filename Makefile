# Gemini Kling MCP 服务项目 Makefile

.PHONY: help install test test-unit test-integration test-e2e test-performance lint typecheck format clean build dev docs coverage

# 默认目标
help:
	@echo "可用的命令:"
	@echo "  install          - 安装项目依赖"
	@echo "  test             - 运行所有测试"
	@echo "  test-unit        - 运行单元测试"
	@echo "  test-integration - 运行集成测试"
	@echo "  test-e2e         - 运行端到端测试"
	@echo "  test-performance - 运行性能测试"
	@echo "  lint             - 代码检查"
	@echo "  typecheck        - 类型检查"
	@echo "  format           - 格式化代码"
	@echo "  clean            - 清理临时文件"
	@echo "  build            - 构建项目"
	@echo "  dev              - 开发模式运行"
	@echo "  docs             - 生成文档"
	@echo "  coverage         - 生成测试覆盖率报告"

# 安装依赖
install:
	@echo "安装项目依赖..."
	pip install -e .
	pip install -r requirements-dev.txt

# 运行所有测试
test:
	@echo "运行所有测试..."
	python -m pytest tests/ -v --tb=short

# 运行单元测试
test-unit:
	@echo "运行单元测试..."
	python -m pytest tests/unit/ -v --tb=short -m "unit"

# 运行集成测试
test-integration:
	@echo "运行集成测试..."
	python -m pytest tests/integration/ -v --tb=short -m "integration"

# 运行端到端测试
test-e2e:
	@echo "运行端到端测试..."
	python -m pytest tests/e2e/ -v --tb=short -m "e2e"

# 运行性能测试
test-performance:
	@echo "运行性能测试..."
	python -m pytest tests/performance/ -v --tb=short -m "performance" -s

# 代码检查
lint:
	@echo "执行代码检查..."
	python -m flake8 src/ tests/ --max-line-length=100 --ignore=E203,W503
	python -m pylint src/gemini_kling_mcp/ --disable=C0114,C0115,C0116

# 类型检查
typecheck:
	@echo "执行类型检查..."
	python -m mypy src/gemini_kling_mcp/ --ignore-missing-imports --strict-optional

# 格式化代码
format:
	@echo "格式化代码..."
	python -m black src/ tests/ --line-length=100
	python -m isort src/ tests/

# 清理临时文件
clean:
	@echo "清理临时文件..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf htmlcov/
	rm -f .coverage
	rm -f coverage.xml

# 构建项目
build: clean lint typecheck
	@echo "构建项目..."
	python -m build

# 开发模式运行
dev:
	@echo "开发模式运行MCP服务器..."
	python -m src.gemini_kling_mcp.server

# 生成文档
docs:
	@echo "生成项目文档..."
	sphinx-build -b html docs/ docs/_build/

# 测试覆盖率
coverage:
	@echo "生成测试覆盖率报告..."
	python -m pytest tests/ --cov=src/gemini_kling_mcp --cov-report=html --cov-report=xml --cov-report=term
	@echo "覆盖率报告已生成到 htmlcov/ 目录"

# 快速测试（不包括性能测试）
test-quick:
	@echo "运行快速测试（排除性能测试）..."
	python -m pytest tests/ -v --tb=short -m "not performance"

# 运行特定测试文件
test-file:
	@echo "运行特定测试文件: $(FILE)"
	python -m pytest $(FILE) -v --tb=short

# 运行冒烟测试
test-smoke:
	@echo "运行冒烟测试..."
	python -m pytest tests/unit/test_gemini_service.py::TestGeminiTextService::test_generate_text_success -v
	python -m pytest tests/integration/test_story_video_workflow.py::TestStoryVideoWorkflow::test_generate_story_video_success -v

# 代码质量检查（综合）
quality: format lint typecheck
	@echo "代码质量检查完成"

# 完整的CI流程
ci: install quality test-quick coverage
	@echo "CI流程执行完成"

# 发布前检查
pre-release: clean quality test coverage build
	@echo "发布前检查完成"

# 开发环境设置
dev-setup: install
	@echo "开发环境设置完成"
	@echo "现在可以运行: make dev 启动开发服务器"
	@echo "或者运行: make test 执行测试"