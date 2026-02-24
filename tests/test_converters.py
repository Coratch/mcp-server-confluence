"""Storage Format ↔ Markdown 转换器测试

基于真实 wiki 使用场景：技术设计文档、API 文档、会议纪要等
"""
import pytest

from confluence_mcp.converters.storage_to_markdown import StorageToMarkdownConverter
from confluence_mcp.converters.markdown_to_storage import MarkdownToStorageConverter

from tests.sample_data import (
    TECH_DESIGN_STORAGE,
    API_DOC_STORAGE,
    MEETING_NOTES_STORAGE,
    ARCHITECTURE_MARKDOWN,
    SIMPLE_PAGE_MARKDOWN,
    COMPLEX_TABLE_MARKDOWN,
    DRAWIO_STORAGE,
    MULTI_DRAWIO_STORAGE,
    MIXED_DIAGRAM_STORAGE,
    DRAWIO_MARKDOWN,
)


class TestStorageToMarkdown:
    """Storage Format → Markdown 转换测试"""

    def setup_method(self):
        self.converter = StorageToMarkdownConverter()

    # ---- 场景：技术设计文档 ----

    def test_tech_design_headings(self):
        """技术设计文档：标题层级正确转换"""
        result = self.converter.convert(TECH_DESIGN_STORAGE)
        assert "# 用户信用评分系统设计文档" in result
        assert "## 1. 系统架构" in result
        assert "## 2. 技术选型" in result

    def test_tech_design_list(self):
        """技术设计文档：无序列表正确转换"""
        result = self.converter.convert(TECH_DESIGN_STORAGE)
        assert "评分引擎服务" in result
        assert "数据采集服务" in result
        assert "规则管理服务" in result

    def test_tech_design_table(self):
        """技术设计文档：表格内容保留"""
        result = self.converter.convert(TECH_DESIGN_STORAGE)
        assert "Spring Boot" in result
        assert "MySQL" in result
        assert "Redis" in result
        assert "Kafka" in result

    def test_tech_design_mermaid(self):
        """技术设计文档：Mermaid 宏转为代码块"""
        result = self.converter.convert(TECH_DESIGN_STORAGE)
        assert "```mermaid" in result
        assert "sequenceDiagram" in result
        assert "Client->>Gateway" in result or "Client" in result

    def test_tech_design_code_block(self):
        """技术设计文档：代码宏转为围栏代码块"""
        result = self.converter.convert(TECH_DESIGN_STORAGE)
        assert "```java" in result
        assert "CreditScoreService" in result
        assert "calculate" in result

    def test_tech_design_info_macro(self):
        """技术设计文档：info 宏转为引用块"""
        result = self.converter.convert(TECH_DESIGN_STORAGE)
        assert "本文档描述用户信用评分系统的技术设计方案" in result

    def test_tech_design_warning_macro(self):
        """技术设计文档：warning 宏转为引用块"""
        result = self.converter.convert(TECH_DESIGN_STORAGE)
        assert "评分结果涉及用户隐私" in result

    # ---- 场景：API 接口文档 ----

    def test_api_doc_endpoint_info(self):
        """API 文档：接口路径和方法保留"""
        result = self.converter.convert(API_DOC_STORAGE)
        assert "/api/v1/users/" in result
        assert "GET" in result
        assert "POST" in result

    def test_api_doc_param_table(self):
        """API 文档：参数表格正确转换"""
        result = self.converter.convert(API_DOC_STORAGE)
        assert "userId" in result
        assert "String" in result

    def test_api_doc_json_code_block(self):
        """API 文档：JSON 响应示例转为代码块"""
        result = self.converter.convert(API_DOC_STORAGE)
        assert "```json" in result
        assert '"code": 200' in result
        assert '"creditScore": 750' in result

    # ---- 场景：会议纪要 ----

    def test_meeting_notes_title(self):
        """会议纪要：标题包含日期"""
        result = self.converter.convert(MEETING_NOTES_STORAGE)
        assert "2025-06-15" in result
        assert "技术评审会议纪要" in result

    def test_meeting_notes_attendees(self):
        """会议纪要：参会人员列表"""
        result = self.converter.convert(MEETING_NOTES_STORAGE)
        assert "张三" in result
        assert "李四" in result
        assert "王五" in result

    def test_meeting_notes_ordered_list(self):
        """会议纪要：有序列表保留"""
        result = self.converter.convert(MEETING_NOTES_STORAGE)
        assert "信用评分系统上线计划" in result
        assert "性能优化方案讨论" in result

    def test_meeting_notes_bold_text(self):
        """会议纪要：加粗文本保留"""
        result = self.converter.convert(MEETING_NOTES_STORAGE)
        assert "7月15日" in result

    def test_meeting_notes_nested_list(self):
        """会议纪要：嵌套列表内容保留"""
        result = self.converter.convert(MEETING_NOTES_STORAGE)
        assert "数据库查询优化" in result
        assert "缓存策略调整" in result
        assert "接口限流配置" in result

    # ---- 场景：元数据头 ----

    def test_metadata_header_added(self):
        """传入 page_title 时添加元数据头"""
        result = self.converter.convert("<p>内容</p>", page_title="测试标题")
        assert "---" in result
        assert "title: 测试标题" in result

    def test_no_metadata_header(self):
        """不传 page_title 时无元数据头"""
        result = self.converter.convert("<p>内容</p>")
        assert "title:" not in result

    # ---- 边界场景 ----

    def test_empty_content(self):
        """空内容不报错"""
        result = self.converter.convert("")
        assert isinstance(result, str)

    def test_plain_text_only(self):
        """纯文本段落"""
        result = self.converter.convert("<p>这是一段纯文本</p>")
        assert "这是一段纯文本" in result

    def test_multiple_code_blocks(self):
        """多个不同语言的代码块"""
        storage = """
<ac:structured-macro ac:name="code">
<ac:parameter ac:name="language">python</ac:parameter>
<ac:plain-text-body><![CDATA[print("hello")]]></ac:plain-text-body>
</ac:structured-macro>
<ac:structured-macro ac:name="code">
<ac:parameter ac:name="language">sql</ac:parameter>
<ac:plain-text-body><![CDATA[SELECT * FROM users;]]></ac:plain-text-body>
</ac:structured-macro>
"""
        result = self.converter.convert(storage)
        assert "```python" in result
        assert 'print("hello")' in result
        assert "```sql" in result
        assert "SELECT * FROM users" in result

    def test_code_block_without_language(self):
        """无语言标记的代码块"""
        storage = """
<ac:structured-macro ac:name="code">
<ac:plain-text-body><![CDATA[echo "hello world"]]></ac:plain-text-body>
</ac:structured-macro>
"""
        result = self.converter.convert(storage)
        assert "```" in result
        assert 'echo "hello world"' in result


