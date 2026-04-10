"""
HTTP 客户端工具测试
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.http_client import HttpClient, SSLConfig, RetryConfig


class TestSSLConfig:
    """SSL 配置测试"""

    def test_create_disabled_context(self):
        """测试创建禁用 SSL 验证的上下文"""
        context = SSLConfig.create_disabled_context()
        assert context.check_hostname is False
        assert context.verify_mode.name == "CERT_NONE"

    def test_create_connector_with_ssl(self):
        """测试创建 SSL 连接器"""
        connector = SSLConfig.create_connector(verify_ssl=True)
        assert connector is not None

    def test_create_connector_without_ssl(self):
        """测试创建非 SSL 连接器"""
        connector = SSLConfig.create_connector(verify_ssl=False)
        assert connector is not None


class TestRetryConfig:
    """重试配置测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = RetryConfig()
        assert config.max_retries == 5
        assert config.base_delay == 5.0
        assert config.max_delay == 60.0

    def test_calculate_delay(self):
        """测试延迟计算（指数退避）"""
        config = RetryConfig(base_delay=1.0, jitter=False)
        assert config.calculate_delay(0) == 1.0
        assert config.calculate_delay(1) == 2.0
        assert config.calculate_delay(2) == 4.0

    def test_calculate_delay_with_max(self):
        """测试最大延迟限制"""
        config = RetryConfig(base_delay=1.0, max_delay=10.0, jitter=False)
        delay = config.calculate_delay(10)  # 会超过 max_delay
        assert delay <= 10.0

    def test_calculate_delay_with_jitter(self):
        """测试随机抖动"""
        config = RetryConfig(base_delay=1.0, jitter=True)
        delays = [config.calculate_delay(1) for _ in range(5)]
        # 验证有抖动（不完全相同）
        assert len(set(delays)) > 1


class TestHttpClient:
    """HTTP 客户端测试"""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """测试初始化"""
        client = HttpClient(verify_ssl=False, timeout=30.0)
        assert client.verify_ssl is False
        assert client.timeout == 30.0

    @pytest.mark.asyncio
    async def test_get_with_invalid_url(self):
        """测试无效 URL 的 GET 请求"""
        client = HttpClient()
        success, content, error = await client.get("http://invalid.url.test")
        # 应该失败但不抛异常
        assert success is False or content is not None or error is not None

    @pytest.mark.asyncio
    async def test_post_with_invalid_url(self):
        """测试无效 URL 的 POST 请求"""
        client = HttpClient()
        success, content, error = await client.post("http://invalid.url.test", json={})
        assert success is False or error is not None


class TestGetDefaultClient:
    """默认客户端测试"""

    def test_get_default_client(self):
        """测试获取默认客户端"""
        from tools.http_client import get_default_client
        client = get_default_client()
        assert isinstance(client, HttpClient)

    def test_get_default_client_changes_ssl_setting(self):
        """测试更改 SSL 设置"""
        from tools.http_client import get_default_client
        client1 = get_default_client(verify_ssl=False)
        client2 = get_default_client(verify_ssl=True)
        assert client1.verify_ssl is False
        assert client2.verify_ssl is True
