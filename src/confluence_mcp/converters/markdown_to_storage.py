"""Markdown 到 Storage Format 转换器"""
import re
from typing import Any, Dict, List, Optional, Tuple

import markdown
from bs4 import BeautifulSoup, NavigableString, Tag

from ..utils.logger import get_logger
from .mermaid_to_image import MermaidToImageConverter

logger = get_logger(__name__)


class MarkdownToStorageConverter:
    """Markdown 到 Storage Format 转换器"""

    def __init__(self) -> None:
        """初始化转换器"""
        # 配置 markdown 解析器
        # 注意：不使用 codehilite，因为它会添加语法高亮的 span 标签，
        # 而且不会在 HTML 中保留语言信息
        self.md = markdown.Markdown(
            extensions=[
                'extra',  # 支持表格、代码块等
                'fenced_code',  # 围栏代码块（保留语言信息）
                'tables',  # 表格
            ]
        )

    async def convert(
        self, 
        markdown_content: str, 
        use_local_mermaid: bool = True,
        page_id: Optional[str] = None,
        confluence_client: Optional[Any] = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """转换 Markdown 到 Storage Format

        Args:
            markdown_content: Markdown 内容
            use_local_mermaid: 是否使用本地 Mermaid 渲染（需要 mmdc）
            page_id: Confluence 页面 ID（用于上传附件）
            confluence_client: Confluence API 客户端（用于上传附件）

        Returns:
            (Confluence Storage Format 内容, 附件信息列表)
        """
        logger.info("开始转换 Markdown 到 Storage Format")
        attachments = []

        # 1. 移除元数据头（如果存在）
        markdown_content = self._remove_metadata(markdown_content)

        # 2. 处理 Mermaid 代码块
        mermaid_placeholders = {}
        
        if use_local_mermaid and page_id and confluence_client:
            # 尝试本地渲染
            from .mermaid_local_renderer import MermaidLocalRenderer
            
            if MermaidLocalRenderer.check_mmdc_available():
                logger.info("使用本地 mermaid-cli 渲染 Mermaid 图表")
                
                # 渲染所有 Mermaid 代码块为临时图片
                temp_content, image_info = await MermaidLocalRenderer.render_all_to_temp(
                    markdown_content
                )
                
                # 上传图片作为附件
                for info in image_info:
                    try:
                        # 上传附件
                        attachment = await confluence_client.upload_attachment(
                            page_id=page_id,
                            file_path=info["path"],
                            file_name=info["filename"],
                            comment="Mermaid diagram rendered locally"
                        )
                        
                        # 记录附件信息
                        attachments.append(attachment)
                        
                        # 准备 Confluence 图片标记
                        image_tag = (
                            f'<ac:image ac:align="center" ac:layout="center">'
                            f'<ri:attachment ri:filename="{info["filename"]}" />'
                            f'</ac:image>'
                        )
                        
                        # 记录占位符映射
                        placeholder = f"[[MERMAID_IMAGE_{info['index']}]]"
                        mermaid_placeholders[placeholder] = image_tag
                        
                        logger.info(f"上传 Mermaid 图片成功: {info['filename']}")
                        
                    except Exception as e:
                        logger.error(f"上传 Mermaid 图片失败: {e}")
                        # 降级到代码块显示
                        placeholder = f"[[MERMAID_IMAGE_{info['index']}]]"
                        mermaid_placeholders[placeholder] = self._create_mermaid_code_block(info["code"])
                
                markdown_content = temp_content
                
                # 清理临时文件
                import shutil
                from pathlib import Path
                if image_info:
                    temp_dir = Path(image_info[0]["path"]).parent
                    try:
                        shutil.rmtree(temp_dir)
                    except:
                        pass
            else:
                logger.warning("mermaid-cli 不可用，使用代码块显示")
                use_local_mermaid = False
        
        # 如果不使用本地渲染，使用代码块显示
        if not use_local_mermaid or not mermaid_placeholders:
            from .mermaid_handler import MermaidHandler
            mermaid_blocks = MermaidHandler.extract_mermaid_blocks(markdown_content)
            
            for idx, (original, code) in enumerate(mermaid_blocks):
                placeholder = f"MERMAIDBLOCK{idx}PLACEHOLDER"
                mermaid_placeholders[placeholder] = self._create_mermaid_code_block(code)
                markdown_content = markdown_content.replace(original, placeholder)

        # 3. 转换 Markdown 到 HTML
        html_content = self.md.convert(markdown_content)

        # 4. 替换 Mermaid 占位符
        for placeholder, replacement in mermaid_placeholders.items():
            # 替换 <p> 包裹的占位符
            html_content = html_content.replace(f'<p>{placeholder}</p>', replacement)
            # 替换其他情况
            html_content = html_content.replace(placeholder, replacement)

        # 5. 转换 HTML 到 Confluence Storage Format
        storage_content = self._html_to_storage(html_content)

        logger.info(f"转换完成，上传了 {len(attachments)} 个附件")
        return storage_content, attachments

    def _create_mermaid_code_block(self, code: str) -> str:
        """创建 Mermaid 代码块的 Confluence 格式

        Args:
            code: Mermaid 代码

        Returns:
            Confluence Storage Format 代码块
        """
        import base64
        import zlib
        
        # 生成 Mermaid Live Editor 链接
        compressed = zlib.compress(code.encode('utf-8'), level=9)
        encoded = base64.urlsafe_b64encode(compressed).decode('utf-8')
        live_editor_url = f"https://mermaid.live/edit#pako:{encoded}"

        # 使用可折叠的代码块 + 在线编辑按钮
        return (
            '<ac:structured-macro ac:name="expand">'
            '<ac:parameter ac:name="title">📝 点击展开查看 Mermaid 代码</ac:parameter>'
            '<ac:rich-text-body>'
            '<ac:structured-macro ac:name="code">'
            '<ac:parameter ac:name="language">mermaid</ac:parameter>'
            '<ac:parameter ac:name="title">Mermaid 源代码</ac:parameter>'
            '<ac:plain-text-body><![CDATA['
            f'{code}'
            ']]></ac:plain-text-body>'
            '</ac:structured-macro>'
            '</ac:rich-text-body>'
            '</ac:structured-macro>'
            f'<p style="margin-top: 15px;">'
            f'<a href="{live_editor_url}" target="_blank" '
            f'style="display: inline-block; padding: 10px 20px; background-color: #0052CC; '
            f'color: white; text-decoration: none; border-radius: 3px; font-weight: bold;">'
            f'🎨 在 Mermaid Live Editor 中查看和编辑'
            f'</a>'
            f'</p>'
        )

    def _remove_metadata(self, markdown_content: str) -> str:
        """移除 YAML 元数据头

        Args:
            markdown_content: Markdown 内容

        Returns:
            移除元数据后的内容
        """
        # 匹配 YAML front matter
        pattern = re.compile(r'^---\s*\n.*?\n---\s*\n', re.DOTALL | re.MULTILINE)
        return pattern.sub('', markdown_content)

    def _html_to_storage(self, html_content: str) -> str:
        """转换 HTML 到 Confluence Storage Format

        Args:
            html_content: HTML 内容

        Returns:
            Storage Format 内容
        """
        soup = BeautifulSoup(html_content, 'html.parser')

        # 处理代码块
        self._process_code_blocks(soup)

        # 处理表格
        self._process_tables(soup)

        # 处理引用块
        self._process_blockquotes(soup)

        # 处理链接
        self._process_links(soup)

        return str(soup)

    def _process_code_blocks(self, soup: BeautifulSoup) -> None:
        """处理代码块，转换为 Confluence 代码宏

        Args:
            soup: BeautifulSoup 对象
        """
        # 处理 codehilite 生成的代码块
        for div in soup.find_all('div', class_='codehilite'):
            pre = div.find('pre')
            if pre:
                code = pre.find('code')
                if code:
                    # 提取纯文本内容（去除语法高亮的 span 标签）
                    code_content = code.get_text()

                    # 尝试从 div 的 class 中提取语言
                    language = ""
                    div_classes = div.get('class', [])
                    for cls in div_classes:
                        if cls.startswith('language-'):
                            language = cls.replace('language-', '')
                            break

                    # 如果 div 没有语言信息，尝试从 code 标签获取
                    if not language and code.get('class'):
                        code_classes = code.get('class', [])
                        for cls in code_classes:
                            if cls.startswith('language-'):
                                language = cls.replace('language-', '')
                                break

                    # 创建 Confluence 代码宏
                    macro = soup.new_tag('ac:structured-macro')
                    macro['ac:name'] = 'code'

                    # 添加语言参数
                    if language:
                        param = soup.new_tag('ac:parameter')
                        param['ac:name'] = 'language'
                        param.string = language
                        macro.append(param)

                    # 添加代码内容（使用 CDATA）
                    body = soup.new_tag('ac:plain-text-body')
                    cdata = f'<![CDATA[{code_content}]]>'
                    body.append(BeautifulSoup(cdata, 'html.parser'))
                    macro.append(body)

                    div.replace_with(macro)

        # 处理普通的 pre/code 代码块（fenced_code 生成的）
        for pre in soup.find_all('pre'):
            code = pre.find('code')
            if code:
                # 提取代码内容
                code_content = code.get_text()

                # 跳过 Mermaid 占位符（这些会在后面单独处理）
                if code_content.strip().startswith('MERMAIDBLOCK') and code_content.strip().endswith('PLACEHOLDER'):
                    continue

                # 提取语言（如果有）
                language = ""
                if code.get('class'):
                    classes = code.get('class', [])
                    for cls in classes:
                        if cls.startswith('language-'):
                            language = cls.replace('language-', '')
                            break

                # 创建 Confluence 代码宏
                macro = soup.new_tag('ac:structured-macro')
                macro['ac:name'] = 'code'

                # 添加语言参数
                if language:
                    param = soup.new_tag('ac:parameter')
                    param['ac:name'] = 'language'
                    param.string = language
                    macro.append(param)

                # 添加代码内容（使用 CDATA）
                body = soup.new_tag('ac:plain-text-body')
                cdata = f'<![CDATA[{code_content}]]>'
                body.append(BeautifulSoup(cdata, 'html.parser'))
                macro.append(body)

                pre.replace_with(macro)

    def _process_tables(self, soup: BeautifulSoup) -> None:
        """处理表格，确保符合 Confluence 格式

        Args:
            soup: BeautifulSoup 对象
        """
        # Confluence 支持标准 HTML 表格，通常不需要特殊处理
        # 但可以添加一些样式或属性
        for table in soup.find_all('table'):
            # 确保表格有边框
            if not table.get('border'):
                table['border'] = '1'

    def _process_blockquotes(self, soup: BeautifulSoup) -> None:
        """处理引用块

        Args:
            soup: BeautifulSoup 对象
        """
        for blockquote in soup.find_all('blockquote'):
            # 检查是否是特殊的 info/warning 块
            text = blockquote.get_text()

            if text.startswith('ℹ️ Info:') or text.startswith('Info:'):
                self._convert_to_info_macro(blockquote, soup)
            elif text.startswith('��️ Warning:') or text.startswith('Warning:'):
                self._convert_to_warning_macro(blockquote, soup)

    def _convert_to_info_macro(self, blockquote: Tag, soup: BeautifulSoup) -> None:
        """转换为 info 宏

        Args:
            blockquote: blockquote 标签
            soup: BeautifulSoup 对象
        """
        # 移除标题
        content = str(blockquote)
        content = re.sub(r'<strong>.*?Info:.*?</strong><br/>', '', content)

        macro = soup.new_tag('ac:structured-macro')
        macro['ac:name'] = 'info'

        body = soup.new_tag('ac:rich-text-body')
        body.append(BeautifulSoup(content, 'html.parser'))
        macro.append(body)

        blockquote.replace_with(macro)

    def _convert_to_warning_macro(self, blockquote: Tag, soup: BeautifulSoup) -> None:
        """转换为 warning 宏

        Args:
            blockquote: blockquote 标签
            soup: BeautifulSoup 对象
        """
        # 移除标题
        content = str(blockquote)
        content = re.sub(r'<strong>.*?Warning:.*?</strong><br/>', '', content)

        macro = soup.new_tag('ac:structured-macro')
        macro['ac:name'] = 'warning'

        body = soup.new_tag('ac:rich-text-body')
        body.append(BeautifulSoup(content, 'html.parser'))
        macro.append(body)

        blockquote.replace_with(macro)

    def _process_links(self, soup: BeautifulSoup) -> None:
        """处理链接，转换为 Confluence 链接格式

        Args:
            soup: BeautifulSoup 对象
        """
        for link in soup.find_all('a'):
            href = link.get('href', '')

            # 如果是内部 Confluence 链接，可以转换为 ac:link
            # 这里保持简单，使用标准 HTML 链接
            # 未来可以扩展支持 Confluence 特定的链接格式
            pass
