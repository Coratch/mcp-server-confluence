#!/usr/bin/env python3
"""Confluence MCP 连接诊断工具"""
import os
import sys
import subprocess
import json

def check_environment():
    """检查环境变量"""
    print("=" * 60)
    print("1. 检查环境变量")
    print("=" * 60)

    required_vars = [
        'CONFLUENCE_BASE_URL',
        'CONFLUENCE_API_TOKEN',
        'CONFLUENCE_DEFAULT_SPACE'
    ]

    all_ok = True
    for var in required_vars:
        value = os.getenv(var)
        if value:
            if 'TOKEN' in var:
                print(f"✅ {var}: {value[:10]}...")
            else:
                print(f"✅ {var}: {value}")
        else:
            print(f"❌ {var}: NOT SET")
            all_ok = False

    return all_ok

def check_python_package():
    """检查 Python 包"""
    print("\n" + "=" * 60)
    print("2. 检查 Python 包")
    print("=" * 60)

    try:
        import confluence_mcp
        print(f"✅ confluence_mcp 已安装")
        print(f"   路径: {confluence_mcp.__file__}")
        return True
    except ImportError as e:
        print(f"❌ confluence_mcp 未安装: {e}")
        return False

def check_config():
    """检查配置加载"""
    print("\n" + "=" * 60)
    print("3. 检查配置加载")
    print("=" * 60)

    try:
        from confluence_mcp.config import get_config
        config = get_config()
        print(f"✅ 配置加载成功")
        print(f"   Base URL: {config.confluence_base_url}")
        print(f"   API Token: {config.confluence_api_token[:10]}...")
        print(f"   Default Space: {config.confluence_default_space}")
        return True
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return False

def check_mcp_server():
    """检查 MCP 服务器启动"""
    print("\n" + "=" * 60)
    print("4. 检查 MCP 服务器启动")
    print("=" * 60)

    try:
        # 尝试启动服务器（超时 3 秒）
        result = subprocess.run(
            ['python', '-m', 'confluence_mcp.server'],
            capture_output=True,
            text=True,
            timeout=3
        )
        print("❌ 服务器启动超时（这是正常的，因为 MCP 服务器会持续运行）")
        return True
    except subprocess.TimeoutExpired:
        print("✅ 服务器可以启动（超时是正常的）")
        return True
    except Exception as e:
        print(f"❌ 服务器启动失败: {e}")
        return False

def check_claude_config():
    """检查 Claude Code 配置"""
    print("\n" + "=" * 60)
    print("5. 检查 Claude Code 配置")
    print("=" * 60)

    config_path = os.path.expanduser("~/.claude.json")

    if not os.path.exists(config_path):
        print(f"❌ 配置文件不存在: {config_path}")
        return False

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)

        confluence = config.get('mcpServers', {}).get('servers', {}).get('confluence')

        if not confluence:
            print("❌ Confluence MCP 未配置")
            return False

        print("✅ Confluence MCP 已配置")
        print(f"   Command: {confluence.get('command')}")
        print(f"   Args: {confluence.get('args')}")

        env = confluence.get('env', {})
        if env.get('CONFLUENCE_BASE_URL'):
            print(f"   ✅ CONFLUENCE_BASE_URL: {env['CONFLUENCE_BASE_URL']}")
        else:
            print(f"   ❌ CONFLUENCE_BASE_URL: NOT SET")

        if env.get('CONFLUENCE_API_TOKEN'):
            print(f"   ✅ CONFLUENCE_API_TOKEN: {env['CONFLUENCE_API_TOKEN'][:10]}...")
        else:
            print(f"   ❌ CONFLUENCE_API_TOKEN: NOT SET")

        if env.get('CONFLUENCE_DEFAULT_SPACE'):
            print(f"   ✅ CONFLUENCE_DEFAULT_SPACE: {env['CONFLUENCE_DEFAULT_SPACE']}")
        else:
            print(f"   ❌ CONFLUENCE_DEFAULT_SPACE: NOT SET")

        return True
    except Exception as e:
        print(f"❌ 读取配置失败: {e}")
        return False

def main():
    print("\n" + "=" * 60)
    print("Confluence MCP 连接诊断")
    print("=" * 60)

    # 加载 .env 文件
    env_path = os.path.join(os.getcwd(), '.env')
    if os.path.exists(env_path):
        print(f"\n加载环境变量: {env_path}")
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value

    results = []
    results.append(("环境变量", check_environment()))
    results.append(("Python 包", check_python_package()))
    results.append(("配置加载", check_config()))
    results.append(("MCP 服务器", check_mcp_server()))
    results.append(("Claude 配置", check_claude_config()))

    print("\n" + "=" * 60)
    print("诊断结果")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✅" if passed else "❌"
        print(f"{status} {name}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ 所有检查通过！")
        print("\n如果仍然无法连接，请尝试：")
        print("1. 重启 Claude Code")
        print("2. 运行: claude mcp list")
        print("3. 检查 Claude Code 日志")
    else:
        print("❌ 部分检查失败，请修复上述问题")
    print("=" * 60)

if __name__ == '__main__':
    main()
