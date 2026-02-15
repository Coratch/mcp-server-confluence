# 安全测试快速配置指南

## 📋 配置步骤（5 分钟）

### 步骤 1: 在 Confluence 中准备测试区域

1. **登录 Confluence**
   ```
   访问: https://confluence.example.com
   ```

2. **进入你的个人空间**
   - 点击顶部导航的 "Spaces" → "Personal"
   - 或直接访问: `https://confluence.example.com/display/~your_username`

3. **创建测试页面**
   - 点击 "Create" 按钮
   - 标题输入: `MCP 测试区域`
   - 内容可以写:
     ```
     # MCP 测试区域

     这个页面用于测试 Confluence MCP 服务器。
     所有自动创建的测试页面都会出现在这个页面下。

     测试完成后可以删除子页面。
     ```
   - 点击 "Publish"

4. **获取页面 ID**
   - 发布后，查看浏览器地址栏
   - URL 格式: `https://confluence.example.com/pages/viewpage.action?pageId=123456`
   - 复制 `pageId=` 后面的数字（例如：123456）

5. **获取空间键**
   - 个人空间的键通常是: `~your_username`
   - 例如：`~your_username`

### 步骤 2: 配置环境变量

1. **复制配置模板**
   ```bash
   cd /path/to/mcp-server-confluence
   cp .env.example .env
   ```

2. **编辑 .env 文件**
   ```bash
   # 使用你喜欢的编辑器
   nano .env
   # 或
   vim .env
   # 或
   code .env
   ```

3. **填入配置**
   ```bash
   # Confluence 配置
   CONFLUENCE_BASE_URL=https://confluence.example.com
   CONFLUENCE_API_TOKEN=你的_token_这里
   CONFLUENCE_DEFAULT_SPACE=~your_username
   CONFLUENCE_TIMEOUT=30

   # 安全测试配置
   CONFLUENCE_TEST_PARENT_PAGE_ID=123456  # 替换为你的测试页面 ID

   # 日志配置
   LOG_LEVEL=INFO
   ```

4. **保存文件**
   - nano: `Ctrl+X`, 然后 `Y`, 然后 `Enter`
   - vim: `:wq`
   - VS Code: `Cmd+S`

### 步骤 3: 获取 Personal Access Token

1. **进入 Token 管理页面**
   - 点击右上角头像 → "Settings"
   - 左侧菜单选择 "Personal Access Tokens"
   - 或直接访问: `https://confluence.example.com/plugins/personalaccesstokens/usertokens.action`

2. **创建新 Token**
   - 点击 "Create token"
   - Token 名称: `MCP Server`
   - 过期时间: 选择合适的时间（建议 30 天或 90 天）
   - 点击 "Create"

3. **复制 Token**
   - ⚠️ **重要**: Token 只显示一次，请立即复制
   - 复制后粘贴到 `.env` 文件的 `CONFLUENCE_API_TOKEN`

### 步骤 4: 验证配置

```bash
# 运行配置验证
python -c "
import os
from dotenv import load_dotenv
load_dotenv()

print('配置检查:')
print(f'✓ URL: {os.getenv(\"CONFLUENCE_BASE_URL\")}')
print(f'✓ Token: {\"已配置\" if os.getenv(\"CONFLUENCE_API_TOKEN\") else \"未配置\"}')
print(f'✓ 空间: {os.getenv(\"CONFLUENCE_DEFAULT_SPACE\")}')
print(f'✓ 测试页面: {os.getenv(\"CONFLUENCE_TEST_PARENT_PAGE_ID\")}')
"
```

### 步骤 5: 运行安全测试

```bash
# 运行安全测试脚本
python examples/safe_test.py
```

**预期输出**:
```
🔍 验证配置
============================================================
Confluence URL: https://confluence.example.com
API Token: ✅ 已配置
测试空间: ~your_username
测试父页面 ID: 123456

✅ 配置完整

按 Enter 键开始测试...

🔒 Confluence MCP 安全测试
============================================================
空间: ~your_username
父页面 ID: 123456

1️⃣  验证父页面...
   ✅ 父页面: MCP 测试区域
   ✅ 空间: ~your_username

2️⃣  创建测试子页面...
   ✅ 页面创建成功!
   页面 ID: 789012
   标题: MCP 测试 - 20260130_143022
   URL: https://confluence.example.com/pages/viewpage.action?pageId=789012

3️⃣  读取页面验证...
   ✅ 读取成功: MCP 测试 - 20260130_143022
   ✅ Markdown 转换成功 (1234 字符)
   ✅ Mermaid 图表转换正确

4️⃣  更新页面测试...
   ✅ 更新成功!
   版本: 1 → 2

5️⃣  搜索测试...
   ✅ 搜索成功，找到 1 个结果

============================================================
✅ 所有测试完成!
============================================================
```

## 🎯 测试成功后

1. **访问 Confluence 查看结果**
   - 打开测试页面
   - 应该能看到新创建的子页面
   - 点击查看内容和 Mermaid 图表

2. **清理测试数据（可选）**
   - 在 Confluence 中删除测试子页面
   - 保留 "MCP 测试区域" 页面供后续测试使用

## 🔒 安全保证

通过这个配置，所有测试操作都会：
- ✅ 只在你的个人空间进行
- ✅ 只在指定的测试页面下创建子页面
- ✅ 不会影响其他任何内容
- ✅ 可以随时删除测试数据

## 🚀 配置 Claude Desktop

测试成功后，可以配置 Claude Desktop：

```json
{
  "mcpServers": {
    "confluence": {
      "command": "python",
      "args": ["-m", "confluence_mcp.server"],
      "env": {
        "CONFLUENCE_BASE_URL": "https://confluence.example.com",
        "CONFLUENCE_API_TOKEN": "your_token_here",
        "CONFLUENCE_DEFAULT_SPACE": "~your_username",
        "CONFLUENCE_TEST_PARENT_PAGE_ID": "123456"
      }
    }
  }
}
```

## ❓ 常见问题

### Q: 找不到页面 ID？
A: 打开页面后，查看 URL 中的 `pageId=` 参数

### Q: Token 无效？
A: 检查 Token 是否正确复制，是否已过期

### Q: 权限错误？
A: 确保在自己的个人空间操作，个人空间你有完全权限

### Q: 测试失败？
A: 查看错误信息，检查网络连接和配置

## 📞 需要帮助？

查看完整文档:
- `examples/SAFE_TESTING.md` - 详细安全测试指南
- `README.md` - 完整项目文档
- `examples/QUICKSTART.md` - 快速入门

---

**准备好了吗？** 按照上面的步骤开始配置吧！ 🚀
