"""
HTTP 客户端工具 - 统一的 aiohttp 客户端封装
提供 SSL 配置、重试机制等功能
"""

import ssl
import asyncio
import random
from typing import Optional, Dict, Any
import aiohttp
from aiohttp import ClientSession, TCPConnector, ClientTimeout, ClientError


class SSLConfig:
    """SSL 配置"""

    @staticmethod
    def create_disabled_context() -> ssl.SSLContext:
        """创建禁用 SSL 验证的上下文（用于绕过证书验证问题）"""
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context

    @staticmethod
    def create_connector(verify_ssl: bool = False) -> TCPConnector:
        """创建 TCP 连接器"""
        if verify_ssl:
            return TCPConnector()
        else:
            ssl_context = SSLConfig.create_disabled_context()
            return TCPConnector(ssl=ssl_context)


class RetryConfig:
    """重试配置"""

    def __init__(
        self,
        max_retries: int = 5,
        base_delay: float = 5.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def calculate_delay(self, attempt: int) -> float:
        """计算延迟时间（指数退避 + 随机抖动）"""
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)
        if self.jitter:
            delay += random.uniform(0, 2)
        return delay


class HttpClient:
    """
    统一的 HTTP 客户端
    提供 SSL 配置、重试机制、超时处理等功能
    """

    def __init__(
        self,
        verify_ssl: bool = False,
        timeout: float = 30.0,
        retry_config: Optional[RetryConfig] = None,
    ):
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.retry_config = retry_config or RetryConfig()
        self._session: Optional[ClientSession] = None

    def _get_connector(self) -> TCPConnector:
        """获取 TCP 连接器"""
        return SSLConfig.create_connector(self.verify_ssl)

    def _get_timeout(self) -> ClientTimeout:
        """获取超时配置"""
        return ClientTimeout(total=self.timeout)

    async def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        retry_on_status: Optional[list] = None,
    ) -> tuple[bool, Optional[str], Optional[dict]]:
        """
        发送 GET 请求

        Args:
            url: 请求 URL
            headers: 请求头
            params: 查询参数
            timeout: 超时时间（秒）
            retry_on_status: 需要重试的状态码列表（如 [429, 503]）

        Returns:
            (success, response_text, error_message)
        """
        retry_on_status = retry_on_status or []
        actual_timeout = timeout or self.timeout

        for attempt in range(self.retry_config.max_retries):
            try:
                connector = self._get_connector()
                async with ClientSession(connector=connector, timeout=self._get_timeout()) as session:
                    async with session.get(url, headers=headers, params=params) as response:
                        response_text = await response.text()

                        if response.status == 200:
                            return True, response_text, None

                        if response.status in retry_on_status:
                            delay = self.retry_config.calculate_delay(attempt)
                            print(f"[HTTP] 触发重试 (状态码：{response.status})，等待 {delay:.1f} 秒后重试... (尝试 {attempt + 1}/{self.retry_config.max_retries})")
                            await asyncio.sleep(delay)
                            continue

                        return False, response_text, f"HTTP error: {response.status}"

            except ClientError as e:
                if attempt < self.retry_config.max_retries - 1:
                    delay = self.retry_config.calculate_delay(attempt)
                    print(f"[HTTP] 请求失败 ({str(e)})，等待 {delay} 秒后重试...")
                    await asyncio.sleep(delay)
                else:
                    return False, None, f"网络错误：{str(e)}"

        return False, None, "请求失败：超过最大重试次数"

    async def post(
        self,
        url: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> tuple[bool, Optional[str], Optional[dict]]:
        """
        发送 POST 请求

        Args:
            url: 请求 URL
            json: JSON 请求体
            headers: 请求头
            timeout: 超时时间（秒）

        Returns:
            (success, response_text, error_message)
        """
        actual_timeout = timeout or self.timeout

        try:
            connector = self._get_connector()
            async with ClientSession(connector=connector, timeout=self._get_timeout()) as session:
                async with session.post(url, json=json, headers=headers) as response:
                    response_text = await response.text()

                    if response.status == 200:
                        return True, response_text, None

                    return False, response_text, f"HTTP error: {response.status}"

        except ClientError as e:
            return False, None, f"网络错误：{str(e)}"

    async def download_file(
        self,
        url: str,
        save_path: str,
        timeout: float = 60.0,
        retry_on_status: Optional[list] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        下载文件

        Args:
            url: 文件 URL
            save_path: 保存路径
            timeout: 超时时间（秒）
            retry_on_status: 需要重试的状态码列表

        Returns:
            (success, error_message)
        """
        import aiofiles

        retry_on_status = retry_on_status or []

        for attempt in range(self.retry_config.max_retries):
            try:
                connector = self._get_connector()
                async with ClientSession(connector=connector, timeout=ClientTimeout(total=timeout)) as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            async with aiofiles.open(save_path, "wb") as f:
                                await f.write(await response.read())
                            return True, None

                        if response.status in retry_on_status:
                            delay = self.retry_config.calculate_delay(attempt)
                            print(f"[HTTP] 下载触发重试 (状态码：{response.status})，等待 {delay:.1f} 秒后重试...")
                            await asyncio.sleep(delay)
                            continue

                        return False, f"HTTP error: {response.status}"

            except ClientError as e:
                if attempt < self.retry_config.max_retries - 1:
                    delay = self.retry_config.calculate_delay(attempt)
                    print(f"[HTTP] 下载失败 ({str(e)})，等待 {delay} 秒后重试...")
                    await asyncio.sleep(delay)
                else:
                    return False, f"网络错误：{str(e)}"

        return False, "下载失败：超过最大重试次数"


# 全局默认客户端实例
_default_client: Optional[HttpClient] = None


def get_default_client(verify_ssl: bool = False) -> HttpClient:
    """获取默认 HTTP 客户端"""
    global _default_client
    if _default_client is None or _default_client.verify_ssl != verify_ssl:
        _default_client = HttpClient(verify_ssl=verify_ssl)
    return _default_client