class TestMarkdownToStorage:
    """Markdown → Storage Format 转换测试"""

    def setup_method(self):
        self.converter = MarkdownToStorageConverter()

    # ---- 场景：架构设计文档 ----

    @pytest.mark.asyncio
    async def test_architecture_headings(self):
        """架构文档：标题转为 HTML heading"""
        result, _ = await self.converter.convert(ARCHITECTURE_MARKDOWN, mermaid_render_mode="code_block")
        assert "<h1>" in result or "<h1" in result
        assert "微服务架构设计" in result

    @pytest.mark.asyncio
    async def test_architecture_table(self):
        """架构文档：表格转为 HTML table"""
        result, _ = await self.converter.convert(ARCHITECTURE_MARKDOWN, mermaid_render_mode="code_block")
        assert "<table" in result
        assert "user-service" in result
        assert "8081" in result

    @pytest.mark.asyncio
    async def test_architecture_yaml_code_block(self):
        """架构文档：YAML 代码块转为 Confluence code 宏"""
        result, _ = await self.converter.convert(ARCHITECTURE_MARKDOWN, mermaid_render_mode="code_block")
        assert 'ac:name="code"' in result
        assert "credit-service" in result

    @pytest.mark.asyncio
    async def test_architecture_mermaid_as_code_block(self):
        """架构文档：Mermaid 不使用本地渲染时转为代码块"""
        result, attachments = await self.converter.convert(
            ARCHITECTURE_MARKDOWN, mermaid_render_mode="code_block"
        )
        assert len(attachments) == 0
        # 应包含 Mermaid 代码内容
        assert "负载均衡" in result or "LB" in result

    @pytest.mark.asyncio
    async def test_architecture_mermaid_as_macro(self):
        """架构文档：macro 模式生成 Confluence 原生 Mermaid 宏"""
        result, attachments = await self.converter.convert(
            ARCHITECTURE_MARKDOWN, mermaid_render_mode="macro"
        )
        assert len(attachments) == 0
        assert 'ac:name="mermaid-macro"' in result
        assert "<![CDATA[" in result
        assert "</ac:structured-macro>" in result
        # 不应包含 expand 宏（那是 code_block 模式）
        assert 'ac:name="expand"' not in result

    # ---- 场景：简单文本页面 ----

    @pytest.mark.asyncio
    async def test_simple_page_paragraphs(self):
        """简单页面：段落正确转换"""
        result, _ = await self.converter.convert(SIMPLE_PAGE_MARKDOWN, mermaid_render_mode="code_block")
        assert "项目说明" in result
        assert "简单的项目说明页面" in result

    @pytest.mark.asyncio
    async def test_simple_page_list(self):
        """简单页面：列表转为 HTML list"""
        result, _ = await self.converter.convert(SIMPLE_PAGE_MARKDOWN, mermaid_render_mode="code_block")
        assert "<li>" in result or "<ul>" in result
        assert "用户注册与登录" in result
        assert "信用评分查询" in result

    # ---- 场景：数据库设计文档 ----

    @pytest.mark.asyncio
    async def test_complex_table_structure(self):
        """数据库设计：复杂表格结构保留"""
        result, _ = await self.converter.convert(COMPLEX_TABLE_MARKDOWN, mermaid_render_mode="code_block")
        assert "<table" in result
        assert "bigint" in result
        assert "varchar" in result
        assert "AUTO_INCREMENT" in result

    @pytest.mark.asyncio
    async def test_complex_table_index_info(self):
        """数据库设计：索引信息保留"""
        result, _ = await self.converter.convert(COMPLEX_TABLE_MARKDOWN, mermaid_render_mode="code_block")
        assert "uk_user_id" in result
        assert "UNIQUE" in result

    # ---- 场景：元数据头处理 ----

    @pytest.mark.asyncio
    async def test_metadata_header_removed(self):
        """YAML 元数据头被移除"""
        md_with_meta = "---\ntitle: 测试\npage_id: 123\n---\n\n# 正文内容"
        result, _ = await self.converter.convert(md_with_meta, mermaid_render_mode="code_block")
        assert "title: 测试" not in result
        assert "正文内容" in result

    @pytest.mark.asyncio
    async def test_no_metadata_header(self):
        """无元数据头的内容正常处理"""
        result, _ = await self.converter.convert("# 标题\n\n内容", mermaid_render_mode="code_block")
        assert "标题" in result
        assert "内容" in result

    # ---- 边界场景 ----

    @pytest.mark.asyncio
    async def test_empty_content(self):
        """空内容不报错"""
        result, attachments = await self.converter.convert(" ", mermaid_render_mode="code_block")
        assert isinstance(result, str)
        assert attachments == []

    @pytest.mark.asyncio
    async def test_special_characters(self):
        """特殊字符不被破坏"""
        md = "# 测试\n\n包含特殊字符：<>&\"' 以及中文标点：，。！？"
        result, _ = await self.converter.convert(md, mermaid_render_mode="code_block")
        assert "特殊字符" in result

    @pytest.mark.asyncio
    async def test_inline_code(self):
        """行内代码保留"""
        md = "使用 `SELECT * FROM users` 查询数据"
        result, _ = await self.converter.convert(md, mermaid_render_mode="code_block")
        assert "SELECT * FROM users" in result

    @pytest.mark.asyncio
    async def test_links_preserved(self):
        """链接正确转换"""
        md = "参考 [Spring Boot 文档](https://spring.io/projects/spring-boot)"
        result, _ = await self.converter.convert(md, mermaid_render_mode="code_block")
        assert "spring.io" in result
        assert "Spring Boot" in result

    @pytest.mark.asyncio
    async def test_blockquote_info(self):
        """Info 引用块转为 Confluence info 宏"""
        md = "> ℹ️ Info: 这是一条提示信息"
        result, _ = await self.converter.convert(md, mermaid_render_mode="code_block")
        assert "提示信息" in result

    @pytest.mark.asyncio
    async def test_blockquote_warning(self):
        """Warning 引用块转为 Confluence warning 宏"""
        md = "> ⚠️ Warning: 这是一条警告信息"
        result, _ = await self.converter.convert(md, mermaid_render_mode="code_block")
        assert "警告信息" in result


