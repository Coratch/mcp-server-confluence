#!/usr/bin/env python3
"""测试 Confluence MCP 服务器的功能"""

import asyncio
import json
import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from confluence_mcp.server import (
    confluence_read_page,
    confluence_create_page,
    confluence_update_page,
    confluence_search_pages,
    ReadPageInput,
    CreatePageInput,
    UpdatePageInput,
    SearchPagesInput,
    ResponseFormat
)


async def test_search():
    """测试搜索功能"""
    print("\n=== 测试搜索功能 ===")
    
    params = SearchPagesInput(
        query="test",
        limit=5,
        response_format=ResponseFormat.JSON
    )
    
    result = await confluence_search_pages(params)
    data = json.loads(result)
    
    print(f"搜索结果数: {data.get('total_count', 0)}")
    if data.get("results"):
        print(f"第一个结果: {data['results'][0].get('title')}")
    
    return data


async def test_create_page():
    """测试创建页面"""
    print("\n=== 测试创建页面 ===")
    
    markdown_content = """# 测试页面

## 概述

这是一个通过 MCP 服务器创建的测试页面。

## Mermaid 图表

```mermaid
graph TD
    A[开始] --> B[处理]
    B --> C{判断}
    C -->|是| D[结果1]
    C -->|否| E[结果2]
```

## 代码示例

```python
def hello_world():
    print("Hello from Confluence MCP!")
```

## 列表

- 项目 1
- 项目 2
  - 子项目 2.1
  - 子项目 2.2
- 项目 3

## 表格

| 列 1 | 列 2 | 列 3 |
|------|------|------|
| A1   | B1   | C1   |
| A2   | B2   | C2   |
"""
    
    params = CreatePageInput(
        space_key=os.getenv("CONFLUENCE_DEFAULT_SPACE", "TEST"),
        title="MCP 测试页面",
        markdown_content=markdown_content,
        use_local_mermaid_render=True
    )
    
    try:
        result = await confluence_create_page(params)
        data = json.loads(result)
        print(f"页面创建成功: ID={data['id']}")
        print(f"页面 URL: {data.get('url')}")
        print(f"Mermaid 渲染方式: {data.get('mermaid_render_method')}")
        return data
    except Exception as e:
        print(f"创建页面失败: {e}")
        return None


async def test_read_page(page_id: str):
    """测试读取页面"""
    print(f"\n=== 测试读取页面 {page_id} ===")
    
    params = ReadPageInput(
        page_id=page_id,
        response_format=ResponseFormat.MARKDOWN
    )
    
    result = await confluence_read_page(params)
    print("页面内容（前 500 字符）:")
    print(result[:500])
    
    return result


async def test_update_page(page_id: str):
    """测试更新页面"""
    print(f"\n=== 测试更新页面 {page_id} ===")
    
    markdown_content = """# 更新后的测试页面

## 更新时间

页面已于测试时更新。

## 新增内容

这是更新后新增的内容。

## Mermaid 序列图

```mermaid
sequenceDiagram
    participant A as Alice
    participant B as Bob
    A->>B: Hello Bob!
    B->>A: Hi Alice!
    A->>B: How are you?
    B->>A: I'm fine, thanks!
```
"""
    
    params = UpdatePageInput(
        page_id=page_id,
        markdown_content=markdown_content,
        title="MCP 测试页面（已更新）",
        use_local_mermaid_render=True
    )
    
    try:
        result = await confluence_update_page(params)
        data = json.loads(result)
        print(f"页面更新成功: 版本 {data.get('previous_version')} -> {data.get('version')}")
        return data
    except Exception as e:
        print(f"更新页面失败: {e}")
        return None


async def main():
    """主测试函数"""
    print("=" * 60)
    print("Confluence MCP 服务器功能测试")
    print("=" * 60)
    
    # 检查环境变量
    if not os.getenv("CONFLUENCE_API_TOKEN"):
        print("错误: 未设置 CONFLUENCE_API_TOKEN 环境变量")
        return
    
    print(f"Confluence URL: {os.getenv('CONFLUENCE_BASE_URL')}")
    print(f"默认空间: {os.getenv('CONFLUENCE_DEFAULT_SPACE')}")
    
    # 测试搜索
    await test_search()
    
    # 询问是否创建测试页面
    create = input("\n是否创建测试页面？(y/n): ")
    if create.lower() == 'y':
        page_data = await test_create_page()
        
        if page_data and page_data.get('id'):
            page_id = page_data['id']
            
            # 测试读取
            await asyncio.sleep(2)  # 等待页面创建完成
            await test_read_page(page_id)
            
            # 询问是否更新
            update = input("\n是否更新测试页面？(y/n): ")
            if update.lower() == 'y':
                await test_update_page(page_id)
    
    print("\n测试完成！")


if __name__ == "__main__":
    asyncio.run(main())