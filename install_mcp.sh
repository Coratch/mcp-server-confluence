#!/bin/bash
# ============================================================
# Confluence MCP 一键部署脚本
# 用途：将 confluence-mcp 服务部署到用户本地并注册到 Claude Code
#
# 用法：
#   bash install_mcp.sh              # 安装 / 重新安装
#   bash install_mcp.sh --update     # 更新到最新版本
#   bash install_mcp.sh --uninstall  # 卸载并清理配置
#   bash install_mcp.sh --help       # 查看帮助
# ============================================================

set -euo pipefail

# ---- 常量 ----
REPO_URL="https://github.com/Coratch/mcp-server-confluence.git"
INSTALL_DIR="$HOME/.local/share/confluence-mcp"
VENV_DIR="$INSTALL_DIR/venv"
CLONE_DIR="$INSTALL_DIR/source"
CLAUDE_CONFIG="$HOME/.claude.json"
MCP_SERVER_NAME="confluence"
MIN_PYTHON_VERSION="3.10"

# ---- 颜色 ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m' # No Color

# ---- 日志函数 ----
info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[ OK ]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; exit 1; }
hint()  { echo -e "         ${DIM}$*${NC}"; }
step()  { echo -e "\n${BOLD}── $* ──${NC}"; }

# ---- 辅助函数 ----

# 检测操作系统类型
detect_os() {
    case "$(uname -s)" in
        Darwin*)  echo "macos" ;;
        Linux*)
            if [ -f /etc/os-release ]; then
                . /etc/os-release
                case "$ID" in
                    ubuntu|debian|linuxmint) echo "debian" ;;
                    centos|rhel|fedora|rocky|alma) echo "redhat" ;;
                    arch|manjaro) echo "arch" ;;
                    *) echo "linux" ;;
                esac
            else
                echo "linux"
            fi
            ;;
        MINGW*|MSYS*|CYGWIN*) echo "windows" ;;
        *) echo "unknown" ;;
    esac
}

# 打印安装指引框
print_install_guide() {
    local title="$1"
    shift
    echo ""
    echo -e "  ${YELLOW}┌─ $title ─${NC}"
    for line in "$@"; do
        echo -e "  ${YELLOW}│${NC} $line"
    done
    echo -e "  ${YELLOW}└──────────────────────────────${NC}"
    echo ""
}

# ============================================================
# 1. 前置检查
# ============================================================

check_python() {
    local py_cmd=""
    for cmd in python3.12 python3.11 python3.10 python3 python; do
        if command -v "$cmd" &>/dev/null; then
            local ver
            ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "")
            if [ -n "$ver" ]; then
                local ok_ver
                ok_ver=$("$cmd" -c "
import sys
cur = tuple(map(int, '$ver'.split('.')))
req = tuple(map(int, '$MIN_PYTHON_VERSION'.split('.')))
print('yes' if cur >= req else 'no')
" 2>/dev/null || echo "no")
                if [ "$ok_ver" = "yes" ]; then
                    py_cmd="$cmd"
                    break
                fi
            fi
        fi
    done

    if [ -z "$py_cmd" ]; then
        local os_type
        os_type=$(detect_os)
        echo ""
        warn "未找到 Python >= $MIN_PYTHON_VERSION"
        case "$os_type" in
            macos)
                print_install_guide "macOS 安装 Python" \
                    "方式一（推荐）：使用 Homebrew" \
                    "  ${CYAN}brew install python@3.12${NC}" \
                    "" \
                    "方式二：从官网下载安装包" \
                    "  ${CYAN}https://www.python.org/downloads/${NC}" \
                    "" \
                    "如果没有 Homebrew，先安装：" \
                    "  ${CYAN}/bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"${NC}"
                ;;
            debian)
                print_install_guide "Ubuntu / Debian 安装 Python" \
                    "${CYAN}sudo apt update${NC}" \
                    "${CYAN}sudo apt install -y python3 python3-venv python3-pip${NC}"
                ;;
            redhat)
                print_install_guide "CentOS / RHEL / Fedora 安装 Python" \
                    "${CYAN}sudo dnf install -y python3 python3-pip${NC}" \
                    "或（CentOS 7）：" \
                    "${CYAN}sudo yum install -y python3 python3-pip${NC}"
                ;;
            arch)
                print_install_guide "Arch Linux 安装 Python" \
                    "${CYAN}sudo pacman -S python python-pip${NC}"
                ;;
            windows)
                print_install_guide "Windows 安装 Python" \
                    "方式一：使用 winget" \
                    "  ${CYAN}winget install Python.Python.3.12${NC}" \
                    "" \
                    "方式二：从官网下载" \
                    "  ${CYAN}https://www.python.org/downloads/${NC}" \
                    "  安装时请勾选 'Add Python to PATH'"
                ;;
            *)
                print_install_guide "安装 Python >= $MIN_PYTHON_VERSION" \
                    "请从官方网站下载安装：" \
                    "  ${CYAN}https://www.python.org/downloads/${NC}"
                ;;
        esac
        fail "请安装 Python >= $MIN_PYTHON_VERSION 后重新运行此脚本"
    fi

    PYTHON_CMD="$py_cmd"
    ok "Python: $($PYTHON_CMD --version)"
}

