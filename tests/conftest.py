"""共享测试 fixtures"""
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from confluence_mcp.api.models import Page, PageBody, PageSpace, PageVersion, SearchResult
from confluence_mcp.config import reset_config


# ============== 环境初始化 ==============

@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    """每个测试自动设置必要的环境变量"""
    monkeypatch.setenv("CONFLUENCE_BASE_URL", "https://wiki.test.com")
    monkeypatch.setenv("CONFLUENCE_API_TOKEN", "test-token-12345")
    monkeypatch.setenv("CONFLUENCE_DEFAULT_SPACE", "DEV")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    reset_config()
    yield
    reset_config()


# ============== Page 工厂 ==============

def make_page(
    page_id: str = "100001",
    title: str = "测试页面",
    space_key: str = "DEV",
    version_number: int = 1,
    storage_content: str = "<p>Hello</p>",
    web_url: str = "/pages/viewpage.action?pageId=100001",
) -> Page:
    """构造 Page 对象的工厂函数"""
    return Page(
        id=page_id,
        type="page",
        status="current",
        title=title,
        space=PageSpace(key=space_key, name=f"Space {space_key}"),
        version=PageVersion(number=version_number, when=datetime(2025, 1, 1)),
        body=PageBody(storage={"value": storage_content, "representation": "storage"}),
        _links={"webui": web_url},
    )


def make_search_result(
    result_id: str = "200001",
    title: str = "搜索结果页面",
    space_key: str = "DEV",
    excerpt: str = "这是搜索摘要...",
) -> SearchResult:
    """构造 SearchResult 对象的工厂函数"""
    return SearchResult(
        id=result_id,
        type="page",
        title=title,
        space=PageSpace(key=space_key),
        excerpt=excerpt,
        url=f"/pages/viewpage.action?pageId={result_id}",
        last_modified=datetime(2025, 6, 15, 10, 30),
    )


# ============== Mock Client ==============

@pytest.fixture
def mock_confluence_client():
    """创建 mock 的 ConfluenceClient"""
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client
