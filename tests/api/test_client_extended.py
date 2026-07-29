"""APIClient 扩展测试 - 边界场景"""

from src.api.client import APIClient
from src.api.exceptions import APIError, AuthenticationError, NotFoundError


class TestAPIClientBoundary:
    """APIClient 边界场景测试"""

    def test_init_with_empty_values(self):
        """测试空值初始化"""
        client = APIClient(base_url="", api_key="", timeout=30)
        assert client.base_url == ""
        assert client.token == ""

    def test_init_with_trailing_slash(self):
        """测试带斜杠的URL"""
        client = APIClient(base_url="https://api.example.com/", api_key="key")
        # 应该正确处理尾部斜杠
        assert "api.example.com" in client.base_url

    def test_init_with_api_key(self):
        """测试使用 api_key 初始化"""
        client = APIClient(base_url="https://api.example.com", api_key="test-key")
        assert client.token == "test-key"

    def test_init_with_token(self):
        """测试使用 token 初始化"""
        client = APIClient(base_url="https://api.example.com", token="test-token")
        assert client.token == "test-token"


class TestAPIExceptionsBoundary:
    """API 异常边界测试"""

    def test_api_error_with_status(self):
        """测试带状态码的API错误"""
        error = APIError("Test error", status_code=500)
        assert error.status_code == 500
        assert error.message == "Test error"

    def test_api_error_default_status(self):
        """测试默认状态码的API错误"""
        error = APIError("Test error")
        assert error.status_code == 500  # 默认状态码

    def test_authentication_error(self):
        """测试认证错误"""
        error = AuthenticationError("Auth failed")
        assert str(error) == "Auth failed"

    def test_not_found_error(self):
        """测试未找到错误"""
        error = NotFoundError("Task not found")
        assert str(error) == "Task not found"