check_python_venv() {
    if ! "$PYTHON_CMD" -c "import venv" &>/dev/null; then
        local os_type
        os_type=$(detect_os)
        warn "Python venv 模块不可用"
        case "$os_type" in
            debian)
                print_install_guide "安装 venv 模块" \
                    "${CYAN}sudo apt install -y python3-venv${NC}"
                ;;
            redhat)
                print_install_guide "安装 venv 模块" \
                    "${CYAN}sudo dnf install -y python3-libs${NC}"
                ;;
            *)
                print_install_guide "安装 venv 模块" \
                    "请确保你的 Python 安装包含 venv 模块" \
                    "通常重新安装完整版 Python 即可解决"
                ;;
        esac
        fail "Python venv 模块缺失，请按上方指引安装后重试"
    fi
    ok "Python venv 模块可用"
}

check_git() {
    if ! command -v git &>/dev/null; then
        local os_type
        os_type=$(detect_os)
        warn "未找到 git"
        case "$os_type" in
            macos)
                print_install_guide "macOS 安装 Git" \
                    "方式一（系统自带，首次使用会提示安装）：" \
                    "  ${CYAN}xcode-select --install${NC}" \
                    "" \
                    "方式二：使用 Homebrew" \
                    "  ${CYAN}brew install git${NC}"
                ;;
            debian)
                print_install_guide "Ubuntu / Debian 安装 Git" \
                    "${CYAN}sudo apt update && sudo apt install -y git${NC}"
                ;;
            redhat)
                print_install_guide "CentOS / RHEL 安装 Git" \
                    "${CYAN}sudo dnf install -y git${NC}"
                ;;
            arch)
                print_install_guide "Arch Linux 安装 Git" \
                    "${CYAN}sudo pacman -S git${NC}"
                ;;
            windows)
                print_install_guide "Windows 安装 Git" \
                    "下载安装：${CYAN}https://git-scm.com/download/win${NC}" \
                    "或使用 winget：${CYAN}winget install Git.Git${NC}"
                ;;
            *)
                print_install_guide "安装 Git" \
                    "请从官网下载安装：${CYAN}https://git-scm.com/downloads${NC}"
                ;;
        esac
        fail "请安装 Git 后重新运行此脚本"
    fi
    ok "Git: $(git --version | head -1)"
}

