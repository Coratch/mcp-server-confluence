"""使用示例脚本

演示如何使用 Confluence MCP 服务器的各个功能。

注意：这个脚本需要在配置好 .env 文件后运行。
"""
import asyncio
from confluence_mcp.api.client import ConfluenceClient
from confluence_mcp.converters.markdown_to_storage import MarkdownToStorageConverter
from confluence_mcp.converters.storage_to_markdown import StorageToMarkdownConverter


async def example_read_page():
    """示例：读取页面"""
    print("\n=== 示例 1: 读取页面 ===")

    async with ConfluenceClient() as client:
        # 替换为实际的页面 ID
        page_id = "123456"

        try:
            page = await client.get_page(page_id)
            print(f"页面标题: {page.title}")
            print(f"空间: {page.space.key}")
            print(f"版本: {page.version.number if page.version else 'N/A'}")

            # 转换为 Markdown
            converter = StorageToMarkdownConverter()
            markdown = converter.convert(page.storage_content, page.title)
            print(f"\nMarkdown 内容预览:\n{markdown[:200]}...")

        except Exception as e:
            print(f"错误: {e}")


async def example_create_page():
    """示例：创建页面"""
    print("\n=== 示例 2: 创建页面 ===")

    markdown_content = """
# 测试页面

这是一个测试页面。

## Mermaid 图表

```mermaid
graph TD
    A[开始] --> B[处理]
    B --> C[结束]
```

## 代码示例

```python
def hello():
    print("Hello, Confluence!")
```
"""

    async with ConfluenceClient() as client:
        try:
            # 转换 Markdown 到 Storage Format
            converter = MarkdownToStorageConverter()
            storage_content = converter.convert(markdown_content)

            # 创建页面
            page = await client.create_page(
                space_key="TEST",  # 替换为实际的空间键
                title="测试页面 - 自动创建",
                body_storage=storage_content
            )

            print(f"页面创建成功!")
            print(f"页面 ID: {page.id}")
            print(f"标题: {page.title}")
            print(f"URL: {page.web_url}")

        except Exception as e:
            print(f"错误: {e}")


async def example_update_page():
    """示例：更新页面"""
    print("\n=== 示例 3: 更新页面 ===")

    markdown_content = """
# 更新后的页面

内容已更新。

## 新增的 Mermaid 图表

```mermaid
sequenceDiagram
    Alice->>Bob: Hello
    Bob->>Alice: Hi
```
"""

    async with ConfluenceClient() as client:
        # 替换为实际的页面 ID
        page_id = "123456"

        try:
            # 获取当前页面
            current_page = await client.get_page(page_id)
            print(f"当前版本: {current_page.version.number if current_page.version else 'N/A'}")

            # 转换 Markdown 到 Storage Format
            converter = MarkdownToStorageConverter()
            storage_content = converter.convert(markdown_content)

            # 更新页面
            updated_page = await client.update_page(
                page_id=page_id,
                title=current_page.title,
                body_storage=storage_content,
                version_number=current_page.version.number if current_page.version else 1
            )

            print(f"页面更新成功!")
            print(f"新版本: {updated_page.version.number if updated_page.version else 'N/A'}")

        except Exception as e:
            print(f"错误: {e}")


async def example_search_pages():
    """示例：搜索页面"""
    print("\n=== 示例 4: 搜索页面 ===")

    async with ConfluenceClient() as client:
        try:
            # 搜索包含 "测试" 的页面
            cql = 'text ~ "测试" AND type = page'
            results = await client.search_pages(cql=cql, limit=5)

            print(f"找到 {len(results)} 个结果:")
            for i, result in enumerate(results, 1):
                print(f"\n{i}. {result.title}")
                print(f"   ID: {result.id}")
                print(f"   空间: {result.space.key if result.space else 'N/A'}")
                if result.excerpt:
                    print(f"   摘要: {result.excerpt[:100]}...")

        except Exception as e:
            print(f"错误: {e}")


async def example_mermaid_conversion():
    """示例：Mermaid 转换"""
    print("\n=== 示例 5: Mermaid 转换 ===")

    from confluence_mcp.converters.mermaid_handler import MermaidHandler

    markdown = """
```mermaid
graph TD
    A[开始] --> B{判断}
    B -->|是| C[处理]
    B -->|否| D[跳过]
    C --> E[结束]
    D --> E
```
"""

    print("原始 Markdown:")
    print(markdown)

    # Markdown -> Confluence
    confluence = MermaidHandler.markdown_to_confluence(markdown)
    print("\n转换为 Confluence 宏:")
    print(confluence[:200] + "...")

    # Confluence -> Markdown
    back_to_markdown = MermaidHandler.confluence_to_markdown(confluence)
    print("\n转换回 Markdown:")
    print(back_to_markdown)


async def main():
    """主函数"""
    print("Confluence MCP 服务器使用示例")
    print("=" * 50)

    # 运行示例（根据需要注释/取消注释）

    # 示例 5: Mermaid 转换（不需要 API 连接）
    await example_mermaid_conversion()

    # 以下示例需要有效的 Confluence 连接
    # 请先配置 .env 文件，并替换示例中的页面 ID 和空间键

    # await example_search_pages()
    # await example_read_page()
    # await example_create_page()
    # await example_update_page()

    print("\n" + "=" * 50)
    print("示例运行完成!")


if __name__ == "__main__":
    asyncio.run(main())
