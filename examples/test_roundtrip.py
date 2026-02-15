"""测试 Markdown 上传下载往返，检查信息丢失"""
import asyncio
import os
from datetime import datetime

from dotenv import load_dotenv

from confluence_mcp.api.client import ConfluenceClient
from confluence_mcp.config import get_config
from confluence_mcp.converters.markdown_to_storage import MarkdownToStorageConverter
from confluence_mcp.converters.storage_to_markdown import StorageToMarkdownConverter

load_dotenv()


async def test_roundtrip():
    """测试 Markdown 往返转换"""

    print('=' * 80)
    print('Markdown 往返测试')
    print('=' * 80)
    print()

    # 1. 读取原始 Markdown
    with open('examples/markdown_example.md', 'r', encoding='utf-8') as f:
        original_markdown = f.read()

    print('步骤 1: 读取原始 Markdown')
    print(f'  长度: {len(original_markdown)} 字符')
    print(f'  行数: {len(original_markdown.splitlines())} 行')
    print()

    # 2. 转换为 Storage Format
    print('步骤 2: 转换 Markdown → Storage Format')
    md_to_storage = MarkdownToStorageConverter()
    storage_content = md_to_storage.convert(original_markdown, use_mermaid_images=False)
    print(f'  Storage Format 长度: {len(storage_content)} 字符')
    print()

    # 3. 上传到 Confluence
    print('步骤 3: 上传到 Confluence')
    config = get_config()
    test_space = config.confluence_default_space
    test_parent_id = os.getenv('CONFLUENCE_TEST_PARENT_PAGE_ID')

    async with ConfluenceClient() as client:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        page = await client.create_page(
            space_key=test_space,
            title=f'往返测试 - {timestamp}',
            body_storage=storage_content,
            parent_id=test_parent_id,
        )

        print(f'  ✅ 页面创建成功: {page.id}')
        print(f'  URL: {config.confluence_base_url}{page.web_url}')
        print()

        # 4. 从 Confluence 读取
        print('步骤 4: 从 Confluence 读取页面')
        page = await client.get_page(page.id)
        print(f'  Storage Format 长度: {len(page.storage_content)} 字符')
        print()

        # 5. 转换回 Markdown
        print('步骤 5: 转换 Storage Format → Markdown')
        storage_to_md = StorageToMarkdownConverter()
        converted_markdown = storage_to_md.convert(page.storage_content)
        print(f'  转换后 Markdown 长度: {len(converted_markdown)} 字符')
        print(f'  转换后行数: {len(converted_markdown.splitlines())} 行')
        print()

        # 6. 对比分析
        print('=' * 80)
        print('对比分析')
        print('=' * 80)
        print()

        # 保存文件用于对比
        with open('/tmp/original.md', 'w', encoding='utf-8') as f:
            f.write(original_markdown)

        with open('/tmp/converted.md', 'w', encoding='utf-8') as f:
            f.write(converted_markdown)

        print('文件已保存:')
        print('  原始: /tmp/original.md')
        print('  转换: /tmp/converted.md')
        print()

        # 统计信息
        print('统计对比:')
        print(f'  原始长度: {len(original_markdown)} 字符')
        print(f'  转换长度: {len(converted_markdown)} 字符')
        print(f'  差异: {len(converted_markdown) - len(original_markdown)} 字符')
        print()

        # 检查关键元素
        print('关键元素检查:')

        # 检查标题
        original_h1 = original_markdown.count('# ')
        converted_h1 = converted_markdown.count('# ')
        print(f'  一级标题: 原始 {original_h1}, 转换 {converted_h1} {"✅" if original_h1 == converted_h1 else "❌"}')

        original_h2 = original_markdown.count('## ')
        converted_h2 = converted_markdown.count('## ')
        print(f'  二级标题: 原始 {original_h2}, 转换 {converted_h2} {"✅" if original_h2 == converted_h2 else "❌"}')

        # 检查代码块
        original_code = original_markdown.count('```')
        converted_code = converted_markdown.count('```')
        print(f'  代码块: 原始 {original_code // 2}, 转换 {converted_code // 2} {"✅" if original_code == converted_code else "❌"}')

        # 检查 Mermaid
        original_mermaid = original_markdown.count('```mermaid')
        converted_mermaid = converted_markdown.count('```mermaid')
        print(f'  Mermaid 图表: 原始 {original_mermaid}, 转换 {converted_mermaid} {"✅" if original_mermaid == converted_mermaid else "❌"}')

        # 检查表格
        original_table = original_markdown.count('|')
        converted_table = converted_markdown.count('|')
        print(f'  表格行: 原始 {original_table}, 转换 {converted_table} {"✅" if abs(original_table - converted_table) <= 2 else "❌"}')

        # 检查列表
        original_list = original_markdown.count('\n- ')
        converted_list = converted_markdown.count('\n- ')
        print(f'  列表项: 原始 {original_list}, 转换 {converted_list} {"✅" if abs(original_list - converted_list) <= 2 else "❌"}')

        print()

        # 检查特定内容
        print('内容完整性检查:')

        key_phrases = [
            'Wiki.js POC',
            'test_login',
            'GraphQL',
            'Playwright',
            'Docker',
        ]

        all_present = True
        for phrase in key_phrases:
            in_original = phrase in original_markdown
            in_converted = phrase in converted_markdown
            status = "✅" if in_converted else "❌"
            print(f'  "{phrase}": {status}')
            if not in_converted:
                all_present = False

        print()

        if all_present:
            print('✅ 所有关键内容都存在')
        else:
            print('❌ 部分内容丢失')

        print()
        print('=' * 80)
        print('使用 diff 查看详细差异:')
        print('  diff /tmp/original.md /tmp/converted.md')
        print('=' * 80)

        return page.id


if __name__ == '__main__':
    asyncio.run(test_roundtrip())