check_disk_and_permissions() {
    # 检查磁盘空间（至少需要 500MB）
    local available_mb
    if command -v df &>/dev/null; then
        available_mb=$(df -m "$HOME" 2>/dev/null | awk 'NR==2 {print $4}' || echo "")
        if [ -n "$available_mb" ] && [ "$available_mb" -lt 500 ] 2>/dev/null; then
            warn "磁盘剩余空间不足 (${available_mb}MB)，建议至少 500MB"
            print_install_guide "释放磁盘空间" \
                "当前可用：${available_mb}MB" \
                "安装约需：~300MB（Python 虚拟环境 + 依赖包）" \
                "" \
                "查看磁盘使用：${CYAN}df -h $HOME${NC}" \
                "查找大文件：${CYAN}du -sh $HOME/* | sort -rh | head -10${NC}"
            read -rp "是否继续安装？[y/N]: " cont
            if [[ ! "$cont" =~ ^[Yy] ]]; then
                info "已取消"
                exit 0
            fi
        else
            ok "磁盘空间充足 (${available_mb:-未知}MB 可用)"
        fi
    fi

    # 检查 HOME 目录写权限
    if [ ! -w "$HOME" ]; then
        fail "无法写入主目录 $HOME，请检查目录权限"
    fi

    # 检查 .local/share 是否可写（或可创建）
    local parent_dir="$HOME/.local/share"
    if [ -d "$parent_dir" ] && [ ! -w "$parent_dir" ]; then
        fail "无法写入 $parent_dir，请执行：${CYAN}chmod u+w $parent_dir${NC}"
    fi
    ok "目录权限正常"
}

check_existing_install() {
    if [ -d "$VENV_DIR" ]; then
        warn "检测到已有安装：$INSTALL_DIR"
        echo ""
        echo "  选择操作："
        echo "    1) 覆盖安装（重新创建虚拟环境）"
        echo "    2) 保留环境，仅更新配置"
        echo "    3) 取消"
        echo ""
        read -rp "请选择 [1/2/3]: " choice
        case "${choice:-1}" in
            1)
                info "将删除旧安装目录并重新安装"
                rm -rf "$INSTALL_DIR"
                ;;
            2)
                SKIP_INSTALL=true
                info "将跳过安装步骤，仅更新 Confluence 配置"
                ;;
            3)
                info "已取消"
                exit 0
                ;;
            *)
                info "无效选择，默认覆盖安装"
                rm -rf "$INSTALL_DIR"
                ;;
        esac
    fi
}

check_claude_code() {
    if ! command -v claude &>/dev/null; then
        warn "未检测到 Claude Code CLI"
        print_install_guide "安装 Claude Code" \
            "Claude Code 是 Anthropic 官方的 CLI 工具" \
            "" \
            "使用 npm 安装（推荐）：" \
            "  ${CYAN}npm install -g @anthropic-ai/claude-code${NC}" \
            "" \
            "详细文档：" \
            "  ${CYAN}https://docs.anthropic.com/en/docs/claude-code${NC}"
        echo ""
        read -rp "是否继续安装？（安装完成后再安装 Claude Code 也可以）[Y/n]: " cont
        if [[ "$cont" =~ ^[Nn] ]]; then
            info "已取消"
            exit 0
        fi
    else
        ok "Claude Code CLI 已安装"
    fi
}

# ============================================================
# 2. 交互式收集 Confluence 配置
# ============================================================

