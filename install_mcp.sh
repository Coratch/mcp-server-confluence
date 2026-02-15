#!/bin/bash
# Confluence MCP 安装脚本

echo "=================================="
echo "Confluence MCP 安装向导"
echo "=================================="
echo ""

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "❌ 错误: 未找到 .env 文件"
    echo "请先创建 .env 文件并配置以下变量："
    echo "  CONFLUENCE_BASE_URL=https://confluence.example.com"
    echo "  CONFLUENCE_API_TOKEN=your_token_here"
    echo "  CONFLUENCE_DEFAULT_SPACE=~your_username"
    exit 1
fi

# 读取环境变量
source .env

# 检查必需的环境变量
if [ -z "$CONFLUENCE_API_TOKEN" ]; then
    echo "❌ 错误: CONFLUENCE_API_TOKEN 未设置"
    echo "请在 .env 文件中设置 CONFLUENCE_API_TOKEN"
    exit 1
fi

echo "✅ 环境变量检查通过"
echo ""

# 检查 Python 包是否安装
echo "检查 Python 包..."
if ! python -c "import confluence_mcp" 2>/dev/null; then
    echo "❌ confluence_mcp 未安装"
    echo "正在安装..."
    pip install -e .
    if [ $? -ne 0 ]; then
        echo "❌ 安装失败"
        exit 1
    fi
fi
echo "✅ Python 包已安装"
echo ""

# 检查 mermaid-cli（可选）
echo "检查 mermaid-cli（可选）..."
if command -v mmdc &> /dev/null; then
    echo "✅ mermaid-cli 已安装"
    MERMAID_AVAILABLE="true"
else
    echo "⚠️  mermaid-cli 未安装（可选）"
    echo "   如需本地渲染 Mermaid 图表，请运行："
    echo "   npm install -g @mermaid-js/mermaid-cli"
    MERMAID_AVAILABLE="false"
fi
echo ""

# 添加到 Claude Code
echo "添加 Confluence MCP 到 Claude Code..."

# 使用 claude mcp add 命令
claude mcp remove confluence 2>/dev/null

# 创建临时配置文件
cat > /tmp/confluence_mcp.json << EOF
{
  "type": "stdio",
  "command": "python",
  "args": ["-m", "confluence_mcp.server"],
  "env": {
    "CONFLUENCE_BASE_URL": "${CONFLUENCE_BASE_URL}",
    "CONFLUENCE_API_TOKEN": "${CONFLUENCE_API_TOKEN}",
    "CONFLUENCE_DEFAULT_SPACE": "${CONFLUENCE_DEFAULT_SPACE:-~your_username}",
    "LOG_LEVEL": "INFO"
  }
}
EOF

# 手动编辑 .claude.json
CLAUDE_CONFIG="$HOME/.claude.json"

if [ ! -f "$CLAUDE_CONFIG" ]; then
    echo "❌ 错误: 未找到 Claude Code 配置文件"
    echo "配置文件路径: $CLAUDE_CONFIG"
    exit 1
fi

# 使用 Python 更新配置
python3 << 'PYTHON_SCRIPT'
import json
import os

config_path = os.path.expanduser("~/.claude.json")
temp_config_path = "/tmp/confluence_mcp.json"

# 读取现有配置
with open(config_path, 'r') as f:
    claude_config = json.load(f)

# 读取 Confluence MCP 配置
with open(temp_config_path, 'r') as f:
    confluence_config = json.load(f)

# 更新配置
if 'mcpServers' not in claude_config:
    claude_config['mcpServers'] = {}

if 'servers' not in claude_config['mcpServers']:
    claude_config['mcpServers']['servers'] = {}

claude_config['mcpServers']['servers']['confluence'] = confluence_config

# 保存配置
with open(config_path, 'w') as f:
    json.dump(claude_config, f, indent=2)

print("✅ 配置已更新")
PYTHON_SCRIPT

if [ $? -ne 0 ]; then
    echo "❌ 配置更新失败"
    echo ""
    echo "请手动编辑 ~/.claude.json，在 mcpServers.servers 中添加："
    cat /tmp/confluence_mcp.json
    exit 1
fi

echo "✅ Confluence MCP 已添加到 Claude Code"
echo ""

# 测试连接
echo "测试 MCP 服务器连接..."
claude mcp list | grep confluence

echo ""
echo "=================================="
echo "✅ 安装完成！"
echo "=================================="
echo ""
echo "功能说明："
echo "  1. read_confluence_page - 读取页面"
echo "  2. create_confluence_page - 创建页面"
echo "  3. update_confluence_page - 更新页面"
echo "  4. search_confluence_pages - 搜索页面"
echo ""
if [ "$MERMAID_AVAILABLE" = "true" ]; then
    echo "✅ Mermaid 本地渲染: 已启用"
else
    echo "⚠️  Mermaid 本地渲染: 未启用（使用代码块方式）"
fi
echo ""
echo "使用示例："
echo "  在 Claude Code 中输入："
echo "  '读取 Confluence 页面 416129733'"
echo "  '创建一个 Confluence 页面...'"
echo ""
echo "详细文档: docs/MCP_FEATURES.md"
