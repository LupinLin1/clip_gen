#!/bin/bash

# Gemini Kling MCP 测试执行脚本
# 
# 这个脚本提供了灵活的测试执行选项，支持不同类型的测试和输出格式。
# 
# 用法:
#   ./scripts/run_tests.sh [选项]
#
# 选项:
#   -u, --unit           只运行单元测试
#   -i, --integration    只运行集成测试
#   -e, --e2e           只运行端到端测试
#   -p, --performance   只运行性能测试
#   -a, --all           运行所有测试 (默认)
#   -q, --quick         快速测试 (排除性能测试)
#   -f, --file FILE     运行指定测试文件
#   -v, --verbose       详细输出
#   -c, --coverage      生成覆盖率报告
#   -h, --help          显示帮助信息
#
# 示例:
#   ./scripts/run_tests.sh --unit --verbose
#   ./scripts/run_tests.sh --coverage
#   ./scripts/run_tests.sh --file tests/unit/test_gemini_service.py

set -e  # 遇到错误时退出

# 默认参数
TEST_TYPE="all"
VERBOSE=""
COVERAGE=""
SPECIFIC_FILE=""
QUICK_MODE=""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印彩色消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示帮助信息
show_help() {
    cat << EOF
Gemini Kling MCP 测试执行脚本

用法: $0 [选项]

选项:
    -u, --unit           只运行单元测试
    -i, --integration    只运行集成测试
    -e, --e2e           只运行端到端测试
    -p, --performance   只运行性能测试
    -a, --all           运行所有测试 (默认)
    -q, --quick         快速测试 (排除性能测试)
    -f, --file FILE     运行指定测试文件
    -v, --verbose       详细输出
    -c, --coverage      生成覆盖率报告
    -h, --help          显示帮助信息

示例:
    $0 --unit --verbose
    $0 --coverage
    $0 --file tests/unit/test_gemini_service.py
    $0 --quick --coverage

EOF
}

# 解析命令行参数
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -u|--unit)
                TEST_TYPE="unit"
                shift
                ;;
            -i|--integration)
                TEST_TYPE="integration"
                shift
                ;;
            -e|--e2e)
                TEST_TYPE="e2e"
                shift
                ;;
            -p|--performance)
                TEST_TYPE="performance"
                shift
                ;;
            -a|--all)
                TEST_TYPE="all"
                shift
                ;;
            -q|--quick)
                QUICK_MODE="true"
                shift
                ;;
            -f|--file)
                SPECIFIC_FILE="$2"
                TEST_TYPE="file"
                shift 2
                ;;
            -v|--verbose)
                VERBOSE="-v"
                shift
                ;;
            -c|--coverage)
                COVERAGE="true"
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                print_error "未知选项: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# 检查依赖
check_dependencies() {
    print_info "检查依赖..."
    
    if ! command -v python &> /dev/null; then
        print_error "Python 未找到，请确保已安装 Python"
        exit 1
    fi
    
    if ! python -c "import pytest" &> /dev/null; then
        print_error "pytest 未找到，请运行: pip install pytest"
        exit 1
    fi
    
    print_success "依赖检查通过"
}

# 设置测试环境
setup_test_env() {
    print_info "设置测试环境..."
    
    # 设置Python路径
    export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
    
    # 创建临时目录
    export TEST_TEMP_DIR="/tmp/gemini_kling_mcp_test_$$"
    mkdir -p "$TEST_TEMP_DIR"
    
    # 设置测试环境变量
    export GEMINI_API_KEY="test-gemini-key"
    export KLING_API_KEY="test-kling-key"
    export FILE_TEMP_DIR="$TEST_TEMP_DIR"
    
    print_success "测试环境设置完成"
}

# 构建pytest命令
build_pytest_cmd() {
    local cmd="python -m pytest"
    
    # 添加详细输出
    if [[ -n "$VERBOSE" ]]; then
        cmd="$cmd -v"
    fi
    
    # 添加覆盖率
    if [[ "$COVERAGE" == "true" ]]; then
        cmd="$cmd --cov=src/gemini_kling_mcp --cov-report=html --cov-report=xml --cov-report=term"
    fi
    
    # 根据测试类型选择路径和标记
    case $TEST_TYPE in
        "unit")
            cmd="$cmd tests/unit/ -m unit"
            ;;
        "integration")
            cmd="$cmd tests/integration/ -m integration"
            ;;
        "e2e")
            cmd="$cmd tests/e2e/ -m e2e"
            ;;
        "performance")
            cmd="$cmd tests/performance/ -m performance -s"
            ;;
        "file")
            cmd="$cmd $SPECIFIC_FILE"
            ;;
        "all")
            cmd="$cmd tests/"
            ;;
    esac
    
    # 快速模式排除性能测试
    if [[ "$QUICK_MODE" == "true" ]]; then
        cmd="$cmd -m 'not performance'"
    fi
    
    # 添加其他选项
    cmd="$cmd --tb=short"
    
    echo "$cmd"
}

# 运行测试
run_tests() {
    local pytest_cmd
    pytest_cmd=$(build_pytest_cmd)
    
    print_info "运行测试: $TEST_TYPE"
    print_info "执行命令: $pytest_cmd"
    
    # 执行测试
    if eval "$pytest_cmd"; then
        print_success "测试执行成功"
        return 0
    else
        print_error "测试执行失败"
        return 1
    fi
}

# 清理测试环境
cleanup_test_env() {
    print_info "清理测试环境..."
    
    # 清理临时目录
    if [[ -n "$TEST_TEMP_DIR" ]] && [[ -d "$TEST_TEMP_DIR" ]]; then
        rm -rf "$TEST_TEMP_DIR"
    fi
    
    # 清理Python缓存
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    
    print_success "清理完成"
}

# 生成测试报告
generate_report() {
    if [[ "$COVERAGE" == "true" ]]; then
        print_info "生成测试报告..."
        
        if [[ -f "htmlcov/index.html" ]]; then
            print_success "覆盖率报告已生成: htmlcov/index.html"
            
            # 如果是macOS，尝试打开报告
            if [[ "$OSTYPE" == "darwin"* ]]; then
                print_info "在浏览器中打开覆盖率报告..."
                open htmlcov/index.html 2>/dev/null || true
            fi
        fi
        
        if [[ -f "coverage.xml" ]]; then
            print_success "XML覆盖率报告已生成: coverage.xml"
        fi
    fi
}

# 主函数
main() {
    print_info "Gemini Kling MCP 测试执行脚本"
    echo
    
    # 解析参数
    parse_args "$@"
    
    # 设置错误处理
    trap cleanup_test_env EXIT
    
    # 执行步骤
    check_dependencies
    setup_test_env
    
    # 运行测试
    if run_tests; then
        generate_report
        print_success "所有操作完成"
        exit 0
    else
        print_error "测试失败"
        exit 1
    fi
}

# 执行主函数
main "$@"