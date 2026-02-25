"""Confluence MCP 服务器

基于 Python + FastMCP 的 Confluence MCP 服务器，提供通过 MCP 协议访问 Confluence API 的能力。
支持 Markdown 与 Confluence Storage Format 的双向转换，支持 Mermaid 图表的多种渲染模式
（原生宏、本地图片渲染、代码块+在线编辑器）。

服务器命名遵循 MCP 规范：confluence_mcp
"""
import html
import json
import os
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup
from fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .api.client import ConfluenceClient
from .config import get_config
from .converters.markdown_to_storage import MarkdownToStorageConverter
from .converters.mermaid_handler import MermaidHandler
from .converters.drawio_handler import DrawioHandler

from .converters.storage_to_markdown import StorageToMarkdownConverter
from .utils.exceptions import (
    APIError,
    AuthenticationError,
    ConfluenceMCPError,
    NotFoundError,
    PermissionError,
)
from .utils.logger import get_logger, setup_logger

# 初始化配置和日志
config = get_config()
setup_logger("confluence_mcp", config.log_level)
logger = get_logger(__name__)

# 创建 MCP 服务器 - 遵循命名规范 {service}_mcp
mcp = FastMCP("confluence_mcp")

# 创建转换器实例
storage_to_md = StorageToMarkdownConverter()
md_to_storage = MarkdownToStorageConverter()


# ============== 响应格式枚举 ==============


class ResponseFormat(str, Enum):
    """响应格式枚举"""

    MARKDOWN = "markdown"
    JSON = "json"


class MermaidRenderMode(str, Enum):
    """Mermaid 渲染模式枚举"""

    MACRO = "macro"
    IMAGE = "image"
    CODE_BLOCK = "code_block"


# ============== Pydantic 输入模型 ==============


class ReadPageInput(BaseModel):
    """读取页面的输入参数"""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    page_id: str = Field(
        ...,
        description="Confluence 页面 ID（例如：'123456'）",
        min_length=1,
        max_length=50,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="输出格式：'markdown'（人类可读）或 'json'（机器处理）",
    )

    @field_validator("page_id")
    @classmethod
    def validate_page_id(cls, v: str) -> str:
        """验证页面 ID"""
        if not v.strip():
            raise ValueError("page_id 不能为空")
        # 移除可能的空格
        return v.strip()


class CreatePageInput(BaseModel):
    """创建页面的输入参数"""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    space_key: str = Field(
        ...,
        description="Confluence 空间键（例如：'DEV', 'TEAM'）",
        min_length=1,
        max_length=100,
    )
    title: str = Field(
        ..., description="页面标题", min_length=1, max_length=255
    )
    markdown_content: str = Field(
        ..., description="Markdown 格式的页面内容", min_length=1
    )
    parent_id: Optional[str] = Field(
        default=None, description="父页面 ID（可选，用于创建子页面）", max_length=50
    )
    mermaid_render_mode: MermaidRenderMode = Field(
        default=MermaidRenderMode.MACRO,
        description="Mermaid 渲染模式："
        "'macro'（默认）使用 Confluence 原生 Mermaid 宏直接渲染；"
        "'image' 使用本地 mermaid-cli 渲染为图片上传；"
        "'code_block' 使用可折叠代码块 + Mermaid Live Editor 链接",
    )

    @field_validator("space_key")
    @classmethod
    def validate_space_key(cls, v: str) -> str:
        """验证空间键"""
        return v.strip().upper()


class UpdatePageInput(BaseModel):
    """更新页面的输入参数"""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    page_id: str = Field(
        ..., description="要更新的页面 ID", min_length=1, max_length=50
    )
    markdown_content: str = Field(
        ..., description="新的 Markdown 内容", min_length=1
    )
    title: Optional[str] = Field(
        default=None,
        description="新标题（可选，不提供则保持原标题）",
        max_length=255,
    )
    mermaid_render_mode: MermaidRenderMode = Field(
        default=MermaidRenderMode.MACRO,
        description="Mermaid 渲染模式："
        "'macro'（默认）使用 Confluence 原生 Mermaid 宏直接渲染；"
        "'image' 使用本地 mermaid-cli 渲染为图片上传；"
        "'code_block' 使用可折叠代码块 + Mermaid Live Editor 链接",
    )


