"""Confluence MCP 服务器

基于 Python + FastMCP 的 Confluence MCP 服务器，提供通过 MCP 协议访问 Confluence API 的能力。
支持 Markdown 与 Confluence Storage Format 的双向转换，特别支持 Mermaid 图表的本地渲染。

服务器命名遵循 MCP 规范：confluence_mcp
"""
import json
import os
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx
from fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .api.client import ConfluenceClient
from .config import get_config
from .converters.markdown_to_storage import MarkdownToStorageConverter
from .converters.mermaid_handler import MermaidHandler

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
    use_local_mermaid_render: bool = Field(
        default=True,
        description="是否使用本地 Mermaid 渲染（需要安装 mermaid-cli）。"
        "如果为 True 且 mermaid-cli 可用，将渲染为图片上传；"
        "否则使用代码块 + 在线编辑器链接方式",
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
    use_local_mermaid_render: bool = Field(
        default=True,
        description=(
            "是否使用本地 Mermaid 渲染（需要 mermaid-cli）。"
            "如果为 True 且 mermaid-cli 可用，将 Mermaid 代码渲染为图片并上传。"
            "如果为 False 或 mermaid-cli 不可用，使用代码块方式。"
        ),
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
    - Mermaid 图表渲染（本地渲染为图片或使用在线编辑器链接）
    - 创建子页面（通过 parent_id 参数）

    Mermaid 处理策略：
    - use_local_mermaid_render=True（默认）：
      如果 mermaid-cli 可用，将 Mermaid 代码渲染为 PNG 图片并上传为附件
    - use_local_mermaid_render=False 或 mermaid-cli 不可用：
      使用可折叠代码块 + Mermaid Live Editor 链接

    Args:
        params (CreatePageInput): 包含以下字段：
            - space_key (str): Confluence 空间键
            - title (str): 页面标题
            - markdown_content (str): Markdown 内容
            - parent_id (Optional[str]): 父页面 ID
            - use_local_mermaid_render (bool): 是否本地渲染 Mermaid

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

        async with ConfluenceClient() as client:
            # 先创建页面（不包含 Mermaid 图片）
            # 转换 Markdown 到 Storage Format（不使用本地渲染）
            storage_content, _ = await md_to_storage.convert(
                params.markdown_content,
                use_local_mermaid=False
            )

            # 创建页面
            page = await client.create_page(
                space_key=params.space_key,
                title=params.title,
                body_storage=storage_content,
                parent_id=params.parent_id,
            )

            logger.info(f"页面创建成功: {page.id}")

            # 如果需要本地渲染 Mermaid，重新转换并更新页面
            mermaid_render_method = "code_block"
            attachments_uploaded = 0
            
            if params.use_local_mermaid_render and has_mermaid:
                from .converters.mermaid_local_renderer import MermaidLocalRenderer
                
                if MermaidLocalRenderer.check_mmdc_available():
                    logger.info(f"使用本地渲染 {len(mermaid_blocks)} 个 Mermaid 图表")
                    
                    # 使用本地渲染重新转换
                    storage_with_images, attachments = await md_to_storage.convert(
                        params.markdown_content,
                        use_local_mermaid=True,
                        page_id=page.id,
                        confluence_client=client
                    )
                    
                    # 更新页面内容
                    if attachments:
                        page = await client.update_page(
                            page_id=page.id,
                            title=params.title,
                            body_storage=storage_with_images,
                            version_number=page.version.number
                        )
                        mermaid_render_method = "local_image"
                        attachments_uploaded = len(attachments)
                        logger.info(f"已上传 {attachments_uploaded} 个 Mermaid 图片")
                else:
                    logger.info("mermaid-cli 不可用，使用代码块显示")

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
                "mermaid_render_method": mermaid_render_method,
                "mermaid_diagrams_count": len(mermaid_blocks) if has_mermaid else 0,
                "mermaid_images_uploaded": attachments_uploaded,
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
            - use_local_mermaid_render (bool): 是否本地渲染 Mermaid

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

            # 决定是否使用本地渲染
            use_local_render = False
            mermaid_render_method = "none"
            attachments_uploaded = 0

            if params.use_local_mermaid_render and has_mermaid:
                from .converters.mermaid_local_renderer import MermaidLocalRenderer
                if MermaidLocalRenderer.check_mmdc_available():
                    use_local_render = True
                    mermaid_render_method = "local_image"
                else:
                    mermaid_render_method = "code_block"
            elif has_mermaid:
                mermaid_render_method = "code_block"

            # 转换 Markdown 到 Storage Format
            storage_content, attachments = await md_to_storage.convert(
                params.markdown_content,
                use_local_mermaid=use_local_render,
                page_id=params.page_id if use_local_render else None,
                confluence_client=client if use_local_render else None
            )
            
            attachments_uploaded = len(attachments) if attachments else 0

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
                "mermaid_render_method": mermaid_render_method,
                "mermaid_diagrams_count": len(mermaid_blocks) if has_mermaid else 0,
                "mermaid_images_uploaded": attachments_uploaded,
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


# ============== 服务器入口 ==============


def main() -> None:
    """主入口函数"""
    logger.info("启动 Confluence MCP 服务器")
    logger.info(f"Confluence URL: {config.confluence_base_url}")
    from .converters.mermaid_local_renderer import MermaidLocalRenderer
    logger.info(f"Mermaid CLI 可用: {MermaidLocalRenderer.check_mmdc_available()}")

    try:
        mcp.run()
    except KeyboardInterrupt:
        logger.info("服务器已停止")
    except Exception as e:
        logger.error(f"服务器错误: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