collect_config() {
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}  Confluence 连接配置${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo ""

    # Base URL
    read -rp "Confluence 地址 [https://wiki.example.net]: " input_url
    CONFLUENCE_BASE_URL="${input_url:-https://wiki.example.net}"

    # 验证 URL 格式
    if [[ ! "$CONFLUENCE_BASE_URL" =~ ^https?:// ]]; then
        warn "URL 格式不正确，自动添加 https:// 前缀"
        CONFLUENCE_BASE_URL="https://$CONFLUENCE_BASE_URL"
    fi
    # 去掉末尾斜杠
    CONFLUENCE_BASE_URL="${CONFLUENCE_BASE_URL%/}"

    # API Token - 带获取指引
    echo ""
    echo -e "  ${DIM}Personal Access Token (PAT) 获取方式：${NC}"
    echo -e "  ${DIM}1. 登录 Confluence → 右上角头像 → 设置${NC}"
    echo -e "  ${DIM}2. 左侧菜单 → 个人访问令牌 (Personal Access Tokens)${NC}"
    echo -e "  ${DIM}3. 点击「创建令牌」，设置名称和有效期${NC}"
    echo -e "  ${DIM}4. 复制生成的 Token（只显示一次）${NC}"
    echo ""
    while true; do
        read -rsp "Personal Access Token (PAT，输入时不会显示): " CONFLUENCE_API_TOKEN
        echo ""  # 换行
        if [ -n "$CONFLUENCE_API_TOKEN" ]; then
            break
        fi
        warn "Token 不能为空，请重新输入"
    done

    # Default Space
    echo ""
    echo -e "  ${DIM}Space Key 是 Confluence 空间的唯一标识，${NC}"
    echo -e "  ${DIM}可在空间首页 URL 中找到，例如 /wiki/spaces/DEV 中的 DEV${NC}"
    echo ""
    read -rp "默认空间 Key (可选，回车跳过): " CONFLUENCE_DEFAULT_SPACE

    echo ""
    info "配置确认："
    echo "  URL:   $CONFLUENCE_BASE_URL"
    echo "  Token: ${CONFLUENCE_API_TOKEN:0:4}****${CONFLUENCE_API_TOKEN: -4}"
    echo "  Space: ${CONFLUENCE_DEFAULT_SPACE:-（未设置）}"
    echo ""
    read -rp "确认以上配置？[Y/n]: " confirm
    if [[ "$confirm" =~ ^[Nn] ]]; then
        info "已取消，请重新运行脚本"
        exit 0
    fi
}

# ============================================================
# 3. 验证 Confluence 连通性
# ============================================================

test_confluence_connection() {
    info "测试 Confluence 连接 ..."

    # 先检查是否有 curl
    if ! command -v curl &>/dev/null; then
        warn "未找到 curl，跳过连通性测试"
        return 0
    fi

    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer $CONFLUENCE_API_TOKEN" \
        --connect-timeout 10 \
        --max-time 15 \
        "$CONFLUENCE_BASE_URL/rest/api/space?limit=1" 2>/dev/null) || true
    # curl 无法连接时会输出 000 并返回非零退出码
    http_code="${http_code:-000}"

    case "$http_code" in
        200)
            ok "Confluence 连接成功"
            ;;
        401|403)
            warn "Token 认证失败 (HTTP $http_code)"
            print_install_guide "请检查" \
                "1. Token 是否正确复制（无多余空格）" \
                "2. Token 是否已过期" \
                "3. Token 是否具有页面读写权限"
            read -rp "是否继续安装？（之后可手动修改配置）[y/N]: " cont
            if [[ ! "$cont" =~ ^[Yy] ]]; then
                info "已取消"
                exit 0
            fi
            ;;
        000)
            warn "无法连接到 $CONFLUENCE_BASE_URL"
            print_install_guide "可能的原因" \
                "1. 网络不通（检查 VPN / 防火墙）" \
                "2. URL 地址不正确" \
                "3. Confluence 服务未运行"
            read -rp "是否继续安装？（之后可手动修改配置）[y/N]: " cont
            if [[ ! "$cont" =~ ^[Yy] ]]; then
                info "已取消"
                exit 0
            fi
            ;;
        *)
            warn "连接返回异常状态码: HTTP $http_code"
            read -rp "是否继续安装？[y/N]: " cont
            if [[ ! "$cont" =~ ^[Yy] ]]; then
                info "已取消"
                exit 0
            fi
            ;;
    esac
}

# ============================================================
# 4. 安装项目
# ============================================================

