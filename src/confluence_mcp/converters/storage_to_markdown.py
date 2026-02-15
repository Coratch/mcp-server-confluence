"""Storage Format 到 Markdown 转换器"""
import re
from typing import Optional

import html2text
from bs4 import BeautifulSoup

from ..utils.logger import get_logger
from .mermaid_handler import MermaidHandler

logger = get_logger(__name__)


class StorageToMarkdownConverter:
    """Storage Format 到 Markdown 转换器"""

    def __init__(self) -> None:
        """初始化转换器"""
        # 配置 html2text
        self.h2t = html2text.HTML2Text()
        self.h2t.body_width = 0  # 不自动换行
        self.h2t.ignore_links = False
        self.h2t.ignore_images = False
        self.h2t.ignore_emphasis = False
        self.h2t.skip_internal_links = False
        self.h2t.inline_links = True
        self.h2t.protect_links = True
        self.h2t.mark_code = True
        self.h2t.wrap_links = False  # 不换行链接
        self.h2t.wrap_list_items = False  # 不换行列表项
        self.h2t.escape_snob = True  # 不转义特殊字符

    def convert(self, storage_content: str, page_title: Optional[str] = None) -> str:
        """转换 Storage Format 到 Markdown

        Args:
            storage_content: Confluence Storage Format 内容
            page_title: 页面标题（可选，用于添加元数据头）

        Returns:
            Markdown 内容
        """
        logger.info("开始转换 Storage Format 到 Markdown")

        # 1. 转换 Mermaid 宏为临时占位符（避免被 html2text 处理）
        mermaid_blocks = MermaidHandler.extract_confluence_mermaid(storage_content)
        mermaid_placeholders = {}

        for idx, (original, code) in enumerate(mermaid_blocks):
            placeholder = f"___MERMAID_BLOCK_{idx}___"
            mermaid_placeholders[placeholder] = code
            storage_content = storage_content.replace(original, placeholder)

        # 2. 处理其他 Confluence 宏，提取代码块
        storage_content, code_placeholders = self._process_confluence_macros(storage_content)

        # 3. 使用 html2text 转换 XHTML 到 Markdown
        markdown_content = self.h2t.handle(storage_content)

        # 4. 恢复 Mermaid 代码块（处理转义的占位符）
        for placeholder, code in mermaid_placeholders.items():
            mermaid_block = f'```mermaid\n{code}\n```'
            # 尝试直接替换
            markdown_content = markdown_content.replace(placeholder, mermaid_block)
            # 也尝试替换转义后的版本
            escaped_placeholder = placeholder.replace('_', r'\_')
            markdown_content = markdown_content.replace(escaped_placeholder, mermaid_block)

        # 5. 恢复代码块（处理转义的占位符）
        for placeholder, (language, code) in code_placeholders.items():
            code_block = f'```{language}\n{code}\n```'
            # 尝试直接替换
            markdown_content = markdown_content.replace(placeholder, code_block)
            # 也尝试替换转义后的版本
            escaped_placeholder = placeholder.replace('_', r'\_')
            markdown_content = markdown_content.replace(escaped_placeholder, code_block)

        # 6. 后处理清理
        markdown_content = self._post_process(markdown_content)

        # 7. 添加元数据头（可选）
        if page_title:
            metadata = f"---\ntitle: {page_title}\n---\n\n"
            markdown_content = metadata + markdown_content

        logger.info("转换完成")
        return markdown_content

    def _process_confluence_macros(self, content: str):
        """处理 Confluence 宏

        Args:
            content: Storage Format 内容

        Returns:
            (处理后的内容, 代码块占位符字典)
        """
        soup = BeautifulSoup(content, "html.parser")
        code_placeholders = {}
        code_counter = 0

        # 处理 expand 宏（可折叠内容）- 先处理，避免影响内部的 code 宏
        for macro in soup.find_all("ac:structured-macro", {"ac:name": "expand"}):
            # 提取标题
            title_param = macro.find("ac:parameter", {"ac:name": "title"})
            title = title_param.get_text() if title_param else "展开内容"

            # 提取内容
            body = macro.find("ac:rich-text-body")
            if body:
                # 保留内部内容，但移除 expand 包装
                # 用注释标记可折叠区域
                body_html = ''.join(str(child) for child in body.children)
                replacement = f'<!-- {title} -->\n{body_html}\n<!-- /expand -->'
                macro.replace_with(BeautifulSoup(replacement, 'html.parser'))

        # 重新解析（因为我们修改了结构）
        soup = BeautifulSoup(str(soup), "html.parser")

        # 处理 info/warning/note 宏
        for macro in soup.find_all("ac:structured-macro"):
            macro_name = macro.get("ac:name", "")

            if macro_name in ["info", "note", "tip"]:
                body = macro.find("ac:rich-text-body")
                if body:
                    # 转换为引用块
                    body_text = str(body)
                    macro.replace_with(BeautifulSoup(f'<blockquote><strong>ℹ️ Info:</strong><br/>{body_text}</blockquote>', 'html.parser'))

            elif macro_name == "warning":
                body = macro.find("ac:rich-text-body")
                if body:
                    body_text = str(body)
                    macro.replace_with(BeautifulSoup(f'<blockquote><strong>⚠️ Warning:</strong><br/>{body_text}</blockquote>', 'html.parser'))

            elif macro_name == "code":
                # 处理代码块 - 使用占位符
                plain_text_body = macro.find("ac:plain-text-body")
                if plain_text_body:
                    # 提取 CDATA 内容
                    code_content = plain_text_body.get_text()
                    language = ""

                    # 尝试获取语言参数
                    lang_param = macro.find("ac:parameter", {"ac:name": "language"})
                    if lang_param:
                        language = lang_param.get_text()

                    # 创建占位符
                    placeholder = f"___CODE_PLACEHOLDER_{code_counter}___"
                    code_placeholders[placeholder] = (language, code_content)
                    code_counter += 1

                    # 替换为占位符
                    macro.replace_with(placeholder)

        return str(soup), code_placeholders

    def _post_process(self, markdown_content: str) -> str:
        """后处理 Markdown 内容

        Args:
            markdown_content: 原始 Markdown 内容

        Returns:
            清理后的内容
        """
        # 1. 修复加粗文本后的空格: "**文本** ：" -> "**文本**："
        markdown_content = re.sub(r'\*\*([^*]+)\*\* ([：:：])', r'**\1**\2', markdown_content)

        # 2. 修复标题编号转义: "#### 1\." -> "#### 1."
        markdown_content = re.sub(r'^(#{1,6}) (\d+)\\\.', r'\1 \2.', markdown_content, flags=re.MULTILINE)

        # 3. 修复列表项: 将 "\-" 转换回 "- "，并确保每个列表项独立成行
        # 先找出所有的 "\- " 模式
        lines = markdown_content.split('\n')
        processed_lines = []

        for line in lines:
            # 如果行中包含多个 "\- "，拆分为多行
            if '\\-' in line:
                # 检查是否是列表行（不在代码块中）
                if not line.strip().startswith('```'):
                    # 将 "\- " 替换为换行 + "- "
                    parts = line.split('\\-')
                    if len(parts) > 1:
                        # 第一部分保持原样
                        processed_lines.append(parts[0].rstrip())
                        # 其余部分作为列表项
                        for part in parts[1:]:
                            if part.strip():
                                processed_lines.append('- ' + part.strip())
                    else:
                        processed_lines.append(line)
                else:
                    processed_lines.append(line)
            else:
                processed_lines.append(line)

        markdown_content = '\n'.join(processed_lines)

        # 4. 修复分隔线: "* * *" -> "---"
        markdown_content = re.sub(r'^\* \* \*$', '---', markdown_content, flags=re.MULTILINE)

        # 5. 移除代码块结束后多余的空行
        markdown_content = re.sub(r'```\n\n\n', '```\n\n', markdown_content)

        # 6. 移除多余的空行（超过 2 个连续空行）
        markdown_content = re.sub(r'\n{3,}', '\n\n', markdown_content)

        # 7. 清理行尾空格
        lines = markdown_content.split('\n')
        lines = [line.rstrip() for line in lines]
        markdown_content = '\n'.join(lines)

        # 8. 确保文件以单个换行符结尾
        markdown_content = markdown_content.strip() + '\n'

        return markdown_content
