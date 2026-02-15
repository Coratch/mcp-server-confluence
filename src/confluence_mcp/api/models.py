"""数据模型"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PageVersion(BaseModel):
    """页面版本信息"""
    number: int
    when: datetime
    by: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


class PageSpace(BaseModel):
    """空间信息"""
    key: str
    name: Optional[str] = None


class PageBody(BaseModel):
    """页面内容"""
    storage: Optional[Dict[str, Any]] = None
    view: Optional[Dict[str, Any]] = None

    class Config:
        extra = "allow"  # 允许额外字段


class Page(BaseModel):
    """Confluence 页面模型"""
    id: str
    type: str = "page"
    status: str = "current"
    title: str
    space: PageSpace
    version: Optional[PageVersion] = None
    body: Optional[PageBody] = None
    ancestors: Optional[List[Dict[str, Any]]] = None

    # 扩展字段
    links: Optional[Dict[str, Any]] = Field(default=None, alias="_links")

    class Config:
        populate_by_name = True

    @property
    def storage_content(self) -> str:
        """获取 Storage Format 内容"""
        if self.body and self.body.storage:
            return self.body.storage.get("value", "")
        return ""

    @property
    def web_url(self) -> str:
        """获取页面 Web URL"""
        if self.links and "webui" in self.links:
            return self.links["webui"]
        return ""


class SearchResult(BaseModel):
    """搜索结果"""
    id: str
    type: str
    title: str
    space: Optional[PageSpace] = None
    excerpt: Optional[str] = None
    url: Optional[str] = None
    last_modified: Optional[datetime] = None

    class Config:
        populate_by_name = True


class CreatePageRequest(BaseModel):
    """创建页面请求"""
    type: str = "page"
    title: str
    space: Dict[str, str]
    body: Dict[str, Dict[str, str]]
    ancestors: Optional[List[Dict[str, str]]] = None


class UpdatePageRequest(BaseModel):
    """更新页面请求"""
    version: Dict[str, int]
    title: str
    type: str = "page"
    body: Dict[str, Dict[str, str]]
