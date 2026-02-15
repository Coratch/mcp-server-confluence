# Confluence MCP Server

基于 Python + FastMCP 的 Confluence MCP 服务器，通过 MCP 协议让 Claude 直接读写 Confluence 页面，支持 Markdown 双向转换和 Mermaid 图表渲染。

## 功能

| 工具 | 说明 |
|------|------|
| `confluence_read_page` | 读取页面，自动转为 Markdown（含 Mermaid 代码块） |
| `confluence_create_page` | 从 Markdown 创建页面（Mermaid 自动渲染为图片） |
| `confluence_update_page` | 更新页面内容，自动处理版本号 |
| `confluence_search_pages` | CQL 关键词搜索页面 |

支持 Confluence 宏：`mermaid`、`code`、`info`、`warning`、`note`、`tip`

## 一键安装

### 前置要求

- Python 3.10+
- Git
- Confluence Personal Access Token ([获取方式](#获取-personal-access-token))

### 安装

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Coratch/mcp-server-confluence/main/install_mcp.sh)
```

或者克隆后本地运行：

```bash
git clone https://github.com/Coratch/mcp-server-confluence.git
cd mcp-server-confluence
bash install_mcp.sh
```

脚本会自动完成：
1. 创建隔离的 Python 虚拟环境（`~/.local/share/confluence-mcp/venv/`）
2. 安装所有依赖
3. 交互式收集 Confluence 配置（URL、Token、Space）
4. 注册 MCP 服务到 Claude Code（`~/.claude.json`）
5. 验证安装

安装完成后重启 Claude Code 即可使用。

### 手动安装

如果不使用一键脚本，也可以手动配置：

```bash
pip install -e .
```

编辑 `~/.claude.json`，在 `mcpServers` 下添加：

```json
{
  "confluence": {
    "type": "stdio",
    "command": "python",
    "args": ["-m", "confluence_mcp.server"],
    "env": {
      "CONFLUENCE_BASE_URL": "https://wiki.example.com",
      "CONFLUENCE_API_TOKEN": "your_token_here",
      "CONFLUENCE_DEFAULT_SPACE": "YOUR_SPACE_KEY"
    }
  }
}
```

### 获取 Personal Access Token

1. 登录 Confluence → 右上角头像 → **Settings**
2. 左侧菜单 → **Personal Access Tokens**
3. 点击 **Create token**，复制保存

## 使用示例

在 Claude Code 中直接对话：

```
读取 Confluence 页面 416129733
```

```
在 DEV 空间创建一个页面，标题"系统架构"，内容包含流程图
```

```
搜索 Confluence 中关于"部署"的页面
```

### Mermaid 图表

Markdown 中的 Mermaid 代码块会自动处理：

- **创建/更新页面**：Mermaid 渲染为图片上传到 Confluence
- **读取页面**：Confluence Mermaid 宏转回 Markdown 代码块

可选安装 `mermaid-cli` 启用本地渲染（更快更稳定）：

```bash
npm install -g @mermaid-js/mermaid-cli
```

## 项目结构

```
mcp-server-confluence/
├── src/confluence_mcp/
│   ├── server.py                  # MCP 服务器入口，定义 4 个 tools
│   ├── config.py                  # 配置管理（Pydantic Settings）
│   ├── api/
│   │   ├── client.py              # Confluence REST API 异步客户端
│   │   └── models.py              # 数据模型
│   ├── converters/
│   │   ├── storage_to_markdown.py # Storage Format → Markdown
│   │   ├── markdown_to_storage.py # Markdown → Storage Format
│   │   ├── mermaid_handler.py     # Mermaid 宏双向转换
│   │   ├── mermaid_local_renderer.py  # 本地 mermaid-cli 渲染
│   │   ├── mermaid_renderer.py    # Mermaid 在线渲染
│   │   └── mermaid_to_image.py    # Mermaid 图片转换
│   └── utils/
│       ├── logger.py              # 日志
│       └── exceptions.py          # 自定义异常
├── tests/                         # 单元测试
├── examples/                      # 示例代码和 Markdown 样例
├── docs/                          # 补充文档
├── install_mcp.sh                 # 一键部署脚本
├── pyproject.toml                 # 项目配置和依赖
└── .env.example                   # 环境变量模板
```

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/ -v --cov=confluence_mcp

# 代码格式化
black src/
ruff check src/

# 类型检查
mypy src/
```

## 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `CONFLUENCE_BASE_URL` | 是 | - | Confluence 实例地址 |
| `CONFLUENCE_API_TOKEN` | 是 | - | Personal Access Token |
| `CONFLUENCE_DEFAULT_SPACE` | 否 | - | 默认空间 Key |
| `CONFLUENCE_TIMEOUT` | 否 | `30` | API 请求超时（秒） |
| `LOG_LEVEL` | 否 | `INFO` | 日志级别 |

## 故障排除

| 错误 | 原因 | 解决 |
|------|------|------|
| `AuthenticationError` | Token 无效或过期 | 重新生成 Token |
| `NotFoundError` | 页面 ID 错误或无权限 | 确认 ID 和权限 |
| `ConversionError` | Markdown/Mermaid 语法错误 | 检查内容格式 |

调试时可设置 `LOG_LEVEL=DEBUG` 查看详细日志。

## License

MIT
