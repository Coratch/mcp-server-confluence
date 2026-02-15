"""从 Markdown 文件创建 Confluence 页面（Mermaid 转图片）"""
import asyncio
import os
from dotenv import load_dotenv
from confluence_mcp.api.client import ConfluenceClient
from confluence_mcp.converters.markdown_to_storage import MarkdownToStorageConverter

load_dotenv()


async def create_page_with_mermaid_images():
    # 读取 Markdown 文件
    with open('examples/markdown_example.md', 'r', encoding='utf-8') as f:
        markdown_content = f.read()

    print('读取 Markdown 文件成功')
    print(f'内容长度: {len(markdown_content)} 字符')
    print()

    # 检查 Mermaid 代码块
    if '```mermaid' in markdown_content:
        print('✅ 检测到 Mermaid 代码块')
    print()

    # 转换为 Storage Format（使用图片方式）
    print('转换 Markdown 到 Confluence Storage Format...')
    print('📸 使用 mermaid.ink 将 Mermaid 图表转换为图片')
    converter = MarkdownToStorageConverter()
    storage_content = converter.convert(markdown_content, use_mermaid_images=True)

    # 验证图片链接
    if 'mermaid.ink/img/' in storage_content:
        print('✅ Mermaid 代码块已转换为图片链接')
    else:
        print('⚠️  未检测到图片链接')
    print()

    # 获取测试配置
    test_space = os.getenv('CONFLUENCE_DEFAULT_SPACE')
    test_parent_id = os.getenv('CONFLUENCE_TEST_PARENT_PAGE_ID')

    print(f'目标空间: {test_space}')
    print(f'父页面 ID: {test_parent_id}')
    print()

    # 创建页面
    async with ConfluenceClient() as client:
        print('创建 Confluence 页面...')
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        page = await client.create_page(
            space_key=test_space,
            title=f'Wiki.js POC 测试案例（图片版）- {timestamp}',
            body_storage=storage_content,
            parent_id=test_parent_id
        )

        print('=' * 80)
        print('✅ 页面创建成功!')
        print('=' * 80)
        print(f'页面 ID: {page.id}')
        print(f'标题: {page.title}')
        print(f'空间: {page.space.key}')
        print(f'版本: {page.version.number if page.version else 1}')
        base_url = os.getenv('CONFLUENCE_BASE_URL')
        print(f'URL: {base_url}{page.web_url}')
        print()
        print('💡 提示:')
        print('   - 页面已创建在测试区域下')
        print('   - Mermaid 图表已转换为图片（使用 mermaid.ink）')
        print('   - 访问上面的 URL 查看效果')
        print('   - 图片可以正常显示，无需 Confluence Mermaid 插件')


if __name__ == '__main__':
    asyncio.run(create_page_with_mermaid_images())