install_project() {
    info "安装 confluence-mcp ..."

    mkdir -p "$INSTALL_DIR"

    # 创建 venv
    if [ ! -d "$VENV_DIR" ]; then
        info "创建虚拟环境 ..."
        if ! "$PYTHON_CMD" -m venv "$VENV_DIR" 2>/tmp/venv_error.log; then
            local err
            err=$(cat /tmp/venv_error.log 2>/dev/null || echo "未知错误")
            warn "创建虚拟环境失败: $err"
            print_install_guide "排查建议" \
                "1. 确认 Python venv 模块已安装（见上方检测结果）" \
                "2. 确认磁盘空间充足：${CYAN}df -h $HOME${NC}" \
                "3. 确认目录权限正常：${CYAN}ls -la $INSTALL_DIR${NC}" \
                "4. 尝试手动创建：${CYAN}$PYTHON_CMD -m venv $VENV_DIR${NC}"
            rm -f /tmp/venv_error.log
            fail "虚拟环境创建失败"
        fi
        rm -f /tmp/venv_error.log
    else
        info "虚拟环境已存在，复用"
    fi

    local pip_cmd="$VENV_DIR/bin/pip"
    info "升级 pip ..."
    "$pip_cmd" install --upgrade pip -q 2>/dev/null || warn "pip 升级失败，继续使用现有版本"

    # 判断是否在项目目录内运行
    if [ -f "./pyproject.toml" ] && grep -q 'name = "confluence-mcp"' ./pyproject.toml 2>/dev/null; then
        info "检测到当前目录为项目源码，使用 editable 模式安装"
        if ! "$pip_cmd" install -e "$(pwd)" -q 2>/tmp/pip_error.log; then
            local err
            err=$(tail -5 /tmp/pip_error.log 2>/dev/null || echo "未知错误")
            warn "pip install 失败"
            echo -e "  ${DIM}错误信息：$err${NC}"
            print_install_guide "排查建议" \
                "1. 检查网络连接（pip 需要从 PyPI 下载依赖）" \
                "2. 如果在公司内网，配置 pip 镜像源：" \
                "   ${CYAN}$pip_cmd install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple${NC}" \
                "3. 查看完整错误日志：${CYAN}cat /tmp/pip_error.log${NC}"
            rm -f /tmp/pip_error.log
            fail "依赖安装失败"
        fi
        rm -f /tmp/pip_error.log
    else
        # 克隆 → 安装 → 清理
        info "克隆仓库 ..."
        rm -rf "$CLONE_DIR"
        if ! git clone --depth 1 "$REPO_URL" "$CLONE_DIR" 2>/tmp/git_error.log; then
            local err
            err=$(tail -3 /tmp/git_error.log 2>/dev/null || echo "未知错误")
            warn "Git 克隆失败"
            echo -e "  ${DIM}错误信息：$err${NC}"
            print_install_guide "排查建议" \
                "1. 检查网络连接和代理设置" \
                "2. 如果在公司内网，可能需要配置 Git 代理：" \
                "   ${CYAN}git config --global http.proxy http://proxy:port${NC}" \
                "3. 也可以手动克隆后在项目目录内运行此脚本：" \
                "   ${CYAN}git clone $REPO_URL${NC}" \
                "   ${CYAN}cd mcp-server-confluence && bash install_mcp.sh${NC}" \
                "4. 查看完整错误：${CYAN}cat /tmp/git_error.log${NC}"
            rm -f /tmp/git_error.log
            fail "仓库克隆失败"
        fi
        rm -f /tmp/git_error.log

        info "安装依赖（首次可能较慢）..."
        if ! "$pip_cmd" install "$CLONE_DIR" -q 2>/tmp/pip_error.log; then
            local err
            err=$(tail -5 /tmp/pip_error.log 2>/dev/null || echo "未知错误")
            warn "依赖安装失败"
            echo -e "  ${DIM}错误信息：$err${NC}"
            print_install_guide "排查建议" \
                "1. 检查网络（需从 PyPI 下载依赖包）" \
                "2. 尝试使用国内镜像：" \
                "   ${CYAN}$pip_cmd install $CLONE_DIR -i https://pypi.tuna.tsinghua.edu.cn/simple${NC}" \
                "3. 查看完整错误：${CYAN}cat /tmp/pip_error.log${NC}"
            rm -f /tmp/pip_error.log
            fail "依赖安装失败"
        fi
        rm -f /tmp/pip_error.log

        info "清理源码 ..."
        rm -rf "$CLONE_DIR"
        ok "源码已清理，仅保留 venv"
    fi

    ok "confluence-mcp 安装完成"
}

# ============================================================
# 5. 注册到 Claude Code
# ============================================================

