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
