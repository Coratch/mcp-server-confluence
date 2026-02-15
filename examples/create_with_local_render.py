"""从 Markdown 文件创建 Confluence 页面（支持本地渲染 Mermaid）"""
import asyncio
import os
from dotenv import load_dotenv
from confluence_mcp.api.client import ConfluenceClient
from confluence_mcp.converters.markdown_to_storage import MarkdownToStorageConverter
from confluence_mcp.converters.mermaid_handler import MermaidHandler
from confluence_mcp.converters.mermaid_renderer import MermaidRenderer

load_dotenv()


async def create_page_with_local_mermaid():
    # 读取 Markdown 文件
    with open('examples/markdown_example.md', 'r', encoding='utf-8') as f:
        markdown_content = f.read()

    print('读取 Markdown 文件成功')
    print(f'内容长度: {len(markdown_content)} 字符')
    print()

    # 检查 Mermaid 代码块
    mermaid_blocks = MermaidHandler.extract_mermaid_blocks(markdown_content)
    if mermaid_blocks:
        print(f'✅ 检测到 {len(mermaid_blocks)} 个 Mermaid 代码块')
    print()

    # 检查 mermaid-cli 是否可用
    if MermaidRenderer.is_available():
        print('✅ mermaid-cli 可用，将本地渲染 Mermaid 图表')
        use_local_render = True
    else:
        print('⚠️  mermaid-cli 不可用，使用代码块方式')
        use_local_render = False
    print()

    # 获取测试配置
    test_space = os.getenv('CONFLUENCE_DEFAULT_SPACE')
    test_parent_id = os.getenv('CONFLUENCE_TEST_PARENT_PAGE_ID')

    print(f'目标空间: {test_space}')
    print(f'父页面 ID: {test_parent_id}')
    print()

    # 创建页面
    async with ConfluenceClient() as client:
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if use_local_render and mermaid_blocks:
            print('='*80)
            print('使用本地渲染方案')
            print('='*80)

            # 1. 先创建页面（不含 Mermaid）
            converter = MarkdownToStorageConverter()
            storage_content = converter.convert(markdown_content, use_mermaid_images=False)

            print('1. 创建 Confluence 页面...')
            page = await client.create_page(
                space_key=test_space,
                title=f'Wiki.js POC 测试案例（本地渲染）- {timestamp}',
                body_storage=storage_content,
                parent_id=test_parent_id
            )
            print(f'   ✅ 页面创建成功: {page.id}')
            print()

            # 2. 渲染并上传 Mermaid 图片
            print(f'2. 渲染并上传 {len(mermaid_blocks)} 个 Mermaid 图表...')

            for idx, (original, code) in enumerate(mermaid_blocks):
                print(f'   处理图表 {idx + 1}/{len(mermaid_blocks)}...')

                # 渲染图片
                png_path = MermaidRenderer.render_to_png(code)

                if png_path and os.path.exists(png_path):
                    try:
                        # 上传为附件
                        filename = f'mermaid-diagram-{idx + 1}.png'

                        import httpx
                        base_url = os.getenv('CONFLUENCE_BASE_URL')
                        token = os.getenv('CONFLUENCE_API_TOKEN')

                        upload_headers = {
                            'Authorization': f'Bearer {token}',
                            'X-Atlassian-Token': 'no-check'
                        }

                        with open(png_path, 'rb') as img:
                            files = {'file': (filename, img, 'image/png')}

                            async with httpx.AsyncClient(timeout=30.0) as http_client:
                                response = await http_client.post(
                                    f'{base_url}/rest/api/content/{page.id}/child/attachment',
                                    files=files,
                                    headers=upload_headers
                                )

                                if response.status_code in [200, 201]:
                                    print(f'      ✅ 图片上传成功: {filename}')
                                else:
                                    print(f'      ❌ 上传失败: {response.status_code}')

                    finally:
                        # 清理临时文件
                        if os.path.exists(png_path):
                            os.remove(png_path)
                else:
                    print(f'      ❌ 渲染失败')

            print()
            print('3. 更新页面，插入图片...')

            # 重新读取页面获取最新版本号
            page_info = await client.get_page(page.id)

            # 在页面顶部插入图片
            images_html = '<h2>📊 Mermaid 图表预览</h2>\n'
            for idx in range(len(mermaid_blocks)):
                filename = f'mermaid-diagram-{idx + 1}.png'
                images_html += f'<p><ac:image><ri:attachment ri:filename="{filename}" /></ac:image></p>\n'

            images_html += '<hr />\n'

            # 更新页面内容 - 使用原始转换的内容，不用 Confluence 返回的
            updated_content = images_html + storage_content

            updated_page = await client.update_page(
                page_id=page.id,
                title=page.title,
                body_storage=updated_content,
                version_number=page_info.version.number if page_info.version else 1
            )

            print('   ✅ 页面更新成功')
            print()

            page = updated_page

        else:
            # 使用代码块方案
            print('='*80)
            print('使用代码块方案')
            print('='*80)

            converter = MarkdownToStorageConverter()
            storage_content = converter.convert(markdown_content, use_mermaid_images=False)

            print('创建 Confluence 页面...')
            page = await client.create_page(
                space_key=test_space,
                title=f'Wiki.js POC 测试案例 - {timestamp}',
                body_storage=storage_content,
                parent_id=test_parent_id
            )
            print()

        print('='*80)
        print('✅ 页面创建成功!')
        print('='*80)
        print(f'页面 ID: {page.id}')
        print(f'标题: {page.title}')
        print(f'空间: {page.space.key}')
        print(f'版本: {page.version.number if page.version else 1}')
        base_url = os.getenv('CONFLUENCE_BASE_URL')
        print(f'URL: {base_url}{page.web_url}')
        print()
        print('💡 提示:')
        if use_local_render and mermaid_blocks:
            print('   - Mermaid 图表已本地渲染并上传为图片')
            print('   - 图片显示在页面顶部')
            print('   - 源代码以可折叠代码块形式保留')
        else:
            print('   - Mermaid 代码以可折叠代码块形式显示')
            print('   - 点击按钮可在 Mermaid Live Editor 中查看')
        print('   - 访问上面的 URL 查看效果')


if __name__ == '__main__':
    asyncio.run(create_page_with_local_mermaid())