register_mcp() {
    info "注册 MCP 服务到 Claude Code ..."

    local venv_python="$VENV_DIR/bin/python"

    # 使用 Python 安全构建 JSON 并写入配置（避免 Token 中特殊字符导致 JSON 注入）
    if ! _INSTALL_BASE_URL="$CONFLUENCE_BASE_URL" \
         _INSTALL_API_TOKEN="$CONFLUENCE_API_TOKEN" \
         _INSTALL_DEFAULT_SPACE="${CONFLUENCE_DEFAULT_SPACE:-}" \
         "$venv_python" -c "
import json, sys, os

config_path = os.path.expanduser('$CLAUDE_CONFIG')
server_name = '$MCP_SERVER_NAME'
venv_python = '$venv_python'

# 从环境变量读取敏感值（避免命令行中暴露）
base_url = os.environ['_INSTALL_BASE_URL']
api_token = os.environ['_INSTALL_API_TOKEN']
default_space = os.environ.get('_INSTALL_DEFAULT_SPACE', '')

# 读取或初始化配置
if os.path.exists(config_path):
    with open(config_path, 'r') as f:
        config = json.load(f)
else:
    config = {}

if 'mcpServers' not in config:
    config['mcpServers'] = {}

# 清理旧的错误嵌套结构 (mcpServers.servers.confluence)
if 'servers' in config['mcpServers']:
    nested = config['mcpServers']['servers']
    if isinstance(nested, dict) and server_name in nested:
        del nested[server_name]
    if not nested:
        del config['mcpServers']['servers']

# 写入正确位置: mcpServers.confluence
config['mcpServers'][server_name] = {
    'type': 'stdio',
    'command': venv_python,
    'args': ['-m', 'confluence_mcp.server'],
    'env': {
        'CONFLUENCE_BASE_URL': base_url,
        'CONFLUENCE_API_TOKEN': api_token,
        'CONFLUENCE_DEFAULT_SPACE': default_space,
        'LOG_LEVEL': 'INFO'
    }
}

with open(config_path, 'w') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

print('done')
" 2>/tmp/reg_error.log; then
        local err
        err=$(cat /tmp/reg_error.log 2>/dev/null || echo "未知错误")
        warn "写入配置失败: $err"
        print_install_guide "手动配置方法" \
            "将以下内容添加到 ${CYAN}$CLAUDE_CONFIG${NC} 的 mcpServers 中：" \
            "" \
            "  \"$MCP_SERVER_NAME\": {" \
            "    \"type\": \"stdio\"," \
            "    \"command\": \"$venv_python\"," \
            "    \"args\": [\"-m\", \"confluence_mcp.server\"]," \
            "    \"env\": {" \
            "      \"CONFLUENCE_BASE_URL\": \"$CONFLUENCE_BASE_URL\"," \
            "      \"CONFLUENCE_API_TOKEN\": \"<your-token>\"," \
            "      \"CONFLUENCE_DEFAULT_SPACE\": \"${CONFLUENCE_DEFAULT_SPACE:-}\"" \
            "    }" \
            "  }"
        rm -f /tmp/reg_error.log
        fail "MCP 注册失败"
    fi
    rm -f /tmp/reg_error.log

    ok "MCP 服务已注册到 $CLAUDE_CONFIG"
}

# ============================================================
# 6. 验证
# ============================================================

verify_install() {
    info "验证安装 ..."

    local venv_python="$VENV_DIR/bin/python"

    # 验证模块可导入（仅检查包安装，不触发配置加载）
    if ! "$venv_python" -c "import confluence_mcp; print('module ok')" 2>/dev/null; then
        warn "模块导入失败"
        print_install_guide "排查建议" \
            "1. 尝试重新安装：${CYAN}bash $0${NC}" \
            "2. 手动检查：${CYAN}$venv_python -c \"import confluence_mcp\"${NC}" \
            "3. 查看已安装包：${CYAN}$VENV_DIR/bin/pip list | grep confluence${NC}"
        fail "模块验证失败"
    fi
    ok "模块验证通过"

    # 验证配置文件
    if ! "$venv_python" -c "
import json, os
with open(os.path.expanduser('$CLAUDE_CONFIG')) as f:
    c = json.load(f)
assert 'confluence' in c.get('mcpServers', {}), 'not found'
print('config ok')
" 2>/dev/null; then
        warn "配置验证失败"
        print_install_guide "排查建议" \
            "检查配置文件格式是否正确：" \
            "  ${CYAN}cat $CLAUDE_CONFIG | python3 -m json.tool${NC}"
        fail "配置验证失败"
    fi
    ok "配置验证通过"
}

