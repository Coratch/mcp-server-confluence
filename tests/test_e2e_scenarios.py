"""端到端场景测试

针对 Confluence MCP Server 的四个核心工具函数进行端到端测试，
覆盖读取、创建、更新、搜索等完整业务场景。
使用真实 wiki 场景的 Storage Format 样本数据驱动测试。
"""
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# server.py 在模块级别调用 get_config()，需要在导入前设置环境变量
# conftest.py 的 setup_env fixture 在 collection 阶段尚未执行
os.environ.setdefault("CONFLUENCE_BASE_URL", "https://wiki.test.com")
os.environ.setdefault("CONFLUENCE_API_TOKEN", "test-token-for-import")
os.environ.setdefault("CONFLUENCE_DEFAULT_SPACE", "DEV")

from confluence_mcp.server import (
    CreatePageInput,
    ReadPageInput,
    ResponseFormat,
    SearchPagesInput,
    UpdatePageInput,
    confluence_create_page,
    confluence_read_page,
    confluence_search_pages,
    confluence_update_page,
)
from tests.conftest import make_page, make_search_result
from tests.sample_data import (
    API_DOC_STORAGE,
    DRAWIO_STORAGE,
    MEETING_NOTES_STORAGE,
    MIXED_DIAGRAM_STORAGE,
    MULTI_DRAWIO_STORAGE,
    TECH_DESIGN_STORAGE,
)


# ============== 搜索场景测试 ==============


class TestSearchScenarios:
    """搜索场景端到端测试

    验证 confluence_search_pages 工具函数在各种场景下的行为，
    包括正常搜索返回结果、JSON 格式输出、空结果处理等。
    """

    @pytest.mark.asyncio
    @patch("confluence_mcp.server.ConfluenceClient")
    async def test_search_returns_matching_pages(self, MockClient):
        """搜索返回匹配的页面结果

        验证搜索关键词能正确传递给 CQL 查询，
        返回的 Markdown 格式结果包含页面标题、ID��摘要等信息。
        """
        # 准备 mock 数据：模拟两个匹配的搜索结果
        mock_results = [
            make_search_result(
                result_id="300001",
                title="API 接口设计文档",
                space_key="DEV",
                excerpt="本文档描述了 RESTful API 的设计规范...",
            ),
            make_search_result(
                result_id="300002",
                title="API 网关配置指南",
                space_key="OPS",
                excerpt="网关路由配置和限流策略说明...",
            ),
        ]

        mock_client = AsyncMock()
        mock_client.search_pages = AsyncMock(return_value=mock_results)
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)

        # 执行搜索（通过 .fn 访问被 @mcp.tool 装饰器包装的原始异步函数）
        params = SearchPagesInput(query="API 文档")
        result = await confluence_search_pages.fn(params)

        # 验证返回结果是 Markdown 格式
        assert "搜索结果" in result
        assert "API 文档" in result
        assert "**2**" in result  # 找到 2 个结果

        # 验证两个结果的标题和 ID 都在输出中
        assert "API 接口设计文档" in result
        assert "300001" in result
        assert "API 网关配置指南" in result
        assert "300002" in result

        # 验证摘要信息出现在结果中
        assert "RESTful API" in result
        assert "网关路由配置" in result

        # 验证 CQL 查询参数正确传递
        mock_client.search_pages.assert_called_once()
        call_kwargs = mock_client.search_pages.call_args
        assert "API 文档" in call_kwargs.kwargs["cql"]
        assert call_kwargs.kwargs["limit"] == 25  # 默认 limit

    @pytest.mark.asyncio
    @patch("confluence_mcp.server.ConfluenceClient")
    async def test_search_json_format(self, MockClient):
        """搜索结果支持 JSON 格式输出

        验证 response_format=json 时返回结构化的 JSON 数据，
        包含 query、space_key、total、limit 和 results 字段。
        """
        mock_results = [
            make_search_result(
                result_id="400001",
                title="技术方案评审模板",
                space_key="TECH",
                excerpt="标准化的技术方案评审流程...",
            ),
        ]

        mock_client = AsyncMock()
        mock_client.search_pages = AsyncMock(return_value=mock_results)
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)

        # 使用 JSON 格式搜索，并指定 space_key
        params = SearchPagesInput(
            query="技术方案",
            space_key="TECH",
            limit=10,
            response_format=ResponseFormat.JSON,
        )
        result = await confluence_search_pages.fn(params)

        # 解析 JSON 结果
        data = json.loads(result)

        # 验证顶层结构字段
        assert data["query"] == "技术方案"
        assert data["space_key"] == "TECH"
        assert data["total"] == 1
        assert data["limit"] == 10

        # 验证 results 数组
        assert len(data["results"]) == 1
        page = data["results"][0]
        assert page["id"] == "400001"
        assert page["title"] == "技术方案评审模板"
        assert page["space"] == "TECH"
        assert page["excerpt"] == "标准化的技术方案评审流程..."
        assert page["url"] is not None
        assert "400001" in page["url"]

        # 验证 CQL 中包含 space 过滤条件
        call_kwargs = mock_client.search_pages.call_args
        cql = call_kwargs.kwargs["cql"]
        assert "TECH" in cql
        assert call_kwargs.kwargs["limit"] == 10

    @pytest.mark.asyncio
    @patch("confluence_mcp.server.ConfluenceClient")
    async def test_search_empty_result(self, MockClient):
        """空搜索结果不会报错

        验证当搜索无匹配结果时，函数正常返回而不抛出异常，
        且返回内容中包含"未找到"的友好提示。
        """
        mock_client = AsyncMock()
        mock_client.search_pages = AsyncMock(return_value=[])
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)

        # 搜索一个不会有结果的关键词（通过 .fn 调用原始函数）
        params = SearchPagesInput(query="完全不存在的内容xyz")
        result = await confluence_search_pages.fn(params)

        # 验证不会抛出异常，且结果中有友好提示
        assert "搜索结果" in result
        assert "**0**" in result  # 找到 0 个结果
        assert "未找到匹配的页面" in result

        # 验证 API 仍然被正确调用
        mock_client.search_pages.assert_called_once()
