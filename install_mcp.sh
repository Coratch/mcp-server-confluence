#!/bin/bash
# ============================================================
# Confluence MCP 一键部署脚本
# 用途：将 confluence-mcp 服务部署到用户本地并注册到 Claude Code
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
NC='\033[0m' # No Color

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; exit 1; }

# ============================================================
# 1. 前置检查
# ============================================================

check_python() {
    local py_cmd=""
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            local ver
            ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
            if [ -n "$ver" ] && python3 -c "
import sys
cur = tuple(map(int, '$ver'.split('.')))
req = tuple(map(int, '$MIN_PYTHON_VERSION'.split('.')))
sys.exit(0 if cur >= req else 1)
" 2>/dev/null; then
                py_cmd="$cmd"
                break
            fi
        fi
    done

    if [ -z "$py_cmd" ]; then
        fail "需要 Python >= $MIN_PYTHON_VERSION，请先安装 Python"
    fi

    PYTHON_CMD="$py_cmd"
    ok "Python: $($PYTHON_CMD --version)"
}

check_git() {
    command -v git &>/dev/null || fail "需要 git，请先安装"
    ok "Git: $(git --version | head -1)"
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
    read -rp "Confluence 地址 [https://wiki.caijj.net]: " input_url
    CONFLUENCE_BASE_URL="${input_url:-https://wiki.caijj.net}"

    # API Token
    while true; do
        read -rp "Personal Access Token (PAT): " CONFLUENCE_API_TOKEN
        if [ -n "$CONFLUENCE_API_TOKEN" ]; then
            break
        fi
        warn "Token 不能为空，请重新输入"
    done

    # Default Space
    read -rp "默认空间 Key (可选，回车跳过): " CONFLUENCE_DEFAULT_SPACE

    echo ""
    info "配置确认："
    echo "  URL:   $CONFLUENCE_BASE_URL"
    echo "  Token: ${CONFLUENCE_API_TOKEN:0:8}********"
    echo "  Space: ${CONFLUENCE_DEFAULT_SPACE:-（未设置）}"
    echo ""
    read -rp "确认以上配置？[Y/n]: " confirm
    if [[ "$confirm" =~ ^[Nn] ]]; then
        info "已取消，请重新运行脚本"
        exit 0
    fi
}

# ============================================================
# 3. 安装项目
# ============================================================

install_project() {
    info "安装 confluence-mcp ..."

    mkdir -p "$INSTALL_DIR"

    # 创建 venv
    if [ ! -d "$VENV_DIR" ]; then
        info "创建虚拟环境 ..."
        "$PYTHON_CMD" -m venv "$VENV_DIR"
    fi

    local pip_cmd="$VENV_DIR/bin/pip"
    "$pip_cmd" install --upgrade pip -q 2>/dev/null

    # 判断是否在项目目录内运行
    if [ -f "./pyproject.toml" ] && grep -q 'name = "confluence-mcp"' ./pyproject.toml 2>/dev/null; then
        info "检测到当前目录为项目源码，使用 editable 模式安装"
        "$pip_cmd" install -e "$(pwd)" -q
    else
        # 克隆 → 安装 → 清理
        info "克隆仓库 ..."
        rm -rf "$CLONE_DIR"
        git clone --depth 1 "$REPO_URL" "$CLONE_DIR"

        info "安装依赖（首次可能较慢）..."
        "$pip_cmd" install "$CLONE_DIR" -q

        info "清理源码 ..."
        rm -rf "$CLONE_DIR"
        ok "源码已清理，仅保留 venv"
    fi

    ok "confluence-mcp 安装完成"
}

# ============================================================
# 4. 注册到 Claude Code
# ============================================================

register_mcp() {
    info "注册 MCP 服务到 Claude Code ..."

    local venv_python="$VENV_DIR/bin/python"

    # 构建 env JSON
    local env_json
    env_json=$(cat <<ENDJSON
{
    "CONFLUENCE_BASE_URL": "$CONFLUENCE_BASE_URL",
    "CONFLUENCE_API_TOKEN": "$CONFLUENCE_API_TOKEN",
    "CONFLUENCE_DEFAULT_SPACE": "${CONFLUENCE_DEFAULT_SPACE:-}",
    "LOG_LEVEL": "INFO"
}
ENDJSON
)

    # 构建 MCP server 配置
    local server_config
    server_config=$(cat <<ENDJSON
{
    "type": "stdio",
    "command": "$venv_python",
    "args": ["-m", "confluence_mcp.server"],
    "env": $env_json
}
ENDJSON
)

    # 更新 ~/.claude.json
    "$venv_python" -c "
import json, sys, os

config_path = os.path.expanduser('$CLAUDE_CONFIG')
server_name = '$MCP_SERVER_NAME'

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
server_config = json.loads('''$server_config''')
config['mcpServers'][server_name] = server_config

with open(config_path, 'w') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

print('done')
" || fail "写入 Claude Code 配置失败"

    ok "MCP 服务已注册到 $CLAUDE_CONFIG"
}

# ============================================================
# 5. 验证
# ============================================================

verify_install() {
    info "验证安装 ..."

    local venv_python="$VENV_DIR/bin/python"

    # 验证模块可导入
    "$venv_python" -c "from confluence_mcp.server import mcp; print('module ok')" 2>/dev/null \
        || fail "模块导入失败，请检查安装"

    ok "模块验证通过"

    # 验证配置文件
    "$venv_python" -c "
import json, os
with open(os.path.expanduser('$CLAUDE_CONFIG')) as f:
    c = json.load(f)
assert 'confluence' in c.get('mcpServers', {}), 'not found'
print('config ok')
" 2>/dev/null || fail "配置验证失败"

    ok "配置验证通过"
}

# ============================================================
# 6. 检查 mermaid-cli（可选）
# ============================================================

check_mermaid() {
    if command -v mmdc &>/dev/null; then
        ok "mermaid-cli 已安装，支持本地渲染 Mermaid 图表"
    else
        warn "mermaid-cli 未安装（可选），如需本地渲染 Mermaid 图表："
        echo "    npm install -g @mermaid-js/mermaid-cli"
    fi
}

# ============================================================
# 主流程
# ============================================================

main() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║   Confluence MCP 一键部署            ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"
    echo ""

    # Step 1: 前置检查
    info "检查环境 ..."
    check_python
    check_git

    # Step 2: 收集配置
    collect_config

    # Step 3: 安装
    install_project

    # Step 4: 注册 MCP
    register_mcp

    # Step 5: 验证
    verify_install

    # Step 6: 可选组件
    check_mermaid

    # 完成
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   部署完成！                          ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
    echo ""
    echo "可用工具："
    echo "  confluence_read_page    - 读取 Confluence 页面"
    echo "  confluence_create_page  - 从 Markdown 创建页面"
    echo "  confluence_update_page  - 更新页面内容"
    echo "  confluence_search_pages - 搜索页面"
    echo ""
    echo "使用方式：重启 Claude Code 后直接对话即可"
    echo "  示例：\"读取 Confluence 页面 416129733\""
    echo ""
    echo -e "安装路径：${CYAN}$INSTALL_DIR${NC}"
    echo -e "虚拟环境：${CYAN}$VENV_DIR${NC}"
    echo -e "配置文件：${CYAN}$CLAUDE_CONFIG${NC}"
    echo ""
}

main "$@"
