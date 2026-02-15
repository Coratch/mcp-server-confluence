"""Mermaid 转图片转换器"""
import base64
import re
import zlib
from typing import List, Tuple
from urllib.parse import quote

from ..utils.logger import get_logger

logger = get_logger(__name__)


class MermaidToImageConverter:
    """Mermaid 代码转换为 mermaid.ink 图片链接"""

    # Mermaid 代码块正则
    MD_MERMAID_PATTERN = re.compile(r'```mermaid\s*\n(.*?)\n```', re.DOTALL)

    @staticmethod
    def encode_mermaid(mermaid_code: str) -> str:
        """将 Mermaid 代码编码为 mermaid.ink URL

        Args:
            mermaid_code: Mermaid 代码

        Returns:
            mermaid.ink 图片 URL
        """
        # 使用 pako 压缩算法（zlib）
        compressed = zlib.compress(mermaid_code.encode('utf-8'), level=9)
        # Base64 编码
        encoded = base64.urlsafe_b64encode(compressed).decode('utf-8')
        # 构建 URL
        url = f"https://mermaid.ink/img/{encoded}?type=png"
        return url

    @classmethod
    def extract_and_convert(cls, markdown_content: str) -> Tuple[str, List[Tuple[str, str, str]]]:
        """提取 Mermaid 代码块并转换为图片链接

        Args:
            markdown_content: Markdown 内容

        Returns:
            (转换后的内容, [(原始代码块, Mermaid代码, 图片URL)])
        """
        mermaid_info = []

        def replace_with_image(match):
            mermaid_code = match.group(1).strip()
            image_url = cls.encode_mermaid(mermaid_code)

            # 保存信息
            mermaid_info.append((match.group(0), mermaid_code, image_url))

            # 替换为图片 Markdown
            return f"![Mermaid Diagram]({image_url})"

        # 替换所有 Mermaid 代码块
        converted_content = cls.MD_MERMAID_PATTERN.sub(replace_with_image, markdown_content)

        logger.info(f"转换了 {len(mermaid_info)} 个 Mermaid 图表为图片")
        return converted_content, mermaid_info

    @classmethod
    def convert_to_confluence_format(cls, markdown_content: str) -> Tuple[str, List[dict]]:
        """转换 Mermaid 为 Confluence 可展示的格式

        包含：
        1. 图片预览
        2. 原始代码（折叠）
        3. 在线编辑链接

        Args:
            markdown_content: Markdown 内容

        Returns:
            (转换后的内容, Mermaid信息列表)
        """
        mermaid_details = []

        def replace_with_full_format(match):
            mermaid_code = match.group(1).strip()
            image_url = cls.encode_mermaid(mermaid_code)

            # 生成 Mermaid Live Editor 链接
            # 使用 pako 编码
            compressed = zlib.compress(mermaid_code.encode('utf-8'), level=9)
            encoded = base64.urlsafe_b64encode(compressed).decode('utf-8')
            live_editor_url = f"https://mermaid.live/edit#pako:{encoded}"

            # 保存详细信息
            mermaid_details.append({
                'code': mermaid_code,
                'image_url': image_url,
                'live_editor_url': live_editor_url
            })

            # 生成完整格式（图片 + 代码 + 链接）
            replacement = f"""
## Mermaid 图表

### 预览

![Mermaid Diagram]({image_url})

### 原始代码

```
{mermaid_code}
```

### 在线编辑

🔗 [在 Mermaid Live Editor 中打开]({live_editor_url})

---
"""
            return replacement

        # 替换所有 Mermaid 代码块
        converted_content = cls.MD_MERMAID_PATTERN.sub(replace_with_full_format, markdown_content)

        logger.info(f"转换了 {len(mermaid_details)} 个 Mermaid 图表为完整格式")
        return converted_content, mermaid_details
