# Confluence MCP Server

基于 Python + FastMCP 的 Confluence MCP 服务器，通过 MCP 协议让 Claude 直接读写 Confluence 页面，支持 Markdown 双向转换、Mermaid 图表渲染、Draw.io 图表上传和页面评论管理。

## 功能

| 工具 | 说明 |
|------|------|
| `confluence_read_page` | 读取页面，自动转为 Markdown（含 Mermaid/Draw.io） |
| `confluence_create_page` | 从 Markdown 创建页面（Mermaid 自动渲染，Draw.io 自动上传） |
| `confluence_update_page` | 更新页面内容，自动处理版本号 |
| `confluence_search_pages` | CQL 关键词搜索页面 |
| `confluence_upload_drawio` | 上传 Draw.io 图表 XML 到页面，自动插入渲染宏 |
| `confluence_get_comments` | 获取页面评论（含嵌套回复），自动转为 Markdown |
| `confluence_add_comment` | 发布页面评论，支持纯文本/Markdown 格式和回复 |

支持 Confluence 宏：`mermaid`、`code`、`info`、`warning`、`note`、`tip`、`expand`、`drawio`

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

### 页面操作

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

Markdown 中的 Mermaid 代码块会自��处理，支持三种渲染模式：

| 模式 | 说明 |
|------|------|
| `macro`（默认） | 使用 Confluence 原生 Mermaid 宏渲染（需要 Mermaid 插件） |
| `image` | 使用本地 mermaid-cli 渲染为 PNG 图片上传 |
| `code_block` | 使用可折叠��码块 + Mermaid Live Editor 链接 |

可选安装 `mermaid-cli` 启用本地渲染（更快更稳定）：

```bash
npm install -g @mermaid-js/mermaid-cli
```

### Draw.io 图表

支持上传 Draw.io XML 到 Confluence 页面，自动创建附件并插入 Draw.io 宏渲染。

```
在页面 123456 的"系统架构"标题下插入一个 Draw.io 架构图
```

### 评论管理

```
获取页面 123456 的所有评论
```

```
在页面 123456 上发布一条评论："审核通过，可以上线"
```

```
回复页面 123456 上的评论 67890："同意这个方案"
```

评论功能支持：
- **纯文本**（默认）：自动转义 HTML 特殊字符
- **Markdown**：自动转换为 Confluence Storage Format
- **回复评论**：通过 `parent_comment_id` 指定父评论 ID

## 项目结构

```
mcp-server-confluence/
├── src/confluence_mcp/
│   ├── server.py                      # MCP 服务器入口，定义 7 个 Tools
│   ├── config.py                      # 配置管理（Pydantic Settings）
│   ├── api/
│   │   ├── client.py                  # Confluence REST API 异步客户端
│   │   └── models.py                  # 数据模型（Page, SearchResult 等）
│   ├── converters/
│   │   ├── storage_to_markdown.py     # Storage Format → Markdown
│   │   ├── markdown_to_storage.py     # Markdown → Storage Format
│   │   ├── mermaid_handler.py         # Mermaid 宏双向转换
│   │   ├── mermaid_local_renderer.py  # 本地 mermaid-cli 渲染
│   │   ├── mermaid_renderer.py        # Mermaid 在线渲染（降级方案）
│   │   ├── mermaid_to_image.py        # Mermaid 图片转换
│   │   └── drawio_handler.py          # Draw.io 宏双向转换
│   └── utils/
│       ├── logger.py                  # 日志工具
│       └── exceptions.py              # 自定义异常层级
├── tests/                             # 单元测试
├── examples/                          # 示例代码和 Markdown 样例
├── docs/                              # 补充文档
├── scripts/                           # 诊断和验证脚本
├── install_mcp.sh                     # 一键部署脚本
├── pyproject.toml                     # 项目配置和依赖
└── .env.example                       # 环境变量模板
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

# 类型检���
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

## API 端点参考

本项目使用 Confluence REST API v1，兼容 Server / Data Center / Cloud。

| 操作 | HTTP 方法 | 端点 |
|------|-----------|------|
| 获取页面 | GET | `/rest/api/content/{id}` |
| 创建页面 | POST | `/rest/api/content` |
| 更新页面 | PUT | `/rest/api/content/{id}` |
| 搜索页面 | GET | `/rest/api/content/search` |
| 获取附件 | GET | `/rest/api/content/{id}/child/attachment` |
| 上传附件 | POST | `/rest/api/content/{id}/child/attachment` |
| 获取评论 | GET | `/rest/api/content/{id}/child/comment` |
| 创建评论 | POST | `/rest/api/content`（type=comment） |

## 故障排除

| 错误 | 原因 | 解决 |
|------|------|------|
| `AuthenticationError` | Token 无效或过期 | 重新生成 Token |
| `NotFoundError` | 页面 ID 错误或无权限 | 确认 ID 和权限 |
| `PermissionError` | 无操作权限 | 确认 Token 权限范围 |
| `ConversionError` | Markdown/Mermaid 语法错误 | 检查内容格式 |
| 版本冲突 (409) | 页面已被其他用户修改 | 重新获取最新版本后重试 |

调试时可设置 `LOG_LEVEL=DEBUG` 查看详细日志。

## License

MIT
