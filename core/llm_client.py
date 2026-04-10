"""
LLM 调用工具 - 统一的大模型调用接口
支持阿里云百炼（DashScope）兼容模式
"""

import os
from typing import Optional, List, Dict, Any

from tools.http_client import HttpClient


class LLMClient:
    """
    LLM 客户端 - 调用大语言模型
    支持阿里云百炼 DashScope API
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: str = "qwen3.5-plus",
        verify_ssl: bool = True,
    ):
        # 支持两种环境变量名：DASHSCOPE_API_KEY 或 ANTHROPIC_API_KEY
        self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
        # 支持两种环境变量名：ANTHROPIC_BASE_URL 或 DASHSCOPE_BASE_URL
        self.base_url = base_url or os.environ.get("ANTHROPIC_BASE_URL") or os.environ.get("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.model_name = model_name
        # SSL 验证控制：从环境变量读取，默认为 True
        # 如果遇到 SSL 证书错误，可设置 DASHSCOPE_VERIFY_SSL=false 或 ANTHROPIC_VERIFY_SSL=false
        verify_ssl_env = os.environ.get("DASHSCOPE_VERIFY_SSL", os.environ.get("ANTHROPIC_VERIFY_SSL", None))
        if verify_ssl_env is not None:
            # 用户明确设置了环境变量，按环境变量来
            self.verify_ssl = verify_ssl_env.lower() == "true"
        else:
            # 默认启用 SSL 验证
            self.verify_ssl = verify_ssl

        # 初始化 HTTP 客户端
        self.http_client = HttpClient(verify_ssl=self.verify_ssl, timeout=120)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """
        发送聊天请求
        messages: 消息列表，每项为 {"role": "user|assistant|system", "content": "..."}
        system: 可选的 system prompt
        """
        # 构建请求体
        payload = {
            "model": self.model_name,
            "messages": self._build_messages(messages, system),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        # 使用共享 HTTP 客户端发送请求
        success, response_text, error = await self.http_client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=120,
        )

        if not success:
            if "SSL" in str(error) or "certificate" in str(error).lower():
                raise Exception(f"SSL 错误：{error}。请设置环境变量 DASHSCOPE_VERIFY_SSL=false 来禁用 SSL 验证")
            raise Exception(f"LLM API error: {error}")

        # 解析响应
        import json
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse LLM response: {e}")

        # 提取回复内容
        if result.get("choices") and len(result["choices"]) > 0:
            return result["choices"][0]["message"]["content"]
        else:
            raise Exception("No response from LLM")

    def _build_messages(
        self, messages: List[Dict[str, str]], system: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """构建消息列表"""
        result = []
        if system:
            result.append({"role": "system", "content": system})
        result.extend(messages)
        return result


def create_llm_client(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model_name: str = "qwen3.5-plus",
) -> LLMClient:
    """创建 LLM 客户端"""
    return LLMClient(api_key=api_key, base_url=base_url, model_name=model_name)