class TestDrawioStorageToMarkdown:
    """Draw.io Storage Format → Markdown 转换测试"""

    def setup_method(self):
        self.converter = StorageToMarkdownConverter()

    def test_drawio_basic(self):
        """draw.io 宏转为 Markdown 描述"""
        result = self.converter.convert(DRAWIO_STORAGE)
        assert "Draw.io" in result
        assert "system-architecture.drawio" in result

    def test_drawio_surrounding_content(self):
        """draw.io 宏不影响周围内容"""
        result = self.converter.convert(DRAWIO_STORAGE)
        assert "系统架构图" in result
        assert "用户服务" in result
        assert "订单服务" in result

    def test_drawio_editor_link(self):
        """draw.io 在线编辑器链接存在"""
        result = self.converter.convert(DRAWIO_STORAGE)
        assert "app.diagrams.net" in result

    def test_multi_drawio(self):
        """多个 draw.io 图表都正确转换"""
        result = self.converter.convert(MULTI_DRAWIO_STORAGE)
        assert "flow-chart.drawio" in result
        assert "data-flow.drawio" in result

    def test_mixed_drawio_and_mermaid(self):
        """draw.io 和 Mermaid 同时存在时都正确转换"""
        result = self.converter.convert(MIXED_DIAGRAM_STORAGE)
        assert "architecture.drawio" in result
        assert "```mermaid" in result
        assert "sequenceDiagram" in result

    def test_drawio_inline_content(self):
        """单个 draw.io 宏的独立转换"""
        storage = """<ac:structured-macro ac:name="drawio" ac:schema-version="1">
<ac:parameter ac:name="diagramName">test.drawio</ac:parameter>
<ac:parameter ac:name="attachment">test.drawio</ac:parameter>
</ac:structured-macro>"""
        result = self.converter.convert(storage)
        assert "test.drawio" in result
        assert "Draw.io" in result


