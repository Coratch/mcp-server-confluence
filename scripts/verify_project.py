#!/usr/bin/env python3
"""项目完整性验证脚本

检查所有必需的文件是否存在，以及基本的代码语法是否正确。
"""
import os
import sys
from pathlib import Path


def check_file_exists(filepath: str, description: str) -> bool:
    """检查文件是否存在"""
    if os.path.exists(filepath):
        print(f"✅ {description}: {filepath}")
        return True
    else:
        print(f"❌ {description} 缺失: {filepath}")
        return False


def check_directory_exists(dirpath: str, description: str) -> bool:
    """检查目录是否存在"""
    if os.path.isdir(dirpath):
        print(f"✅ {description}: {dirpath}")
        return True
    else:
        print(f"❌ {description} 缺失: {dirpath}")
        return False


def main():
    """主验证函数"""
    print("=" * 60)
    print("Confluence MCP 服务器 - 项目完整性验证")
    print("=" * 60)

    all_checks_passed = True

    # 检查目录结构
    print("\n📁 检查目录结构...")
    directories = [
        ("src/confluence_mcp", "主模块目录"),
        ("src/confluence_mcp/api", "API 模块目录"),
        ("src/confluence_mcp/converters", "转换器模块目录"),
        ("src/confluence_mcp/utils", "工具模块目录"),
        ("tests", "测试目录"),
        ("examples", "示例目录"),
    ]

    for dirpath, description in directories:
        if not check_directory_exists(dirpath, description):
            all_checks_passed = False

    # 检查核心文件
    print("\n📄 检查核心文件...")
    core_files = [
        ("pyproject.toml", "项目配置文件"),
        ("README.md", "主文档"),
        (".env.example", "环境变量模板"),
        (".gitignore", "Git 忽略规则"),
        ("src/confluence_mcp/__init__.py", "主模块初始化"),
        ("src/confluence_mcp/server.py", "MCP 服务器"),
        ("src/confluence_mcp/config.py", "配置管理"),
    ]

    for filepath, description in core_files:
        if not check_file_exists(filepath, description):
            all_checks_passed = False

    # 检查 API 模块
    print("\n🔌 检查 API 模块...")
    api_files = [
        ("src/confluence_mcp/api/__init__.py", "API 模块初始化"),
        ("src/confluence_mcp/api/client.py", "API 客户端"),
        ("src/confluence_mcp/api/models.py", "数据模型"),
    ]

    for filepath, description in api_files:
        if not check_file_exists(filepath, description):
            all_checks_passed = False

    # 检查转换器模块
    print("\n🔄 检查转换器模块...")
    converter_files = [
        ("src/confluence_mcp/converters/__init__.py", "转换器模块初始化"),
        ("src/confluence_mcp/converters/mermaid_handler.py", "Mermaid 转换器"),
        ("src/confluence_mcp/converters/storage_to_markdown.py", "Storage → Markdown"),
        ("src/confluence_mcp/converters/markdown_to_storage.py", "Markdown → Storage"),
    ]

    for filepath, description in converter_files:
        if not check_file_exists(filepath, description):
            all_checks_passed = False

    # 检查工具模块
    print("\n🛠️  检查工具模块...")
    util_files = [
        ("src/confluence_mcp/utils/__init__.py", "工具模块初始化"),
        ("src/confluence_mcp/utils/logger.py", "日志工具"),
        ("src/confluence_mcp/utils/exceptions.py", "异常定义"),
    ]

    for filepath, description in util_files:
        if not check_file_exists(filepath, description):
            all_checks_passed = False

    # 检查测试文件
    print("\n🧪 检查测试文件...")
    test_files = [
        ("tests/__init__.py", "测试模块初始化"),
        ("tests/test_mermaid_handler.py", "Mermaid 转换测试"),
        ("tests/test_config.py", "配置管理测试"),
    ]

    for filepath, description in test_files:
        if not check_file_exists(filepath, description):
            all_checks_passed = False

    # 检查示例文件
    print("\n📚 检查示例文件...")
    example_files = [
        ("examples/sample_page.md", "示例页面"),
        ("examples/usage_example.py", "使用示例"),
        ("examples/QUICKSTART.md", "快速入门指南"),
    ]

    for filepath, description in example_files:
        if not check_file_exists(filepath, description):
            all_checks_passed = False

    # 检查 Python 语法
    print("\n🐍 检查 Python 语法...")
    try:
        import py_compile
        python_files = [
            "src/confluence_mcp/server.py",
            "src/confluence_mcp/config.py",
            "src/confluence_mcp/api/client.py",
            "src/confluence_mcp/api/models.py",
            "src/confluence_mcp/converters/mermaid_handler.py",
            "src/confluence_mcp/converters/storage_to_markdown.py",
            "src/confluence_mcp/converters/markdown_to_storage.py",
            "src/confluence_mcp/utils/logger.py",
            "src/confluence_mcp/utils/exceptions.py",
        ]

        for filepath in python_files:
            try:
                py_compile.compile(filepath, doraise=True)
                print(f"✅ 语法正确: {filepath}")
            except py_compile.PyCompileError as e:
                print(f"❌ 语法错误: {filepath}")
                print(f"   错误: {e}")
                all_checks_passed = False
    except ImportError:
        print("⚠️  无法检查 Python 语法（py_compile 不可用）")

    # 最终结果
    print("\n" + "=" * 60)
    if all_checks_passed:
        print("✅ 所有检查通过！项目结构完整。")
        print("\n下一步:")
        print("1. 复制 .env.example 为 .env 并配置")
        print("2. 运行: pip install -e .")
        print("3. 运行测试: pytest tests/")
        print("4. 在 Claude Desktop 中配置 MCP 服务器")
        return 0
    else:
        print("❌ 部分检查失败，请检查缺失的文件。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