# ============================================================
# 7. 检查 mermaid-cli（可选）
# ============================================================

check_mermaid() {
    if command -v mmdc &>/dev/null; then
        ok "mermaid-cli 已安装，支持本地渲染 Mermaid 图表"
        return
    fi

    warn "mermaid-cli 未安装（可选功能，不影响核心使用）"
    echo -e "  ${DIM}mermaid-cli 用于将 Mermaid 图表渲染为图片上传到 Confluence${NC}"
    echo ""

    if command -v npm &>/dev/null; then
        echo -e "  已检测到 npm，安装命令："
        echo -e "  ${CYAN}npm install -g @mermaid-js/mermaid-cli${NC}"
    elif command -v node &>/dev/null; then
        warn "检测到 Node.js 但未找到 npm"
        echo -e "  请先安装 npm，再安装 mermaid-cli"
    else
        echo -e "  mermaid-cli 需要 Node.js 环境："
        local os_type
        os_type=$(detect_os)
        case "$os_type" in
            macos)
                echo -e "  ${CYAN}brew install node${NC}"
                ;;
            debian)
                echo -e "  ${CYAN}sudo apt install -y nodejs npm${NC}"
                ;;
            redhat)
                echo -e "  ${CYAN}sudo dnf install -y nodejs npm${NC}"
                ;;
            *)
                echo -e "  ${CYAN}https://nodejs.org/en/download/${NC}"
                ;;
        esac
        echo -e "  安装 Node.js 后再运行："
        echo -e "  ${CYAN}npm install -g @mermaid-js/mermaid-cli${NC}"
    fi
    echo ""
}

# ============================================================
# 卸载
# ============================================================

do_uninstall() {
    echo ""
    echo -e "${YELLOW}╔══════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║   Confluence MCP 卸载                ║${NC}"
    echo -e "${YELLOW}╚══════════════════════════════════════╝${NC}"
    echo ""

    echo "将执行以下操作："
    echo "  1. 删除安装目录: $INSTALL_DIR"
    echo "  2. 从 $CLAUDE_CONFIG 中移除 MCP 配置"
    echo ""
    read -rp "确认卸载？[y/N]: " confirm
    if [[ ! "$confirm" =~ ^[Yy] ]]; then
        info "已取消"
        exit 0
    fi

    # 删除安装目录
    if [ -d "$INSTALL_DIR" ]; then
        rm -rf "$INSTALL_DIR"
        ok "已删除 $INSTALL_DIR"
    else
        info "安装目录不存在，跳过"
    fi

    # 清理 Claude 配置
    if [ -f "$CLAUDE_CONFIG" ]; then
        if command -v python3 &>/dev/null; then
            python3 -c "
import json, os
config_path = os.path.expanduser('$CLAUDE_CONFIG')
with open(config_path, 'r') as f:
    config = json.load(f)
if 'mcpServers' in config and '$MCP_SERVER_NAME' in config['mcpServers']:
    del config['mcpServers']['$MCP_SERVER_NAME']
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print('已从配置中移除 MCP 服务')
else:
    print('配置中未找到 MCP 服务，跳过')
" 2>/dev/null || warn "自动清理配置失败，请手动编辑 $CLAUDE_CONFIG 删除 \"$MCP_SERVER_NAME\" 条目"
        else
            warn "未找到 Python，请手动编辑 $CLAUDE_CONFIG 删除 \"$MCP_SERVER_NAME\" 条目"
        fi
    fi

    echo ""
    ok "卸载完成！重启 Claude Code 后生效"
    echo ""
    exit 0
}

# ============================================================
# 更新
# ============================================================

