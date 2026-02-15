"""配置管理"""
import os
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .utils.exceptions import ConfigurationError


class ConfluenceConfig(BaseSettings):
    """Confluence 配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Confluence 配置
    confluence_base_url: str = Field(
        default="https://confluence.example.com",
        description="Confluence 实例 URL"
    )
    confluence_api_token: str = Field(
        ...,
        description="Personal Access Token"
    )
    confluence_default_space: Optional[str] = Field(
        default=None,
        description="默认空间键"
    )
    confluence_timeout: int = Field(
        default=30,
        description="API 请求超时时间（秒）"
    )

    # 日志配置
    log_level: str = Field(
        default="INFO",
        description="日志级别"
    )

    @field_validator("confluence_base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """验证并规范化 base URL"""
        v = v.rstrip("/")
        if not v.startswith(("http://", "https://")):
            raise ConfigurationError(f"Invalid base URL: {v}")
        return v

    @field_validator("confluence_timeout")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """验证超时时间"""
        if v <= 0:
            raise ConfigurationError("Timeout must be positive")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """验证日志级别"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v = v.upper()
        if v not in valid_levels:
            raise ConfigurationError(f"Invalid log level: {v}")
        return v

    @property
    def api_base_url(self) -> str:
        """获取 API 基础 URL"""
        return f"{self.confluence_base_url}/rest/api"


# 全局配置实例
_config: Optional[ConfluenceConfig] = None


def get_config() -> ConfluenceConfig:
    """获取配置实例（单例模式）"""
    global _config
    if _config is None:
        _config = ConfluenceConfig()
    return _config


def reset_config() -> None:
    """重置配置（主要用于测试）"""
    global _config
    _config = None
