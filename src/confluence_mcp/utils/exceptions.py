"""自定义异常类"""


class ConfluenceMCPError(Exception):
    """基础异常类"""
    pass


class ConfigurationError(ConfluenceMCPError):
    """配置错误"""
    pass


class APIError(ConfluenceMCPError):
    """API 调用错误"""
    def __init__(self, message: str, status_code: int | None = None, response_body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class AuthenticationError(APIError):
    """认证错误"""
    pass


class NotFoundError(APIError):
    """资源未找到"""
    pass


class PermissionError(APIError):
    """权限错误"""
    pass


class ConversionError(ConfluenceMCPError):
    """格式转换错误"""
    pass


class ValidationError(ConfluenceMCPError):
    """数据验证错误"""
    pass