do_update() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║   Confluence MCP 更新                ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"
    echo ""

    if [ ! -d "$VENV_DIR" ]; then
        warn "未检测到已安装的 confluence-mcp"
        info "请先运行完整安装：bash $0"
        exit 1
    fi

    local pip_cmd="$VENV_DIR/bin/pip"

    # 判断是否在项目源码目录
    if [ -f "./pyproject.toml" ] && grep -q 'name = "confluence-mcp"' ./pyproject.toml 2>/dev/null; then
        info "检测到项目源码目录，更新 editable 安装 ..."
        "$pip_cmd" install -e "$(pwd)" --upgrade || fail "更新失败"
    else
        info "从远程仓库更新 ..."
        rm -rf "$CLONE_DIR"
        git clone --depth 1 "$REPO_URL" "$CLONE_DIR" || fail "克隆失败，请检查网络"
        "$pip_cmd" install "$CLONE_DIR" --upgrade || fail "更新失败"
        rm -rf "$CLONE_DIR"
    fi

    ok "更新完成！重启 Claude Code 后生效"
    echo ""
    exit 0
}

# ============================================================
# 帮助
# ============================================================

show_help() {
    echo ""
    echo -e "${BOLD}Confluence MCP 部署脚本${NC}"
    echo ""
    echo "用法："
    echo "  bash install_mcp.sh              安装或重新安装"
    echo "  bash install_mcp.sh --update     更新到最新版本"
    echo "  bash install_mcp.sh --uninstall  卸载并清理配置"
    echo "  bash install_mcp.sh --help       显示此帮助信息"
    echo ""
    echo "安装路径：$INSTALL_DIR"
    echo "配置文件：$CLAUDE_CONFIG"
    echo ""
    echo "环境要求："
    echo "  - Python >= $MIN_PYTHON_VERSION (含 venv 模块)"
    echo "  - Git"
    echo "  - Claude Code CLI（可选，安装后再装也行）"
    echo "  - Node.js + npm（可选，仅 Mermaid 图表渲染需要）"
    echo ""
    exit 0
}

# ============================================================
# 主流程
# ============================================================

main() {
    # 处理命令行参数
    case "${1:-}" in
        --help|-h)
            show_help
            ;;
        --uninstall|--remove)
            do_uninstall
            ;;
        --update|--upgrade)
            do_update
            ;;
    esac

    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║   Confluence MCP 一键部署            ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"
    echo ""

    # Step 1: 前置检查
    step "Step 1/7: 环境检查"
    check_python
    check_python_venv
    check_git
    check_disk_and_permissions
    check_claude_code
    SKIP_INSTALL=false
    check_existing_install

    # Step 2: 收集配置
    step "Step 2/7: Confluence 配置"
    collect_config

    # Step 3: 验证连通性
    step "Step 3/7: 连通性测试"
    test_confluence_connection

    # Step 4: 安装
    step "Step 4/7: 安装项目"
    if [ "$SKIP_INSTALL" = true ]; then
        info "跳过安装步骤（保留现有环境）"
    else
        install_project
    fi

    # Step 5: 注册 MCP
    step "Step 5/7: 注册服务"
    register_mcp

    # Step 6: 验证 + 可选组件
    step "Step 6/7: 验证安装"
    verify_install
    echo ""

    # Step 7: 可选组件
    step "Step 7/7: 可选组件"
    check_mermaid

    # 完成
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   部署完成！                                  ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BOLD}可用工具：${NC}"
    echo "  confluence_read_page    - 读取 Confluence 页面"
    echo "  confluence_create_page  - 从 Markdown 创建页面"
    echo "  confluence_update_page  - 更新页面内容"
    echo "  confluence_search_pages - 搜索页面"
    echo ""
    echo -e "${BOLD}使用方式：${NC}重启 Claude Code 后直接对话即可"
    echo "  示例：\"读取 Confluence 页面 416129733\""
    echo ""
    echo -e "${BOLD}管理命令：${NC}"
    echo "  更新：bash $0 --update"
    echo "  卸载：bash $0 --uninstall"
    echo "  帮助：bash $0 --help"
    echo ""
    echo -e "安装路径：${CYAN}$INSTALL_DIR${NC}"
    echo -e "虚拟环境：${CYAN}$VENV_DIR${NC}"
    echo -e "配置文件：${CYAN}$CLAUDE_CONFIG${NC}"
    echo ""
}

main "$@"