class TestDrawioMarkdownToStorage:
    """Draw.io Markdown → Storage Format 转换测试"""

    def setup_method(self):
        self.converter = MarkdownToStorageConverter()

    @pytest.mark.asyncio
    async def test_drawio_markdown_to_storage(self):
        """Markdown draw.io 标记转为 Confluence drawio 宏"""
        result, _ = await self.converter.convert(DRAWIO_MARKDOWN, mermaid_render_mode="code_block")
        assert 'ac:name="drawio"' in result
        assert "system-architecture.drawio" in result

    @pytest.mark.asyncio
    async def test_drawio_surrounding_content_preserved(self):
        """draw.io 转换不影响周围内容"""
        result, _ = await self.converter.convert(DRAWIO_MARKDOWN, mermaid_render_mode="code_block")
        assert "系统架构图" in result
        assert "用户服务" in result

    @pytest.mark.asyncio
    async def test_drawio_macro_params(self):
        """draw.io 宏包含必要参数"""
        md = '> \U0001f4ca **Draw.io 图表**: my-diagram.drawio\n> [draw.io 在线编辑器](https://app.diagrams.net/)'
        result, _ = await self.converter.convert(md, mermaid_render_mode="code_block")
        assert 'ac:name="diagramName"' in result
        assert 'ac:name="attachment"' in result
        assert "my-diagram.drawio" in result

    @pytest.mark.asyncio
    async def test_drawio_no_attachments(self):
        """draw.io 转换不产生附件"""
        result, attachments = await self.converter.convert(DRAWIO_MARKDOWN, mermaid_render_mode="code_block")
        assert attachments == []

    @pytest.mark.asyncio
    async def test_drawio_roundtrip_no_orphaned_link(self):
        """draw.io 双向转换不会产生孤立的编辑器链接"""
        md = '> \U0001f4ca **Draw.io 图表**: test.drawio\n> [draw.io 在线编辑器](https://app.diagrams.net/)'
        result, _ = await self.converter.convert(md, mermaid_render_mode="code_block")
        assert 'ac:name="drawio"' in result
        # 编辑器链接不应残留在结果中
        assert "app.diagrams.net" not in result

    @pytest.mark.asyncio
    async def test_drawio_schema_version(self):
        """draw.io 宏包含 ac:schema-version 属性"""
        md = '> \U0001f4ca **Draw.io 图表**: test.drawio\n> [draw.io 在线编辑器](https://app.diagrams.net/)'
        result, _ = await self.converter.convert(md, mermaid_render_mode="code_block")
        assert 'ac:schema-version="1"' in result
