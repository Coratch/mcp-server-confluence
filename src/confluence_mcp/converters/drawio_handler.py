"""Draw.io 图表双向转换处理器

处理 Confluence Storage Format 中的 draw.io 宏与 Markdown 之间的双向转换。
draw.io 图表以附件方式存储，宏通过 diagramName/attachment 参数引用。
"""
import re
from typing import Dict, List, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)


class DrawioHandler:
    """Draw.io 图表转换处理器"""

    # Confluence Storage Format 中的 draw.io 宏模式
    CONFLUENCE_DRAWIO_PATTERN = re.compile(
        r'<ac:structured-macro[^>]*\bac:name="drawio"[^>]*>'
        r'(.*?)'
        r'</ac:structured-macro>',
        re.DOTALL | re.MULTILINE
    )

    # 从宏参数中提取 diagramName
    DIAGRAM_NAME_PATTERN = re.compile(
        r'<ac:parameter\s+ac:name="diagramName"[^>]*>(.*?)</ac:parameter>',
        re.DOTALL
    )

    # 从宏参数中提取 attachment（图表附件名）
    ATTACHMENT_PATTERN = re.compile(
        r'<ac:parameter\s+ac:name="attachment"[^>]*>(.*?)</ac:parameter>',
        re.DOTALL
    )

    # Markdown 中的 draw.io 标记模式（用于反向转换）
    MD_DRAWIO_PATTERN = re.compile(
        r'> ?\U0001f4ca ?\*\*Draw\.io (?:图表|Diagram)\*\*[：:]\s*(.+?)$',
        re.MULTILINE
    )

    @classmethod
    def extract_confluence_drawio(cls, confluence_content: str) -> List[Tuple[str, Dict[str, str]]]:
        """从 Confluence Storage Format 中提取所有 draw.io 宏

        Args:
            confluence_content: Confluence Storage Format 内容

        Returns:
            (原始宏文本, 参数字典) 的列表，参数字典包含 diagramName、attachment 等
        """
        results = []
        for match in cls.CONFLUENCE_DRAWIO_PATTERN.finditer(confluence_content):
            full_macro = match.group(0)
            inner_content = match.group(1)

            params = cls._extract_params(inner_content)
            if params:
                logger.debug(f"提取到 draw.io 图表: {params.get('diagramName', 'unknown')}")
                results.append((full_macro, params))

        return results

    @classmethod
    def _extract_params(cls, macro_inner: str) -> Dict[str, str]:
        """从宏内部内容中提取参数

        Args:
            macro_inner: ac:structured-macro 标签内部的内容

        Returns:
            参数字典
        """
        params = {}

        # 通用参数提取
        param_pattern = re.compile(
            r'<ac:parameter\s+ac:name="([^"]+)"[^>]*>(.*?)</ac:parameter>',
            re.DOTALL
        )
        for param_match in param_pattern.finditer(macro_inner):
            params[param_match.group(1)] = param_match.group(2).strip()

        return params

    @classmethod
    def drawio_to_markdown(cls, diagram_name: str) -> str:
        """将 draw.io 图表信息转换为 Markdown 格式

        Args:
            diagram_name: 图表名称（附件文件名）

        Returns:
            Markdown 格式的描述文本
        """
        return (
            f'> \U0001f4ca **Draw.io 图表**: {diagram_name}\n'
            f'> [draw.io 在线编辑器](https://app.diagrams.net/)'
        )

    @classmethod
    def markdown_to_drawio_macro(cls, diagram_name: str) -> str:
        """将 Markdown 中的 draw.io 标记还原为 Confluence 宏

        Args:
            diagram_name: 图表名称（附件文件名）

        Returns:
            Confluence Storage Format 的 draw.io 宏
        """
        return (
            '<ac:structured-macro ac:name="drawio" ac:schema-version="1">'
            f'<ac:parameter ac:name="diagramName">{diagram_name}</ac:parameter>'
            f'<ac:parameter ac:name="attachment">{diagram_name}</ac:parameter>'
            '</ac:structured-macro>'
        )

    @classmethod
    def extract_markdown_drawio(cls, markdown_content: str) -> List[Tuple[str, str]]:
        """从 Markdown 中提取所有 draw.io 图表标记

        Args:
            markdown_content: Markdown 内容

        Returns:
            (原始标记文本, 图表名称) 的列表
        """
        results = []
        for match in cls.MD_DRAWIO_PATTERN.finditer(markdown_content):
            full_match = match.group(0)
            diagram_name = match.group(1).strip()

            # 检查下一行是否有 draw.io 编辑器链接，如果有则一起匹配
            link_line_pattern = re.compile(
                re.escape(full_match) + r'\n> ?\[draw\.io[^\]]*\]\([^\)]+\)',
                re.MULTILINE
            )
            link_match = link_line_pattern.search(markdown_content)
            if link_match:
                full_match = link_match.group(0)

            logger.debug(f"提取到 Markdown draw.io 标记: {diagram_name}")
            results.append((full_match, diagram_name))

        return results
