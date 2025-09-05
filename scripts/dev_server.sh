#!/bin/bash

# Gemini Kling MCP 开发服务器启动脚本
#
# 这个脚本用于在开发环境中启动MCP服务器，支持热重载和详细日志。
#
# 用法:
#   ./scripts/dev_server.sh [选项]
#
# 选项:
#   -p, --port PORT      指定端口 (默认: 8000)
#   -h, --host HOST      指定主机 (默认: localhost)
#   -d, --debug          启用调试模式
#   -r, --reload         启用自动重载
#   -l, --log-level LEVEL 日志级别 (debug, info, warning, error)
#   --help               显示帮助信息
#
# 环境变量:
#   GEMINI_API_KEY      Gemini API密钥
#   KLING_API_KEY       Kling API密钥
#   GEMINI_BASE_URL     Gemini API基础URL (可选)
#   KLING_BASE_URL      Kling API基础URL (可选)

set -e

# 默认参数
PORT="8000"
HOST="localhost"
DEBUG="false"
RELOAD="false"
LOG_LEVEL="info"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 打印函数
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
Gemini Kling MCP 开发服务器启动脚本

用法: $0 [选项]

选项:
    -p, --port PORT      指定端口 (默认: 8000)
    -h, --host HOST      指定主机 (默认: localhost)  
    -d, --debug          启用调试模式
    -r, --reload         启用自动重载
    -l, --log-level LEVEL 日志级别 (debug, info, warning, error)
    --help               显示帮助信息

环境变量:
    GEMINI_API_KEY      Gemini API密钥 (必需)
    KLING_API_KEY       Kling API密钥 (必需)
    GEMINI_BASE_URL     Gemini API基础URL (可选，默认: https://gptproto.com)
    KLING_BASE_URL      Kling API基础URL (可选，默认: https://api.minimax.chat)

示例:
    $0 --debug --reload
    $0 --port 8080 --log-level debug
    GEMINI_API_KEY=your_key KLING_API_KEY=your_key $0

EOF
}

# 解析命令行参数
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -p|--port)
                PORT="$2"
                shift 2
                ;;
            -h|--host)
                HOST="$2"  
                shift 2
                ;;
            -d|--debug)
                DEBUG="true"
                LOG_LEVEL="debug"
                shift
                ;;
            -r|--reload)
                RELOAD="true"
                shift
                ;;
            -l|--log-level)
                LOG_LEVEL="$2"
                shift 2
                ;;
            --help)
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

# 检查环境
check_environment() {
    print_info "检查开发环境..."
    
    # 检查Python
    if ! command -v python &> /dev/null; then
        print_error "Python 未找到"
        exit 1
    fi
    
    # 检查项目结构
    if [[ ! -f "src/gemini_kling_mcp/__init__.py" ]]; then
        print_error "项目结构不正确，请确保在项目根目录运行此脚本"
        exit 1
    fi
    
    # 检查API密钥
    if [[ -z "$GEMINI_API_KEY" ]]; then
        print_warning "GEMINI_API_KEY 环境变量未设置"
        print_info "你可以这样设置: export GEMINI_API_KEY=your_api_key"
    fi
    
    if [[ -z "$KLING_API_KEY" ]]; then
        print_warning "KLING_API_KEY 环境变量未设置"
        print_info "你可以这样设置: export KLING_API_KEY=your_api_key"
    fi
    
    print_success "环境检查完成"
}

# 设置开发环境
setup_dev_env() {
    print_info "设置开发环境..."
    
    # 设置Python路径
    export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
    
    # 设置默认API URLs如果未提供
    export GEMINI_BASE_URL="${GEMINI_BASE_URL:-https://gptproto.com}"
    export KLING_BASE_URL="${KLING_BASE_URL:-https://api.minimax.chat}"
    
    # 设置日志级别
    export LOG_LEVEL="$LOG_LEVEL"
    
    # 设置调试模式
    if [[ "$DEBUG" == "true" ]]; then
        export DEBUG="true"
        export PYTHONDEVMODE="1"
    fi
    
    # 创建临时目录
    export DEV_TEMP_DIR="/tmp/gemini_kling_mcp_dev"
    mkdir -p "$DEV_TEMP_DIR"
    export FILE_TEMP_DIR="$DEV_TEMP_DIR"
    
    print_success "开发环境设置完成"
}

# 显示服务器信息
show_server_info() {
    print_info "服务器配置:"
    echo "  主机: $HOST"
    echo "  端口: $PORT"
    echo "  调试模式: $DEBUG"
    echo "  自动重载: $RELOAD"
    echo "  日志级别: $LOG_LEVEL"
    echo "  Gemini API URL: ${GEMINI_BASE_URL}"
    echo "  Kling API URL: ${KLING_BASE_URL}"
    echo "  临时目录: $DEV_TEMP_DIR"
    echo
    
    if [[ -n "$GEMINI_API_KEY" ]]; then
        print_success "Gemini API密钥: 已设置"
    else
        print_warning "Gemini API密钥: 未设置"
    fi
    
    if [[ -n "$KLING_API_KEY" ]]; then
        print_success "Kling API密钥: 已设置"
    else
        print_warning "Kling API密钥: 未设置"
    fi
    echo
}

# 启动服务器
start_server() {
    print_info "启动MCP开发服务器..."
    print_info "使用 Ctrl+C 停止服务器"
    echo
    
    # 构建启动命令
    local cmd="python -m src.gemini_kling_mcp.server"
    
    # 添加选项
    cmd="$cmd --host $HOST --port $PORT"
    
    if [[ "$DEBUG" == "true" ]]; then
        cmd="$cmd --debug"
    fi
    
    if [[ "$RELOAD" == "true" ]]; then
        cmd="$cmd --reload"
    fi
    
    cmd="$cmd --log-level $LOG_LEVEL"
    
    print_info "执行命令: $cmd"
    echo
    
    # 执行命令
    exec $cmd
}

# 清理函数
cleanup() {
    print_info "清理开发环境..."
    
    # 清理临时目录
    if [[ -n "$DEV_TEMP_DIR" ]] && [[ -d "$DEV_TEMP_DIR" ]]; then
        rm -rf "$DEV_TEMP_DIR"
    fi
    
    print_success "清理完成"
}

# 信号处理
handle_interrupt() {
    echo
    print_info "收到中断信号，正在停止服务器..."
    cleanup
    exit 0
}

# 主函数
main() {
    print_success "Gemini Kling MCP 开发服务器"
    echo
    
    # 解析参数
    parse_args "$@"
    
    # 设置信号处理
    trap handle_interrupt INT TERM
    trap cleanup EXIT
    
    # 检查和设置环境
    check_environment
    setup_dev_env
    show_server_info
    
    # 启动服务器
    start_server
}

# 执行主函数
main "$@"