class SearchPagesInput(BaseModel):
    """搜索页面的输入参数"""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    query: str = Field(
        ..., description="搜索关键词", min_length=2, max_length=500
    )
    space_key: Optional[str] = Field(
        default=None,
        description="限制搜索的空间键（可选）",
        max_length=100,
    )
    limit: int = Field(
        default=25,
        description="返回结果数量限制",
        ge=1,
        le=100,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="输出格式：'markdown' 或 'json'",
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """验证搜索查询"""
        if not v.strip():
            raise ValueError("搜索关键词不能为空")
        return v.strip()


class UploadDrawioInput(BaseModel):
    """上传 draw.io 图表到已有 Confluence 页面的输入参数"""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    page_id: str = Field(
        ...,
        description="目标 Confluence 页面 ID（例如：'123456'）",
        min_length=1,
        max_length=50,
    )
    drawio_xml: str = Field(
        ...,
        description="Draw.io 图表的 XML 内容（完整的 mxfile 或 mxGraphModel XML 字符串）",
        min_length=1,
    )
    file_name: Optional[str] = Field(
        default=None,
        description=(
            "附件文件名（可选，默认自动生成 'drawio_diagram_0.drawio'）。"
            "必须以 .drawio ��尾"
        ),
        max_length=255,
    )
    insert_position: Optional[str] = Field(
        default=None,
        description=(
            "插入位置的标题文本（可选）。"
            "如果指定，draw.io 宏将插入到该标题之后；"
            "如果不指定或标题未找到，将追加到页面内容末尾。"
            "例如：'系统架构' 或 '流程设计'"
        ),
        max_length=500,
    )

    @field_validator("page_id")
    @classmethod
    def validate_page_id(cls, v: str) -> str:
        """验证页面 ID"""
        if not v.strip():
            raise ValueError("page_id 不能为空")
        return v.strip()

    @field_validator("drawio_xml")
    @classmethod
    def validate_drawio_xml(cls, v: str) -> str:
        """验证 draw.io XML 内容的基本格式"""
        stripped = v.strip()
        if not stripped:
            raise ValueError("drawio_xml 不能为空")
        if not (stripped.startswith("<mxfile") or stripped.startswith("<mxGraphModel")):
            raise ValueError(
                "drawio_xml 格式无效：应以 <mxfile 或 <mxGraphModel 开头。"
                "请提供完整的 draw.io XML 内容。"
            )
        return stripped

    @field_validator("file_name")
    @classmethod
    def validate_file_name(cls, v: Optional[str]) -> Optional[str]:
        """验证文件名格式"""
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if not v.endswith(".drawio"):
            raise ValueError("file_name 必须以 .drawio 结尾")
        if any(c in v for c in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']):
            raise ValueError("file_name 包含非法字符")
        return v


class ContentFormat(str, Enum):
    """评论内容格式枚举"""

    MARKDOWN = "markdown"
    PLAIN_TEXT = "plain_text"


class GetCommentsInput(BaseModel):
    """获取页面评论的输入参数"""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    page_id: str = Field(
        ...,
        description="Confluence 页面 ID（例如：'123456'）",
        min_length=1,
        max_length=50,
    )
    limit: int = Field(
        default=50,
        description="返回评论数量限制",
        ge=1,
        le=100,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="输出格式：'markdown'（人类可读）或 'json'（机器处理）",
    )

    @field_validator("page_id")
    @classmethod
    def validate_page_id(cls, v: str) -> str:
        """验证页面 ID"""
        if not v.strip():
            raise ValueError("page_id 不能为空")
        return v.strip()


class AddCommentInput(BaseModel):
    """发布评论的输入参数"""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    page_id: str = Field(
        ...,
        description="Confluence 页面 ID（例如：'123456'）",
        min_length=1,
        max_length=50,
    )
    content: str = Field(
        ...,
        description="评论内容",
        min_length=1,
    )
    content_format: ContentFormat = Field(
        default=ContentFormat.PLAIN_TEXT,
        description=(
            "评论内容格式：'plain_text'（默认）纯文本，自动包裹 HTML 标签；"
            "'markdown' 将 Markdown 转换为 Confluence Storage Format"
        ),
    )
    parent_comment_id: Optional[str] = Field(
        default=None,
        description="父评论 ID（可选，用于回复已有评论）",
        max_length=50,
    )

    @field_validator("page_id")
    @classmethod
    def validate_page_id(cls, v: str) -> str:
        """验证页面 ID"""
        if not v.strip():
            raise ValueError("page_id 不能为空")
        return v.strip()

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """验证评论内容"""
        if not v.strip():
            raise ValueError("评论内容不能为空")
        return v


# ============== 错误处理辅助函数 ==============


def _handle_error(e: Exception) -> str:
    """统一错误处理，返回清晰的错误消息

    Args:
        e: 异常对象

    Returns:
        格式化的错误消息
    """
    if isinstance(e, AuthenticationError):
        return (
            "错误：认证失败。请检查：\n"
            "1. CONFLUENCE_API_TOKEN 是否正确配置\n"
            "2. Token 是否已过期\n"
            "3. Token 是否有足够的权限\n"
            f"详细信息：{str(e)}"
        )
    elif isinstance(e, NotFoundError):
        return (
            "错误：资源未找到。请检查：\n"
            "1. 页面 ID 是���正确\n"
            "2. 空间键是否正确\n"
            "3. 是否有访问该资源的权限\n"
            f"详细信息：{str(e)}"
        )
    elif isinstance(e, PermissionError):
        return (
            "错误：权限不足。请检查：\n"
            "1. 当前用户是否有访问该资源的权限\n"
            "2. Token 是否包含所需的权限范围\n"
            f"详细信息：{str(e)}"
        )
    elif isinstance(e, APIError):
        return f"错误：API 请求失败。{str(e)}"
    elif isinstance(e, ConfluenceMCPError):
        return f"错误：{str(e)}"
    else:
        return f"错误：发生未预期的错误。{type(e).__name__}: {str(e)}"


# ============== MCP Tools ==============


@mcp.tool(
    name="confluence_read_page",
    annotations={
        "title": "读取 Confluence 页面",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def confluence_read_page(params: ReadPageInput) -> str:
    """读取 Confluence 页面并转换为 Markdown 格式。

    此工具从 Confluence 获取指定页面的内容，并将 Storage Format 转换为
    易读的 Markdown 格式。支持以下特性：
    - 自动转换 Confluence 宏（code, info, warning 等）
    - 将 Mermaid 宏转换为 Markdown 代码块
    - 包含页面元数据（标题、ID、空间、版本等）

    Args:
        params (ReadPageInput): 包含以下字段：
            - page_id (str): Confluence 页面 ID（例如：'123456'）
            - response_format (ResponseFormat): 输出格式，'markdown' 或 'json'

    Returns:
        str: 根据 response_format 返回：
            - markdown: 包含元数据头的 Markdown 文本
            - json: 包含页面详细信息的 JSON 字符串

    Examples:
        - 读取页面: params = {"page_id": "123456"}
        - JSON 格式: params = {"page_id": "123456", "response_format": "json"}

    Error Handling:
        - 页面不存在: 返回 NotFoundError 相关提示
        - 权限不足: 返回 PermissionError 相关提示
        - 认证失败: 返回 AuthenticationError 相关提示
    """
    logger.info(f"读取页面: {params.page_id}")

    try:
        async with ConfluenceClient() as client:
            # 获取页面
            page = await client.get_page(params.page_id)

            # 转换为 Markdown
            markdown_content = storage_to_md.convert(
                page.storage_content, page_title=page.title
            )

            # 构建元数据
            metadata = {
                "title": page.title,
                "page_id": page.id,
                "space": page.space.key,
                "version": page.version.number if page.version else 1,
                "url": (
                    f"{config.confluence_base_url}{page.web_url}"
                    if page.web_url
                    else None
                ),
            }

            if params.response_format == ResponseFormat.JSON:
                # JSON 格式：返回完整数据
                result = {
                    "metadata": metadata,
                    "content": markdown_content,
                    "storage_format": page.storage_content,  # 包含原始格式
                }
                return json.dumps(result, ensure_ascii=False, indent=2)
            else:
                # Markdown 格式：人类可读
                metadata_lines = [
                    "---",
                    f"title: {metadata['title']}",
                    f"page_id: {metadata['page_id']}",
                    f"space: {metadata['space']}",
                    f"version: {metadata['version']}",
                ]
                if metadata["url"]:
                    metadata_lines.append(f"url: {metadata['url']}")
                metadata_lines.append("---\n")

                # 移除原有的简单元数据头
                if markdown_content.startswith("---\n"):
                    end_idx = markdown_content.find("---\n", 4)
                    if end_idx != -1:
                        markdown_content = markdown_content[end_idx + 4 :].lstrip()

                full_content = "\n".join(metadata_lines) + "\n" + markdown_content
                logger.info(f"页面读取成功: {page.title}")
                return full_content

    except Exception as e:
        logger.error(f"读取页面失败: {e}", exc_info=True)
        return _handle_error(e)


@mcp.tool(
    name="confluence_create_page",
    annotations={
        "title": "创建 Confluence 页面",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def confluence_create_page(params: CreatePageInput) -> str:
    """从 Markdown 创建新的 Confluence 页面。

    此工具将 Markdown 内容转换为 Confluence Storage Format 并创建新页面。
    支持以下特性：
    - Markdown 语法转换（标题、列表、表格、代码块等）
    - Mermaid 图表渲染（三种模式可选）
    - 创建子页面（通过 parent_id 参数）

    Mermaid 处理策略：
    - mermaid_render_mode="macro"（默认）：
      使用 Confluence 原生 Mermaid 宏直接渲染（需要 Mermaid 插件）
    - mermaid_render_mode="image"：
      使用本地 mermaid-cli 渲染为 PNG 图片并上传为附件
    - mermaid_render_mode="code_block"：
      使用可折叠代码块 + Mermaid Live Editor 链接

    Args:
        params (CreatePageInput): 包含以下字段：
            - space_key (str): Confluence 空间键
            - title (str): 页面标题
            - markdown_content (str): Markdown 内容
            - parent_id (Optional[str]): 父页面 ID
            - mermaid_render_mode (MermaidRenderMode): Mermaid 渲染模式

    Returns:
        str: JSON 格式的创建结果，包含：
            - id: 新页面 ID
            - title: 页面标题
            - space: 空间键
            - version: 版本号
            - url: 页面 URL
            - status: 操作状态
            - mermaid_render_method: Mermaid 渲染方式
            - mermaid_diagrams_count: Mermaid 图表数量

    Examples:
        - 创建简单页面:
          params = {
              "space_key": "DEV",
              "title": "测试页面",
              "markdown_content": "# 标题\\n\\n内容"
          }
        - 创建子页面:
          params = {
              "space_key": "DEV",
              "title": "子页面",
              "markdown_content": "内容",
              "parent_id": "123456"
          }
    """
    logger.info(f"创建页面: {params.title} (空间: {params.space_key})")

    try:
        # 检查是否有 Mermaid 代码块
        mermaid_blocks = MermaidHandler.extract_mermaid_blocks(params.markdown_content)
        has_mermaid = len(mermaid_blocks) > 0
        render_mode = params.mermaid_render_mode.value

        # 检查是否有 draw.io XML 代码块
        drawio_codeblocks = DrawioHandler.extract_drawio_codeblocks(params.markdown_content)
        has_drawio_codeblocks = len(drawio_codeblocks) > 0

        # 判断是否需要两步创建流程（需要先获取 page_id 才能上传附件）
        needs_two_step = (render_mode == "image" and has_mermaid) or has_drawio_codeblocks

        async with ConfluenceClient() as client:
            if needs_two_step:
                # 两步创建：先创建占位页面，再上传附件并更新
                # 第一步：用简化模式创建页面（不上传附件）
                first_pass_mermaid_mode = "code_block" if (render_mode == "image" and has_mermaid) else render_mode
                storage_content, _ = await md_to_storage.convert(
                    params.markdown_content,
                    mermaid_render_mode=first_pass_mermaid_mode,
                )

                page = await client.create_page(
                    space_key=params.space_key,
                    title=params.title,
                    body_storage=storage_content,
                    parent_id=params.parent_id,
                )
                logger.info(f"页面创建成功（占位）: {page.id}")

                # 第二步：用完整模式重新转换并更新（传入 page_id 和 client 以支持附件上传）
                storage_with_attachments, attachments = await md_to_storage.convert(
                    params.markdown_content,
                    mermaid_render_mode=render_mode,
                    page_id=page.id,
                    confluence_client=client,
                )

                attachments_uploaded = len(attachments) if attachments else 0
                if attachments:
                    page = await client.update_page(
                        page_id=page.id,
                        title=params.title,
                        body_storage=storage_with_attachments,
                        version_number=page.version.number,
                    )
                    logger.info(f"已上传 {attachments_uploaded} 个附件（Mermaid + draw.io）")
                else:
                    # 附件上传全部失败或降级，实际使用的可能是 code_block
                    if render_mode == "image" and has_mermaid:
                        render_mode = "code_block"
            else:
                # 单步创建：直接转换并创建（无需附件上传）
                storage_content, _ = await md_to_storage.convert(
                    params.markdown_content,
                    mermaid_render_mode=render_mode,
                )
                attachments_uploaded = 0

                page = await client.create_page(
                    space_key=params.space_key,
                    title=params.title,
                    body_storage=storage_content,
                    parent_id=params.parent_id,
                )
                logger.info(f"页面创建成功: {page.id}")

            result = {
                "id": page.id,
                "title": page.title,
                "space": page.space.key,
                "version": page.version.number if page.version else 1,
                "url": (
                    f"{config.confluence_base_url}{page.web_url}"
                    if page.web_url
                    else None
                ),
                "status": "success",
                "message": f"页面创建成功: {params.title}",
                "mermaid_render_method": render_mode,
                "mermaid_diagrams_count": len(mermaid_blocks) if has_mermaid else 0,
                "mermaid_images_uploaded": attachments_uploaded if render_mode == "image" else 0,
                "drawio_diagrams_count": len(drawio_codeblocks) if has_drawio_codeblocks else 0,
            }

            logger.info(f"页面创建完成: {page.id}")
            return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"创建页面失败: {e}", exc_info=True)
        return _handle_error(e)


@mcp.tool(
    name="confluence_update_page",
    annotations={
        "title": "更新 Confluence 页面",
        "readOnlyHint": False,
        "destructiveHint": True,  # 会覆盖现有内容
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def confluence_update_page(params: UpdatePageInput) -> str:
    """更新现有的 Confluence 页面内容。

    此工具获取指定页面的当前版本，将新的 Markdown 内容转换为
    Storage Format 并更新页面。版本号会自动递增。

    注意：此操作会覆盖页面的现有内容！

    Args:
        params (UpdatePageInput): 包含以下字段：
            - page_id (str): 要更新的页面 ID
            - markdown_content (str): 新的 Markdown 内容
            - title (Optional[str]): 新标题（不提供则保持原标题）
            - mermaid_render_mode (MermaidRenderMode): Mermaid 渲染模式

    Returns:
        str: JSON 格式的更新结果，包含：
            - id: 页面 ID
            - title: 页面标题
            - space: 空间键
            - version: 新版本号
            - url: 页面 URL
            - status: 操作状态

    Examples:
        - 更新内容:
          params = {
              "page_id": "123456",
              "markdown_content": "# 更新后的标题\\n\\n新内容"
          }
        - 同时更新标题:
          params = {
              "page_id": "123456",
              "markdown_content": "内容",
              "title": "新标题"
          }
    """
    logger.info(f"更新页面: {params.page_id}")

    try:
        async with ConfluenceClient() as client:
            # 获取当前页面信息
            current_page = await client.get_page(params.page_id)

            # 使用提供的标题或保持原标题
            new_title = params.title if params.title else current_page.title

            # 检查是否有 Mermaid 代码块
            mermaid_blocks = MermaidHandler.extract_mermaid_blocks(params.markdown_content)
            has_mermaid = len(mermaid_blocks) > 0
            render_mode = params.mermaid_render_mode.value

            # 检查是否有 draw.io XML 代码块
            drawio_codeblocks = DrawioHandler.extract_drawio_codeblocks(params.markdown_content)
            has_drawio_codeblocks = len(drawio_codeblocks) > 0

            # 转换 Markdown 到 Storage Format
            # 始终传入 page_id 和 client，以支持 draw.io 代码块上传和 Mermaid image 模式
            storage_content, attachments = await md_to_storage.convert(
                params.markdown_content,
                mermaid_render_mode=render_mode,
                page_id=params.page_id,
                confluence_client=client,
            )

            attachments_uploaded = len(attachments) if attachments else 0
            # 如果 image 模式降级（mmdc 不可用），更新实际使用的模式
            if render_mode == "image" and has_mermaid and attachments_uploaded == 0:
                render_mode = "code_block"

            # 更新页面
            updated_page = await client.update_page(
                page_id=params.page_id,
                title=new_title,
                body_storage=storage_content,
                version_number=(
                    current_page.version.number if current_page.version else 1
                ),
            )

            result = {
                "id": updated_page.id,
                "title": updated_page.title,
                "space": updated_page.space.key,
                "version": (
                    updated_page.version.number if updated_page.version else 1
                ),
                "url": (
                    f"{config.confluence_base_url}{updated_page.web_url}"
                    if updated_page.web_url
                    else None
                ),
                "status": "success",
                "message": f"页面更新成功: {new_title}",
                "previous_version": (
                    current_page.version.number if current_page.version else 1
                ),
                "mermaid_render_method": render_mode,
                "mermaid_diagrams_count": len(mermaid_blocks) if has_mermaid else 0,
                "mermaid_images_uploaded": attachments_uploaded if render_mode == "image" else 0,
                "drawio_diagrams_count": len(drawio_codeblocks) if has_drawio_codeblocks else 0,
            }

            logger.info(f"页面更新成功: {params.page_id}")
            return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"更新页面失败: {e}", exc_info=True)
        return _handle_error(e)


@mcp.tool(
    name="confluence_search_pages",
    annotations={
        "title": "搜索 Confluence 页面",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def confluence_search_pages(params: SearchPagesInput) -> str:
    """在 Confluence 中搜索页面。

    此工具使用 CQL (Confluence Query Language) 搜索页面，
    支持全文搜索和空间过滤。

    Args:
        params (SearchPagesInput): 包含以下字段：
            - query (str): 搜索关键词
            - space_key (Optional[str]): 限制搜索的空间
            - limit (int): 结果数量限制（1-100，默认25）
            - response_format (ResponseFormat): 输出格式

    Returns:
        str: 根据 response_format 返回：
            - markdown: 格式化的搜索结果列表
            - json: 包含完整搜索结果的 JSON

    Examples:
        - 简单搜索: params = {"query": "API 文档"}
        - 空间内搜索: params = {"query": "设计", "space_key": "DEV"}
        - JSON 格式: params = {"query": "测试", "response_format": "json"}
    """
    logger.info(f"搜索页面: {params.query}")

    try:
        # 构建 CQL 查询
        cql_parts = [f'text ~ "{params.query}"', "type = page"]

        if params.space_key:
            cql_parts.append(f"space = {params.space_key}")

        cql = " AND ".join(cql_parts)

        async with ConfluenceClient() as client:
            # 执行搜索
            results = await client.search_pages(cql=cql, limit=params.limit)

            if params.response_format == ResponseFormat.JSON:
                # JSON 格式
                search_results = []
                for result in results:
                    search_results.append(
                        {
                            "id": result.id,
                            "title": result.title,
                            "type": result.type,
                            "space": result.space.key if result.space else None,
                            "excerpt": result.excerpt,
                            "url": (
                                f"{config.confluence_base_url}{result.url}"
                                if result.url
                                else None
                            ),
                            "last_modified": (
                                result.last_modified.isoformat()
                                if result.last_modified
                                else None
                            ),
                        }
                    )

                response = {
                    "query": params.query,
                    "space_key": params.space_key,
                    "total": len(search_results),
                    "limit": params.limit,
                    "results": search_results,
                }

                logger.info(f"搜索完成，找到 {len(search_results)} 个结果")
                return json.dumps(response, ensure_ascii=False, indent=2)

            else:
                # Markdown 格式
                lines = [
                    f"# 搜索结果: '{params.query}'",
                    "",
                    f"找到 **{len(results)}** 个结果"
                    + (f"（空间: {params.space_key}）" if params.space_key else ""),
                    "",
                ]

                if not results:
                    lines.append("未找到匹配的页面。")
                else:
                    for idx, result in enumerate(results, 1):
                        space_info = (
                            f" [{result.space.key}]" if result.space else ""
                        )
                        url = (
                            f"{config.confluence_base_url}{result.url}"
                            if result.url
                            else "无链接"
                        )

                        lines.append(f"## {idx}. {result.title}{space_info}")
                        lines.append(f"- **ID**: {result.id}")
                        lines.append(f"- **链接**: {url}")
                        if result.excerpt:
                            # 清理摘要中的 HTML 标签
                            excerpt = result.excerpt.replace("<", "&lt;").replace(
                                ">", "&gt;"
                            )
                            lines.append(f"- **摘要**: {excerpt[:200]}...")
                        lines.append("")

                logger.info(f"搜索完成，找到 {len(results)} 个结果")
                return "\n".join(lines)

    except Exception as e:
        logger.error(f"搜索失败: {e}", exc_info=True)
        return _handle_error(e)


@mcp.tool(
    name="confluence_get_comments",
    annotations={
        "title": "获取 Confluence 页面评论",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def confluence_get_comments(params: GetCommentsInput) -> str:
    """获取 Confluence 页面的评论列表。

    此工具从 Confluence 获取指定页面的所有评论（包括嵌套回复），
    并将评论内容从 Storage Format 转换为易读的 Markdown 格式。

    支持以下特性：
    - 获取页面级评论（footer comments）
    - 包含所有嵌套回复（depth=all）
    - 评论内容自动转换为 Markdown
    - 包含评论者、时间、解决状态等元数据

    Args:
        params (GetCommentsInput): 包含以下字段：
            - page_id (str): Confluence 页面 ID（例如：'123456'）
            - limit (int): 返回评论数量限制（1-100，默认50）
            - response_format (ResponseFormat): 输出格式，'markdown' 或 'json'

    Returns:
        str: 根据 response_format 返回：
            - markdown: 格式化的评论列表
            - json: 包含完整评论数据的 JSON 字符串

    Examples:
        - 获取评论: params = {"page_id": "123456"}
        - JSON 格式: params = {"page_id": "123456", "response_format": "json"}
        - 限制数量: params = {"page_id": "123456", "limit": 10}

    Error Handling:
        - 页面不存在: 返回 NotFoundError 相关提示
        - 权限不足: 返回 PermissionError 相关提示
        - 认证失败: 返回 AuthenticationError 相关提示
    """
    logger.info(f"获取页面评论: {params.page_id}")

    try:
        async with ConfluenceClient() as client:
            data = await client.get_comments(
                page_id=params.page_id,
                depth="all",
                limit=params.limit,
            )

            comments_raw = data.get("results", [])

            # 解析评论数据
            comments = []
            for comment in comments_raw:
                body_storage = ""
                if comment.get("body", {}).get("storage"):
                    body_storage = comment["body"]["storage"].get("value", "")

                # 将 Storage Format 转为 Markdown
                body_markdown = storage_to_md.convert(body_storage) if body_storage else ""

                # 提取评论者信息
                version_info = comment.get("version", {})
                author = version_info.get("by", {})
                author_name = author.get("displayName", author.get("username", "未知"))
                created_at = version_info.get("when", "")

                # 提取解决状态
                extensions = comment.get("extensions", {})
                resolution = extensions.get("resolution", {})
                resolution_status = resolution.get("status", "")

                # 判断是否为回复（有 ancestors）
                ancestors = comment.get("ancestors", [])
                parent_id = ancestors[-1]["id"] if ancestors else None

                comment_data = {
                    "id": comment.get("id", ""),
                    "author": author_name,
                    "created_at": created_at,
                    "body_markdown": body_markdown.strip(),
                    "body_storage": body_storage,
                    "resolution_status": resolution_status,
                    "parent_comment_id": parent_id,
                }
                comments.append(comment_data)

            if params.response_format == ResponseFormat.JSON:
                response = {
                    "page_id": params.page_id,
                    "total": len(comments),
                    "comments": comments,
                }
                return json.dumps(response, ensure_ascii=False, indent=2)
            else:
                lines = [
                    f"# 页面评论 (page_id: {params.page_id})",
                    "",
                    f"共 **{len(comments)}** 条评论",
                    "",
                ]

                if not comments:
                    lines.append("暂无评论。")
                else:
                    top_level_idx = 0
                    for c in comments:
                        if c["parent_comment_id"]:
                            prefix = "  ↳ 回复"
                        else:
                            top_level_idx += 1
                            prefix = f"## {top_level_idx}."
                        lines.append(
                            f"{prefix} **{c['author']}** (ID: {c['id']})"
                        )
                        if c["created_at"]:
                            lines.append(f"- **时间**: {c['created_at']}")
                        if c["resolution_status"]:
                            lines.append(f"- **状态**: {c['resolution_status']}")
                        if c["parent_comment_id"]:
                            lines.append(
                                f"- **回复评论**: {c['parent_comment_id']}"
                            )
                        lines.append(f"- **内容**:")
                        lines.append("")
                        lines.append(c["body_markdown"])
                        lines.append("")

                logger.info(f"获取到 {len(comments)} 条评论")
                return "\n".join(lines)

    except Exception as e:
        logger.error(f"获取评论失败: {e}", exc_info=True)
        return _handle_error(e)


@mcp.tool(
    name="confluence_add_comment",
    annotations={
        "title": "发布 Confluence 页面评论",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def confluence_add_comment(params: AddCommentInput) -> str:
    """在 Confluence 页面上发布评论。

    此工具在指定页面上创建新评论，支持纯文本和 Markdown 两种内容格式，
    并支持回复已有评论（嵌套评论）。

    内容格式：
    - content_format="plain_text"（默认）：纯文本，自动包裹 HTML 标签
    - content_format="markdown"：将 Markdown 转换为 Confluence Storage Format

    Args:
        params (AddCommentInput): 包含以下字段：
            - page_id (str): Confluence 页面 ID
            - content (str): 评论内容
            - content_format (ContentFormat): 内容格式（'plain_text' 或 'markdown'）
            - parent_comment_id (Optional[str]): 父评论 ID（用于回复评论）

    Returns:
        str: JSON 格式的创建结果，包含：
            - status: 操作状态
            - comment_id: 新评论 ID
            - page_id: 页面 ID
            - author: 评论者
            - content_format: 使用的内容格式
            - message: 操作消息

    Examples:
        - 发布纯文本评论:
          params = {
              "page_id": "123456",
              "content": "这是一条评论"
          }
        - 发布 Markdown 评论:
          params = {
              "page_id": "123456",
              "content": "**重要**: 请查看 `config.yaml` 的修改",
              "content_format": "markdown"
          }
        - 回复评论:
          params = {
              "page_id": "123456",
              "content": "同意这个方案",
              "parent_comment_id": "67890"
          }

    Error Handling:
        - 页面不存在: 返回 NotFoundError 相关提示
        - 权限不足: 返回 PermissionError 相关提示
        - 认证失败: 返回 AuthenticationError 相关提示
    """
    logger.info(
        f"发布评论: page_id={params.page_id}, "
        f"format={params.content_format.value}, "
        f"parent={params.parent_comment_id}"
    )

    try:
        # 根据内容格式转换为 Storage Format
        if params.content_format == ContentFormat.MARKDOWN:
            body_storage, _ = await md_to_storage.convert(params.content)
        else:
            # 纯文本：按行分割，每行包裹在 <p> 标签中，转义 HTML 特殊字符
            lines = params.content.strip().split("\n")
            body_storage = "".join(f"<p>{html.escape(line)}</p>" for line in lines)

        async with ConfluenceClient() as client:
            result = await client.create_comment(
                page_id=params.page_id,
                body_storage=body_storage,
                parent_comment_id=params.parent_comment_id,
            )

            # 提取返回信息
            comment_id = result.get("id", "")
            version_info = result.get("version", {})
            author = version_info.get("by", {})
            author_name = author.get("displayName", author.get("username", "未知"))

            response = {
                "status": "success",
                "comment_id": comment_id,
                "page_id": params.page_id,
                "author": author_name,
                "content_format": params.content_format.value,
                "parent_comment_id": params.parent_comment_id,
                "message": (
                    f"评论发布成功 (ID: {comment_id})"
                    + (f"，已回复评论 {params.parent_comment_id}" if params.parent_comment_id else "")
                ),
            }

            logger.info(f"评论发布成功: {comment_id}")
            return json.dumps(response, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"发布评论失败: {e}", exc_info=True)
        return _handle_error(e)


# ============== 辅助函数 ==============


def _insert_macro_after_heading(
    storage_content: str, heading_text: str, macro_html: str
) -> Tuple[str, bool]:
    """在匹配标题后插入 HTML 内容

    在 Confluence Storage Format 中找到与 heading_text 匹配的标题标签（h1-h6），
    将 macro_html 插入到该标题标签之后。

    Args:
        storage_content: Confluence Storage Format 内容
        heading_text: 要匹配的标题文本（精确匹配，忽略首尾空白）
        macro_html: 要插入的 draw.io 宏 HTML

    Returns:
        (修改后的内容, 是否成功找到并插入)
    """
    soup = BeautifulSoup(storage_content, "html.parser")
    target_heading = None

    for heading_tag in soup.find_all(re.compile(r"^h[1-6]$")):
        if heading_tag.get_text(strip=True) == heading_text.strip():
            target_heading = heading_tag
            break

    if target_heading is None:
        return storage_content, False

    macro_soup = BeautifulSoup(macro_html, "html.parser")
    target_heading.insert_after(macro_soup)
    return str(soup), True


@mcp.tool(
    name="confluence_upload_drawio",
    annotations={
        "title": "上传 Draw.io 图表到 Confluence 页面",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def confluence_upload_drawio(params: UploadDrawioInput) -> str:
    """上传 Draw.io 图表 XML 作为附件到 Confluence 页面，并在页面内容中插入 draw.io 宏。

    此工具接受 draw.io 的原始 XML 内容，将其作为 .drawio 附件上传到指定页面，
    然后在页面内容中插入对应的 draw.io 宏来渲染该图表。

    支持以下特性：
    - 自动上传 XML 为 .drawio 附件（支持同名覆盖更新）
    - 在指定标题位置后插入 draw.io 宏
    - 追加到页面末尾（默认行为）
    - 自定义附件文件名

    Args:
        params (UploadDrawioInput): 包含以下字段：
            - page_id (str): 目标页面 ID
            - drawio_xml (str): Draw.io XML 内容（mxfile 或 mxGraphModel 格式）
            - file_name (Optional[str]): 附件文件名（默认自动生成，需以 .drawio 结尾）
            - insert_position (Optional[str]): 标题文本，宏将插入到该标题下方

    Returns:
        str: JSON 格式的操作结果，包含：
            - status: 操作状态
            - message: 操作消息
            - page_id: 页面 ID
            - title: 页面标题
            - version: 新版本号
            - url: 页面 URL
            - attachment_id: 附件 ID
            - attachment_name: 附件文件名
            - insert_position_matched: 是否找到匹配的标题位置

    Examples:
        - 追加到末尾:
          params = {
              "page_id": "123456",
              "drawio_xml": "<mxfile>...</mxfile>"
          }
        - 指定位置和文件名:
          params = {
              "page_id": "123456",
              "drawio_xml": "<mxfile>...</mxfile>",
              "file_name": "architecture.drawio",
              "insert_position": "系统架构"
          }

    Error Handling:
        - 页面不存在: 返回 NotFoundError 相关提示
        - 权限不足: 返回 PermissionError 相关提示
        - 认证失败: 返回 AuthenticationError 相关提示
    """
    logger.info(
        f"上传 draw.io 图表到页面: {params.page_id} "
        f"(file_name={params.file_name}, insert_position={params.insert_position})"
    )

    try:
        async with ConfluenceClient() as client:
            # Step 1: 获取当前页面信息
            page = await client.get_page(params.page_id)
            storage_content = page.storage_content
            version_number = page.version.number if page.version else 1

            # Step 2: 确定文件名
            file_name = params.file_name or DrawioHandler.generate_attachment_filename(0)

            # Step 3: 上传 draw.io XML 为附件
            attachment_info = await client.upload_attachment_bytes(
                page_id=params.page_id,
                content=params.drawio_xml.encode("utf-8"),
                file_name=file_name,
                content_type="application/vnd.jgraph.mxfile",
                comment="Draw.io diagram uploaded via MCP",
            )
            logger.info(f"draw.io 附件上传成功: {file_name}")

            # Step 4: 生成 draw.io 宏
            macro_html = DrawioHandler.markdown_to_drawio_macro(file_name)

            # Step 5: 将宏插入页面内容
            insert_position_matched = False
            if params.insert_position:
                storage_content, insert_position_matched = _insert_macro_after_heading(
                    storage_content, params.insert_position, macro_html
                )
                if not insert_position_matched:
                    logger.warning(
                        f"未找到匹配标题 '{params.insert_position}'，将追加到页面末尾"
                    )
                    storage_content += macro_html
            else:
                storage_content += macro_html

            # Step 6: 更新页面
            updated_page = await client.update_page(
                page_id=params.page_id,
                title=page.title,
                body_storage=storage_content,
                version_number=version_number,
            )

            # Step 7: 返回结果
            result = {
                "status": "success",
                "message": f"Draw.io 图表上传成功: {file_name}",
                "page_id": updated_page.id,
                "title": updated_page.title,
                "space": updated_page.space.key,
                "version": (
                    updated_page.version.number if updated_page.version else 1
                ),
                "url": (
                    f"{config.confluence_base_url}{updated_page.web_url}"
                    if updated_page.web_url
                    else None
                ),
                "attachment_id": attachment_info.get("id"),
                "attachment_name": file_name,
                "insert_position_matched": insert_position_matched,
            }

            if params.insert_position and not insert_position_matched:
                result["message"] += (
                    f"（注意：未找到标题 '{params.insert_position}'，已追加到页面末尾）"
                )

            logger.info(f"draw.io 图表上传完成: {params.page_id}")
            return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"上传 draw.io 图表失败: {e}", exc_info=True)
        return _handle_error(e)


# ============== 服务器入口 ==============


def main() -> None:
    """主入口函数"""
    logger.info("启动 Confluence MCP 服务器")
    logger.info(f"Confluence URL: {config.confluence_base_url}")
    logger.info("默认 Mermaid 渲染模式: macro（Confluence 原生宏）")
    try:
        from .converters.mermaid_local_renderer import MermaidLocalRenderer
        logger.info(f"Mermaid CLI 可用（image 模式）: {MermaidLocalRenderer.check_mmdc_available()}")
    except ImportError:
        logger.info("Mermaid CLI 不可用（image 模式不可用）")

    try:
        mcp.run()
    except KeyboardInterrupt:
        logger.info("服务器已停止")
    except Exception as e:
        logger.error(f"服务器错误: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
