"""测试 Mermaid 转换功能"""
import pytest

from confluence_mcp.converters.mermaid_handler import MermaidHandler


class TestMermaidHandler:
    """测试 MermaidHandler 类"""

    def test_markdown_to_confluence_simple(self):
        """测试简单的 Markdown 到 Confluence 转换"""
        markdown = """
# 测试

```mermaid
graph TD
    A --> B
```

内容
"""
        result = MermaidHandler.markdown_to_confluence(markdown)

        assert '<ac:structured-macro ac:name="mermaid">' in result
        assert '<ac:plain-text-body><![CDATA[' in result
        assert 'graph TD' in result
        assert 'A --> B' in result

    def test_confluence_to_markdown_simple(self):
        """测试简单的 Confluence 到 Markdown 转换"""
        confluence = """
<p>测试</p>
<ac:structured-macro ac:name="mermaid">
<ac:plain-text-body><![CDATA[
graph TD
    A --> B
]]></ac:plain-text-body>
</ac:structured-macro>
<p>内容</p>
"""
        result = MermaidHandler.confluence_to_markdown(confluence)

        assert '```mermaid' in result
        assert 'graph TD' in result
        assert 'A --> B' in result
        assert '```' in result

    def test_multiple_mermaid_blocks(self):
        """测试多个 Mermaid 代码块"""
        markdown = """
```mermaid
graph TD
    A --> B
```

文本

```mermaid
sequenceDiagram
    Alice->>Bob: Hello
```
"""
        result = MermaidHandler.markdown_to_confluence(markdown)

        # 应该有两个宏
        assert result.count('<ac:structured-macro ac:name="mermaid">') == 2
        assert 'graph TD' in result
        assert 'sequenceDiagram' in result

    def test_extract_mermaid_blocks(self):
        """测试提取 Mermaid 代码块"""
        markdown = """
```mermaid
graph TD
    A --> B
```

```mermaid
sequenceDiagram
    Alice->>Bob: Hello
```
"""
        blocks = MermaidHandler.extract_mermaid_blocks(markdown)

        assert len(blocks) == 2
        assert 'graph TD' in blocks[0][1]
        assert 'sequenceDiagram' in blocks[1][1]

    def test_extract_confluence_mermaid(self):
        """测试提取 Confluence Mermaid 宏"""
        confluence = """
<ac:structured-macro ac:name="mermaid">
<ac:plain-text-body><![CDATA[
graph TD
    A --> B
]]></ac:plain-text-body>
</ac:structured-macro>

<ac:structured-macro ac:name="mermaid">
<ac:plain-text-body><![CDATA[
sequenceDiagram
    Alice->>Bob: Hello
]]></ac:plain-text-body>
</ac:structured-macro>
"""
        macros = MermaidHandler.extract_confluence_mermaid(confluence)

        assert len(macros) == 2
        assert 'graph TD' in macros[0][1]
        assert 'sequenceDiagram' in macros[1][1]

    def test_roundtrip_conversion(self):
        """测试往返转换"""
        original_markdown = """```mermaid
graph TD
    A --> B
    B --> C
```"""

        # Markdown -> Confluence
        confluence = MermaidHandler.markdown_to_confluence(original_markdown)

        # Confluence -> Markdown
        result_markdown = MermaidHandler.confluence_to_markdown(confluence)

        # 验证内容保持一致
        assert 'graph TD' in result_markdown
        assert 'A --> B' in result_markdown
        assert 'B --> C' in result_markdown
        assert '```mermaid' in result_markdown
