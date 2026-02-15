"""测试配置模块"""
import os
import pytest

from confluence_mcp.config import ConfluenceConfig, get_config, reset_config
from confluence_mcp.utils.exceptions import ConfigurationError


class TestConfluenceConfig:
    """测试 ConfluenceConfig 类"""

    def setup_method(self):
        """每个测试前重置配置和环境变量"""
        reset_config()
        # 清理可能影响测试的环境变量
        for key in ["CONFLUENCE_BASE_URL", "CONFLUENCE_API_TOKEN",
                    "CONFLUENCE_TIMEOUT", "LOG_LEVEL", "CONFLUENCE_DEFAULT_SPACE"]:
            os.environ.pop(key, None)

    def test_default_values(self):
        """测试默认值"""
        # 设置必需的环境变量
        os.environ["CONFLUENCE_API_TOKEN"] = "test_token"

        config = ConfluenceConfig()

        assert config.confluence_base_url == "https://confluence.example.com"
        assert config.confluence_api_token == "test_token"
        assert config.confluence_timeout == 30
        assert config.log_level == "INFO"

    def test_custom_values(self):
        """测试自定义值"""
        os.environ["CONFLUENCE_BASE_URL"] = "https://custom.wiki.com"
        os.environ["CONFLUENCE_API_TOKEN"] = "custom_token"
        os.environ["CONFLUENCE_TIMEOUT"] = "60"
        os.environ["LOG_LEVEL"] = "DEBUG"

        config = ConfluenceConfig()

        assert config.confluence_base_url == "https://custom.wiki.com"
        assert config.confluence_api_token == "custom_token"
        assert config.confluence_timeout == 60
        assert config.log_level == "DEBUG"

    def test_base_url_normalization(self):
        """测试 URL 规��化"""
        os.environ["CONFLUENCE_BASE_URL"] = "https://wiki.example.com/"
        os.environ["CONFLUENCE_API_TOKEN"] = "test_token"

        config = ConfluenceConfig()

        # 应该移除尾部斜杠
        assert config.confluence_base_url == "https://wiki.example.com"

    def test_invalid_base_url(self):
        """测试无效的 base URL"""
        os.environ["CONFLUENCE_BASE_URL"] = "invalid_url"
        os.environ["CONFLUENCE_API_TOKEN"] = "test_token"

        with pytest.raises(ConfigurationError):
            ConfluenceConfig()

    def test_invalid_timeout(self):
        """测试无效的超时时间"""
        os.environ["CONFLUENCE_API_TOKEN"] = "test_token"
        os.environ["CONFLUENCE_TIMEOUT"] = "-1"

        with pytest.raises(ConfigurationError):
            ConfluenceConfig()

    def test_invalid_log_level(self):
        """测试无效的日志级别"""
        os.environ["CONFLUENCE_API_TOKEN"] = "test_token"
        os.environ["LOG_LEVEL"] = "INVALID"

        with pytest.raises(ConfigurationError):
            ConfluenceConfig()

    def test_api_base_url(self):
        """测试 API base URL 属性"""
        os.environ["CONFLUENCE_BASE_URL"] = "https://wiki.example.com"
        os.environ["CONFLUENCE_API_TOKEN"] = "test_token"

        config = ConfluenceConfig()

        assert config.api_base_url == "https://wiki.example.com/rest/api"

    def test_get_config_singleton(self):
        """测试配置单例模式"""
        os.environ["CONFLUENCE_API_TOKEN"] = "test_token"

        config1 = get_config()
        config2 = get_config()

        # 应该返回同一个实例
        assert config1 is config2

    def test_reset_config(self):
        """测试重置配置"""
        os.environ["CONFLUENCE_API_TOKEN"] = "test_token"

        config1 = get_config()
        reset_config()
        config2 = get_config()

        # 应该是不同的实例
        assert config1 is not config2
