"""测试 MCP create_confluence_page 功能"""
import asyncio
import os
from datetime import datetime

from dotenv import load_dotenv

from confluence_mcp.api.client import ConfluenceClient
from confluence_mcp.config import get_config
from confluence_mcp.converters.markdown_to_storage import MarkdownToStorageConverter
from confluence_mcp.converters.mermaid_handler import MermaidHandler
from confluence_mcp.converters.mermaid_renderer import MermaidRenderer

load_dotenv()


async def test_create_page_with_mermaid():
    """测试创建包含 Mermaid 的页面（模拟 MCP tool 逻辑）"""

    # 读取示例 Markdown
    with open('examples/markdown_example.md', 'r', encoding='utf-8') as f:
        markdown_content = f.read()

    print('读取 Markdown 文件成功')
    print(f'内容长度: {len(markdown_content)} 字符')
    print()

    # 获取配置
    config = get_config()
    test_space = config.confluence_default_space
    test_parent_id = os.getenv('CONFLUENCE_TEST_PARENT_PAGE_ID')

    print(f'目标空间: {test_space}')
    print(f'父页面 ID: {test_parent_id}')
    print()

    # 检查 Mermaid
    mermaid_blocks = MermaidHandler.extract_mermaid_blocks(markdown_content)
    has_mermaid = len(mermaid_blocks) > 0
    use_local_render = has_mermaid and MermaidRenderer.is_available()

    if use_local_render:
        print(f'✅ 使用本地渲染方案（检测到 {len(mermaid_blocks)} 个 Mermaid 图表）')
    elif has_mermaid:
        print(f'⚠️  使用代码块方案（检测到 {len(mermaid_blocks)} 个 Mermaid 图表）')
    print()

    # 转换 Markdown
    converter = MarkdownToStorageConverter()
    storage_content = converter.convert(markdown_content, use_mermaid_images=False)

    print('=' * 80)
    print('创建 Confluence 页面')
    print('=' * 80)

    async with ConfluenceClient() as client:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # 创建页面
        page = await client.create_page(
            space_key=test_space,
            title=f'MCP 测试页面 - {timestamp}',
            body_storage=storage_content,
            parent_id=test_parent_id,
        )

        print(f'✅ 页面创建成功: {page.id}')
        print()

        # 如果使用本地渲染，上传图片
        if use_local_render:
            print(f'渲染并上传 {len(mermaid_blocks)} 个 Mermaid 图表...')

            import httpx
            upload_headers = {
                "Authorization": f"Bearer {config.confluence_api_token}",
                "X-Atlassian-Token": "no-check",
            }

            uploaded_images = []
            for idx, (original, code) in enumerate(mermaid_blocks):
                print(f'  处理图表 {idx + 1}/{len(mermaid_blocks)}...')

                png_path = MermaidRenderer.render_to_png(code)

                if png_path and os.path.exists(png_path):
                    try:
                        filename = f"mermaid-diagram-{idx + 1}.png"

                        with open(png_path, "rb") as img:
                            files = {"file": (filename, img, "image/png")}

                            async with httpx.AsyncClient(timeout=30.0) as http_client:
                                response = await http_client.post(
                                    f"{config.confluence_base_url}/rest/api/content/{page.id}/child/attachment",
                                    files=files,
                                    headers=upload_headers,
                                )

                                if response.status_code in [200, 201]:
                                    print(f'    ✅ 图片上传成功: {filename}')
                                    uploaded_images.append(filename)
                                else:
                                    print(f'    ❌ 上传失败: {response.status_code}')

                    finally:
                        if os.path.exists(png_path):
                            os.remove(png_path)
                else:
                    print(f'    ❌ 渲染失败')

            # 更新页面插入图片
            if uploaded_images:
                print()
                print('更新页面，插入图片...')

                page_info = await client.get_page(page.id)

                images_html = "<h2>📊 Mermaid 图表预览</h2>\n"
                for filename in uploaded_images:
                    images_html += f'<p><ac:image><ri:attachment ri:filename="{filename}" /></ac:image></p>\n'

                images_html += "<hr />\n"

                updated_content = images_html + storage_content

                page = await client.update_page(
                    page_id=page.id,
                    title=page.title,
                    body_storage=updated_content,
                    version_number=page_info.version.number if page_info.version else 1,
                )

                print('✅ 页面更新成功')

        print()
        print('=' * 80)
        print('✅ 测试完成!')
        print('=' * 80)
        print(f'页面 ID: {page.id}')
        print(f'标题: {page.title}')
        print(f'空间: {page.space.key}')
        print(f'版本: {page.version.number if page.version else 1}')
        print(f'URL: {config.confluence_base_url}{page.web_url}')
        print(f'Mermaid 渲染方式: {"local_image" if use_local_render else "code_block"}')
        print(f'Mermaid 图表数量: {len(mermaid_blocks) if has_mermaid else 0}')


if __name__ == '__main__':
    asyncio.run(test_create_page_with_mermaid())

