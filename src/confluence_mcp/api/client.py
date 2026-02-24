"""Confluence REST API 客户端

提供与 Confluence REST API 交互的异步客户端。
支持重试机制、指数退避和完善的错误处理。
"""
import asyncio
from typing import Any, Dict, List, Optional, TypeVar

import httpx

from ..config import get_config
from ..utils.exceptions import (
    APIError,
    AuthenticationError,
    NotFoundError,
    PermissionError,
)
from ..utils.logger import get_logger
from .models import CreatePageRequest, Page, SearchResult, UpdatePageRequest

logger = get_logger(__name__)

# 类型变量用于泛型返回类型
T = TypeVar("T")

# 重试配置
MAX_RETRIES = 3
RETRY_DELAY_BASE = 1.0  # 基础延迟（秒）
RETRY_DELAY_MAX = 10.0  # 最大延迟（秒）
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}  # 可重试的状态码


class ConfluenceClient:
    """Confluence API 客户端

    提供与 Confluence REST API 交互的异步方法。
    支持以下特性：
    - 自动重试失败请求（指数退避）
    - 详细的错误处理和日志
    - 异步上下文管理器
    """

    def __init__(self) -> None:
        """初始化客户端"""
        self.config = get_config()
        self.base_url = self.config.api_base_url
        self.timeout = self.config.confluence_timeout
        self.max_retries = MAX_RETRIES

        # 创建 HTTP 客户端
        # 注意：不在默认头中设置 Content-Type，因为上传附件时需要 multipart/form-data
        # Content-Type 在 _request_with_retry 中按需设置
        self._auth_headers = {
            "Authorization": f"Bearer {self.config.confluence_api_token}",
            "Accept": "application/json",
        }
        self.client = httpx.AsyncClient(
            headers=self._auth_headers,
            timeout=self.timeout,
        )

    async def close(self) -> None:
        """关闭客户端"""
        await self.client.aclose()

    async def __aenter__(self) -> "ConfluenceClient":
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """异步上下文管理器退出"""
        await self.close()

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """带重试机制的 HTTP 请求

        使用指数退避策略进行重试。

        Args:
            method: HTTP 方法
            url: 请求 URL
            **kwargs: 传递给 httpx 的其他参数

        Returns:
            HTTP 响应对象

        Raises:
            APIError: 所有重试失败后抛出
        """
        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.request(method, url, **kwargs)

                # 检查是否需要重试
                if response.status_code in RETRYABLE_STATUS_CODES:
                    if attempt < self.max_retries:
                        delay = min(
                            RETRY_DELAY_BASE * (2 ** attempt),
                            RETRY_DELAY_MAX
                        )
                        logger.warning(
                            f"请求失败 (状态码: {response.status_code})，"
                            f"第 {attempt + 1}/{self.max_retries} 次重试，"
                            f"等待 {delay:.1f} 秒"
                        )
                        await asyncio.sleep(delay)
                        continue

                return response

            except httpx.TimeoutException as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = min(
                        RETRY_DELAY_BASE * (2 ** attempt),
                        RETRY_DELAY_MAX
                    )
                    logger.warning(
                        f"请求超时，第 {attempt + 1}/{self.max_retries} 次重试，"
                        f"等待 {delay:.1f} 秒"
                    )
                    await asyncio.sleep(delay)
                    continue
                raise APIError(
                    f"请求超时，已重试 {self.max_retries} 次: {str(e)}",
                    status_code=None,
                    response_body=None,
                )

            except httpx.ConnectError as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = min(
                        RETRY_DELAY_BASE * (2 ** attempt),
                        RETRY_DELAY_MAX
                    )
                    logger.warning(
                        f"连接失败，第 {attempt + 1}/{self.max_retries} 次重试，"
                        f"等待 {delay:.1f} 秒"
                    )
                    await asyncio.sleep(delay)
                    continue
                raise APIError(
                    f"连接失败，已重试 {self.max_retries} 次: {str(e)}",
                    status_code=None,
                    response_body=None,
                )

        # 不应该到达这里，但为了类型安全
        if last_exception:
            raise APIError(f"请求失败: {str(last_exception)}")
        raise APIError("请求失败: 未知错误")

    def _handle_error(self, response: httpx.Response) -> None:
        """处理 API 错误响应

        根据不同的状态码抛出对应的异常类型，提供详细的错误信息和建议。

        Args:
            response: HTTP 响应对象

        Raises:
            AuthenticationError: 401 认证失败
            PermissionError: 403 权限不足
            NotFoundError: 404 资源未找到
            APIError: 其他 API 错误
        """
        status_code = response.status_code
        try:
            error_body = response.json()
            message = error_body.get("message", response.text)
        except Exception:
            message = response.text

        # 构建详细的错误消息
        error_details = f"状态码: {status_code}"
        if message:
            error_details += f", 消息: {message}"

        if status_code == 401:
            raise AuthenticationError(
                f"认证失�� ({error_details}). "
                f"请检查 CONFLUENCE_API_TOKEN 是否正确配置。",
                status_code=status_code,
                response_body=message,
            )
        elif status_code == 403:
            raise PermissionError(
                f"权限不足 ({error_details}). "
                f"请确认当前用户有访问该资源的权限。",
                status_code=status_code,
                response_body=message,
            )
        elif status_code == 404:
            raise NotFoundError(
                f"资源未找到 ({error_details}). "
                f"请检查 ID 或路径是否正确。",
                status_code=status_code,
                response_body=message,
            )
        elif status_code == 429:
            # 速率限制错误（通常会被重试机制处理）
            raise APIError(
                f"请求过于频繁 ({error_details}). "
                f"请稍后重试。",
                status_code=status_code,
                response_body=message,
            )
        elif status_code >= 500:
            raise APIError(
                f"服务器错误 ({error_details}). "
                f"请稍后重试或联系管理员。",
                status_code=status_code,
                response_body=message,
            )
        else:
            raise APIError(
                f"API 错误 ({error_details})",
                status_code=status_code,
                response_body=message,
            )

    async def get_page(
        self, page_id: str, expand: Optional[List[str]] = None
    ) -> Page:
        """获取页面详情

        Args:
            page_id: 页面 ID
            expand: 需要扩展的字段列表

        Returns:
            页面对象

        Raises:
            NotFoundError: 页面不存在
            PermissionError: 无权限访问
            APIError: 其他 API 错误
        """
        if expand is None:
            expand = ["body.storage", "version", "space", "ancestors"]

        url = f"{self.base_url}/content/{page_id}"
        params = {"expand": ",".join(expand)}

        logger.info(f"获取页面: {page_id}")
        response = await self._request_with_retry("GET", url, params=params)

        if response.status_code != 200:
            self._handle_error(response)

        data = response.json()
        return Page(**data)

    async def create_page(
        self,
        space_key: str,
        title: str,
        body_storage: str,
        parent_id: Optional[str] = None
    ) -> Page:
        """创建新页面

        Args:
            space_key: 空间键
            title: 页面标题
            body_storage: Storage Format 内容
            parent_id: 父页面 ID（可选）

        Returns:
            创建的页面对象
        
        Raises:
            PermissionError: 无权限在指定空间创建页面
            APIError: 其他 API 错误
        """
        request_data = CreatePageRequest(
            title=title,
            space={"key": space_key},
            body={"storage": {"value": body_storage, "representation": "storage"}},
            ancestors=[{"id": parent_id}] if parent_id else None
        )

        url = f"{self.base_url}/content"
        logger.info(f"创建页面: {title} (空间: {space_key})")

        response = await self._request_with_retry(
            "POST",
            url,
            json=request_data.model_dump(exclude_none=True)
        )

        if response.status_code != 200:
            self._handle_error(response)

        data = response.json()
        logger.info(f"页面创建成功: ID={data.get('id')}, URL={data.get('_links', {}).get('webui')}")
        return Page(**data)

    async def update_page(
        self,
        page_id: str,
        title: str,
        body_storage: str,
        version_number: int
    ) -> Page:
        """更新页面

        Args:
            page_id: 页面 ID
            title: 页面标题
            body_storage: Storage Format 内容
            version_number: 当前版本号（需要递增）

        Returns:
            更新后的页面对象
        
        Raises:
            NotFoundError: 页面不存在
            PermissionError: 无权限更新
            APIError: 版本冲突或其他错误
        """
        request_data = UpdatePageRequest(
            title=title,
            version={"number": version_number + 1},
            body={"storage": {"value": body_storage, "representation": "storage"}}
        )

        url = f"{self.base_url}/content/{page_id}"
        logger.info(f"更新页面: {page_id} (版本: {version_number} -> {version_number + 1})")

        response = await self._request_with_retry(
            "PUT",
            url,
            json=request_data.model_dump(exclude_none=True)
        )

        if response.status_code == 409:
            # 版本冲突特殊处理
            logger.error(f"版本冲突: 页面 {page_id} 已被其他用户修改")
            raise APIError(
                f"版本冲突: 页面已被其他用户修改。请重新获取最新版本后再试。",
                status_code=409,
                response_body=response.text
            )

        if response.status_code != 200:
            self._handle_error(response)

        data = response.json()
        logger.info(f"页面更新成功: ID={page_id}, 新版本={version_number + 1}")
        return Page(**data)

    async def search_pages(
        self,
        cql: str,
        limit: int = 25,
        start: int = 0
    ) -> List[SearchResult]:
        """搜索页面

        Args:
            cql: CQL 查询语句
            limit: 返回结果数量限制
            start: 起始位置

        Returns:
            搜索结果列表
        
        Raises:
            APIError: CQL 语法错误或其他 API 错误
        """
        url = f"{self.base_url}/content/search"
        params = {
            "cql": cql,
            "limit": limit,
            "start": start
        }

        logger.info(f"搜索页面: {cql} (limit={limit}, start={start})")
        response = await self._request_with_retry("GET", url, params=params)

        if response.status_code == 400:
            # CQL 语法错误特殊处理
            logger.error(f"CQL 语法错误: {cql}")
            raise APIError(
                f"CQL 查询语法错误。请检查查询语句: {cql}",
                status_code=400,
                response_body=response.text
            )

        if response.status_code != 200:
            self._handle_error(response)

        data = response.json()
        results = []
        total_size = data.get("totalSize", 0)

        for item in data.get("results", []):
            result = SearchResult(
                id=item["id"],
                type=item["type"],
                title=item["title"],
                space=item.get("space"),
                excerpt=item.get("excerpt"),
                url=item.get("_links", {}).get("webui"),
                last_modified=item.get("lastModified")
            )
            results.append(result)

        logger.info(f"搜索完成: 找到 {len(results)} 条结果 (总计 {total_size} 条)")
        return results

    async def upload_attachment(
        self,
        page_id: str,
        file_path: str,
        file_name: Optional[str] = None,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """上传附件到页面

        Args:
            page_id: 页面 ID  
            file_path: 文件路径
            file_name: 附件名称（可选，默认使用文件名）
            comment: 附件注释（可选）

        Returns:
            附件信息字典

        Raises:
            NotFoundError: 页面不存在
            PermissionError: 无权限上传附件
            APIError: 其他 API 错误
        """
        import os
        from pathlib import Path

        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        if file_name is None:
            file_name = file_path_obj.name

        url = f"{self.base_url}/content/{page_id}/child/attachment"
        
        # 先检查是否已存在同名附件
        check_url = f"{url}?filename={file_name}"
        logger.info(f"检查附件是否存在: {file_name}")
        
        try:
            check_response = await self._request_with_retry("GET", check_url)
            if check_response.status_code == 200:
                data = check_response.json()
                if data.get("size", 0) > 0:
                    # 附件已存在，需要更新
                    existing_id = data["results"][0]["id"]
                    url = f"{self.base_url}/content/{page_id}/child/attachment/{existing_id}/data"
                    logger.info(f"更新现有附件: {file_name} (ID: {existing_id})")
        except Exception as e:
            logger.debug(f"检查附件时出错（可能是新附件）: {e}")

        # 准备文件上传
        with open(file_path_obj, "rb") as f:
            files = {"file": (file_name, f, "application/octet-stream")}
            data = {}
            if comment:
                data["comment"] = comment

            # 使用单独的请求，因为需要 multipart/form-data
            # 添加 X-Atlassian-Token: nocheck 以禁用 XSRF 检查
            response = await self.client.post(
                url,
                files=files,
                data=data,
                headers={"X-Atlassian-Token": "nocheck"},
            )

        if response.status_code not in [200, 201]:
            self._handle_error(response)

        result = response.json()

        # 处理返回数据（可能是单个对象或 results 数组）
        if "results" in result and result["results"]:
            attachment_info = result["results"][0]
        else:
            attachment_info = result

        logger.info(
            f"附件上传成功: {file_name} "
            f"(ID: {attachment_info.get('id')}, "
            f"大小: {attachment_info.get('extensions', {}).get('fileSize', 'N/A')} bytes)"
        )

        return attachment_info

    async def upload_attachment_bytes(
        self,
        page_id: str,
        content: bytes,
        file_name: str,
        content_type: str = "application/octet-stream",
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """从内存字节上传附件到页面

        Args:
            page_id: 页面 ID
            content: 文件内容字节
            file_name: 附件名称
            content_type: MIME 类型
            comment: 附件注释（可选）

        Returns:
            附件信息字典

        Raises:
            NotFoundError: 页面不存在
            PermissionError: 无权限上传附件
            APIError: 其他 API 错误
        """
        url = f"{self.base_url}/content/{page_id}/child/attachment"

        # 先检查是否已存在同名附件
        check_url = f"{url}?filename={file_name}"
        logger.info(f"检查附件是否存在: {file_name}")

        try:
            check_response = await self._request_with_retry("GET", check_url)
            if check_response.status_code == 200:
                data = check_response.json()
                if data.get("size", 0) > 0:
                    existing_id = data["results"][0]["id"]
                    url = f"{self.base_url}/content/{page_id}/child/attachment/{existing_id}/data"
                    logger.info(f"更新现有附件: {file_name} (ID: {existing_id})")
        except Exception as e:
            logger.debug(f"检查附件时出错（可能是新附件）: {e}")

        files = {"file": (file_name, content, content_type)}
        data = {}
        if comment:
            data["comment"] = comment

        # 添加 X-Atlassian-Token: nocheck 以禁用 XSRF 检查
        response = await self.client.post(
            url,
            files=files,
            data=data,
            headers={"X-Atlassian-Token": "nocheck"},
        )

        if response.status_code not in [200, 201]:
            self._handle_error(response)

        result = response.json()
        if "results" in result and result["results"]:
            attachment_info = result["results"][0]
        else:
            attachment_info = result

        logger.info(
            f"附件上传成功: {file_name} "
            f"(ID: {attachment_info.get('id')}, 大小: {len(content)} bytes)"
        )
        return attachment_info

    async def get_attachments(
        self,
        page_id: str,
        filename: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """获取页面的附件列表

        Args:
            page_id: 页面 ID
            filename: 筛选特定文件名（可选）
            limit: 返回结果数量限制

        Returns:
            附件信息列表

        Raises:
            NotFoundError: 页面不存在
            APIError: 其他 API 错误
        """
        url = f"{self.base_url}/content/{page_id}/child/attachment"
        params = {"limit": limit}
        if filename:
            params["filename"] = filename

        logger.info(f"获取页面附件: {page_id}")
        response = await self._request_with_retry("GET", url, params=params)

        if response.status_code != 200:
            self._handle_error(response)

        data = response.json()
        attachments = data.get("results", [])
        
        logger.info(f"找到 {len(attachments)} 个附件")
        return attachments
