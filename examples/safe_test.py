"""安全测试脚本 - 只在指定页面下操作"""
import asyncio
import os
from dotenv import load_dotenv

from confluence_mcp.api.client import ConfluenceClient
from confluence_mcp.converters.markdown_to_storage import MarkdownToStorageConverter
from confluence_mcp.converters.storage_to_markdown import StorageToMarkdownConverter

# 加载环境变量
load_dotenv()


async def safe_test():
    """安全测试 - 只在测试页面下创建子页面"""

    # 从环境变量获取配置
    test_space = os.getenv("CONFLUENCE_DEFAULT_SPACE")
    test_parent_id = os.getenv("CONFLUENCE_TEST_PARENT_PAGE_ID")

    if not test_space or not test_parent_id:
        print("❌ 请先配置环境变量:")
        print("   CONFLUENCE_DEFAULT_SPACE - 你的个人空间（例如：~username）")
        print("   CONFLUENCE_TEST_PARENT_PAGE_ID - 测试页面 ID")
        print("\n💡 编辑 .env 文件添加这些配置")
        return

    print("=" * 60)
    print("🔒 Confluence MCP 安全测试")
    print("=" * 60)
    print(f"空间: {test_space}")
    print(f"父页面 ID: {test_parent_id}")
    print()

    # 测试内容
    test_markdown = """
# MCP 自动测试页面

这是一个自动创建的测试页面，用于验证 Confluence MCP 服务器功能。

## 测试时间

测试时间: {timestamp}

## Mermaid 图表测试

```mermaid
graph TD
    A[测试开始] --> B[创建页面]
    B --> C[验证内容]
    C --> D[更新页面]
    D --> E[测试完成]
```

## 功能验证清单

- ✅ Markdown 转换
- ✅ Mermaid 图表支持
- ✅ 页面创建（带父页面）
- ✅ 页面读取
- ✅ 页面更新

## ��码示例

```python
def hello_confluence():
    print("Hello from MCP!")
    return True
```

## 表格测试

| 功能 | 状态 | 备注 |
|------|------|------|
| 创建 | ✅ | 成功 |
| 读取 | ✅ | 成功 |
| 更新 | ✅ | 成功 |

---

**注意**: 这是自动生成的测试页面，测试完成后可以安全删除。
"""

    from datetime import datetime
    test_markdown = test_markdown.replace("{timestamp}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    async with ConfluenceClient() as client:
        try:
            # 1. 验证父页面存在
            print("1️⃣  验证父页面...")
            parent_page = await client.get_page(test_parent_id)
            print(f"   ✅ 父页面: {parent_page.title}")
            print(f"   ✅ 空间: {parent_page.space.key}")

            if parent_page.space.key != test_space:
                print(f"   ⚠️  警告: 父页面空间 ({parent_page.space.key}) 与配置空间 ({test_space}) 不匹配")
            print()

            # 2. 创建测试子页面
            print("2️⃣  创建测试子页面...")
            converter = MarkdownToStorageConverter()
            storage_content = converter.convert(test_markdown)

            new_page = await client.create_page(
                space_key=parent_page.space.key,  # 使用父页面的空间
                title=f"MCP 测试 - {datetime.now().strftime('%Y%m%d_%H%M%S')}",
                body_storage=storage_content,
                parent_id=test_parent_id  # 重要：指定父页面
            )

            print(f"   ✅ 页面创建成功!")
            print(f"   页面 ID: {new_page.id}")
            print(f"   标题: {new_page.title}")
            print(f"   URL: {os.getenv('CONFLUENCE_BASE_URL')}{new_page.web_url}")
            print()

            # 3. 读取验证
            print("3️⃣  读取页面验证...")
            read_page = await client.get_page(new_page.id)
            print(f"   ✅ 读取成功: {read_page.title}")

            # 转换为 Markdown 验证
            md_converter = StorageToMarkdownConverter()
            markdown_content = md_converter.convert(read_page.storage_content)
            print(f"   ✅ Markdown 转换成功 ({len(markdown_content)} 字符)")

            # 验证 Mermaid 转换
            if "```mermaid" in markdown_content:
                print(f"   ✅ Mermaid 图表转换正确")
            print()

            # 4. 更新测试
            print("4️⃣  更新页面测试...")
            updated_markdown = test_markdown + "\n\n## 更新测试\n\n✅ 页面已成功更新！\n\n更新时间: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            updated_storage = converter.convert(updated_markdown)

            updated_page = await client.update_page(
                page_id=new_page.id,
                title=new_page.title,
                body_storage=updated_storage,
                version_number=new_page.version.number if new_page.version else 1
            )
            print(f"   ✅ 更新成功!")
            print(f"   版本: {new_page.version.number if new_page.version else 1} → {updated_page.version.number if updated_page.version else 'N/A'}")
            print()

            # 5. 搜索测试
            print("5️⃣  搜索测试...")
            search_results = await client.search_pages(
                cql=f'space = "{parent_page.space.key}" AND title ~ "MCP 测试"',
                limit=5
            )
            print(f"   ✅ 搜索成功，找到 {len(search_results)} 个结果")
            print()

            print("=" * 60)
            print("✅ 所有测试完成!")
            print("=" * 60)
            print(f"\n📝 测试页面位置:")
            print(f"   父页面: {parent_page.title}")
            print(f"   新页面: {new_page.title}")
            print(f"\n🔗 访问链接:")
            print(f"   {os.getenv('CONFLUENCE_BASE_URL')}{new_page.web_url}")
            print(f"\n💡 提示:")
            print(f"   - 测试页面已创建在 '{parent_page.title}' 下")
            print(f"   - 测试完成后可以手动删除")
            print(f"   - 所有操作都限制在指定的测试区域")

        except Exception as e:
            print(f"\n❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()


async def verify_config():
    """验证配置"""
    print("=" * 60)
    print("🔍 验证配置")
    print("=" * 60)

    base_url = os.getenv("CONFLUENCE_BASE_URL")
    api_token = os.getenv("CONFLUENCE_API_TOKEN")
    test_space = os.getenv("CONFLUENCE_DEFAULT_SPACE")
    test_parent_id = os.getenv("CONFLUENCE_TEST_PARENT_PAGE_ID")

    print(f"Confluence URL: {base_url or '❌ 未配置'}")
    print(f"API Token: {'✅ 已配置' if api_token else '❌ 未配置'}")
    print(f"测试空间: {test_space or '❌ 未配置'}")
    print(f"测试父页面 ID: {test_parent_id or '❌ 未配置'}")
    print()

    if not all([base_url, api_token, test_space, test_parent_id]):
        print("❌ 配置不完整，请编辑 .env 文件")
        return False

    print("✅ 配置完整")
    return True


async def main():
    """主函数"""
    # 验证配置
    if not await verify_config():
        return

    print()
    print("开始测试...")
    print()

    # 运行测试
    await safe_test()


if __name__ == "__main__":
    asyncio.run(main())
