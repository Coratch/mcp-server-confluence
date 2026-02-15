# 快速入门指南

本指南将帮助你快速开始使用 Confluence MCP 服务器。

## 步骤 1: 安装

```bash
# 克隆或进入项目目录
cd JiraMCP

# 安装依赖
pip install -e .
```

## 步骤 2: 配置

### 2.1 创建配置文件

```bash
cp .env.example .env
```

### 2.2 获取 Personal Access Token

1. 登录你的 Confluence 实例（例如：https://confluence.example.com）
2. 点击右上角头像 → **Settings**
3. 在左侧菜单选择 **Personal Access Tokens**
4. 点击 **Create token**
5. 输入 Token 名称（例如：MCP Server）
6. 复制生成的 Token

### 2.3 编辑 .env 文件

```bash
CONFLUENCE_BASE_URL=https://confluence.example.com
CONFLUENCE_API_TOKEN=你的_token_这里
CONFLUENCE_DEFAULT_SPACE=你的空间键
CONFLUENCE_TIMEOUT=30
LOG_LEVEL=INFO
```

## 步骤 3: 测试连接

运行示例脚本测试连接：

```bash
python examples/usage_example.py
```

如果配置正确，你应该看到 Mermaid 转换示例的输出。

## 步骤 4: 在 Claude Desktop 中使用

### 4.1 配置 Claude Desktop

编辑配置文件：

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

添加以下配置：

```json
{
  "mcpServers": {
    "confluence": {
      "command": "python",
      "args": ["-m", "confluence_mcp.server"],
      "env": {
        "CONFLUENCE_BASE_URL": "https://confluence.example.com",
        "CONFLUENCE_API_TOKEN": "你的_token_这里"
      }
    }
  }
}
```

### 4.2 重启 Claude Desktop

完全退出并重新启动 Claude Desktop。

### 4.3 验证连接

在 Claude Desktop 中，你应该能看到 Confluence 相关的工具。尝试以下命令：

```
搜索 Confluence 中包含"测试"的页面
```

或

```
读取页面 ID 为 123456 的内容
```

## 步骤 5: 基本使用

### 读取页面

```
请读取 Confluence 页面 123456 的内容
```

### 创建页面

```
在空间 TEST 中创建一个新页面，标题为"测试页面"，内容如下：

# 测试页面

这是测试内容。

## 流程图

```mermaid
graph TD
    A --> B
```
```

### 更新页面

```
更新页面 123456，将内容改为：

# 更新后的内容

这是新的内容。
```

### 搜索页面

```
在空间 TEST 中搜索包含"项目"的页面
```

## 常见问题

### Q: 认证失败怎么办？

A: 检查以下几点：
1. Token 是否正确复制（没有多余空格）
2. Token 是否已过期
3. Token 是否有足够的权限

### Q: 找不到页面？

A: 确认：
1. 页面 ID 是否正确
2. 你是否有访问该页面的权限
3. 页面是否存在

### Q: Mermaid 图表显示不正确？

A: 确保：
1. Confluence 实例已安装 Mermaid 插件
2. Mermaid 语法正确
3. 代码块使用 \`\`\`mermaid 标记

## 下一步

- 查看 [README.md](../README.md) 了解完整功能
- 查看 [examples/sample_page.md](sample_page.md) 了解支持的格式
- 运行 [examples/usage_example.py](usage_example.py) 查看代码示例

## 获取帮助

如遇到问题，请：
1. 检查日志输出（设置 `LOG_LEVEL=DEBUG` 获取详细日志）
2. 查看 [故障排除](../README.md#故障排除) 部分
3. 在 GitHub 上提交 Issue

祝使用愉快！
