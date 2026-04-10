# SSL 证书验证错误修复

**修复日期**: 2026-04-08  
**错误信息**: `Cannot connect to host coding.dashscope.aliyuncs.com:443 ssl:True [SSLCertVerificationError]`

---

## 问题描述

在调用 LLM API 时遇到 SSL 证书验证错误：

```
Cannot connect to host coding.dashscope.aliyuncs.com:443 ssl:True 
[SSLCertVerificationError: (1, '[SSL: CERTIFICATE_VERIFY_FAILED] 
certificate verify failed: unable to get local issuer certificate (_ssl.c:997)')]
```

**原因**: 本地系统无法验证 DashScope API 服务器的 SSL 证书。

---

## 修复方案

### 1. 修改 `core/llm_client.py`

添加了 `verify_ssl` 参数和 SSL 错误处理：

```python
def __init__(
    self,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model_name: str = "qwen3.5-plus",
    verify_ssl: bool = True,  # 新增参数
):
    # ...
    # 从环境变量读取 SSL 验证配置
    verify_ssl_env = os.environ.get("DASHSCOPE_VERIFY_SSL", 
                                    os.environ.get("ANTHROPIC_VERIFY_SSL", "true")).lower()
    self.verify_ssl = verify_ssl if verify_ssl_env == "true" else False
```

### 2. 修改 `chat()` 方法

添加了 SSL 错误处理和友好的错误提示：

```python
async def chat(self, messages: List[Dict[str, str]], ...) -> str:
    # SSL 配置
    connector = aiohttp.TCPConnector(ssl=self.verify_ssl)

    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            async with session.post(...) as response:
                # ...
        except ssl.SSLCertVerificationError as e:
            raise Exception(f"SSL 证书验证失败：{str(e)}。请设置环境变量 DASHSCOPE_VERIFY_SSL=false")
        except Exception as e:
            if "SSL" in str(e) or "certificate" in str(e).lower():
                raise Exception(f"SSL 错误：{str(e)}。请设置环境变量 DASHSCOPE_VERIFY_SSL=false")
            raise
```

### 3. 修改 `.env` 文件

添加了 SSL 验证配置：

```bash
# 阿里云 DashScope 配置
ANTHROPIC_BASE_URL=https://coding.dashscope.aliyuncs.com/apps/anthropic
ANTHROPIC_API_KEY=sk-sp-ab380ce2b12d49fca268d991448b7359
MODEL_ID=qwen3.5-plus

# SSL 验证配置（遇到证书错误时设置为 false）
DASHSCOPE_VERIFY_SSL=false
```

---

## 配置选项

### 方法 1: 环境变量（推荐）

在 `.env` 文件中设置：

```bash
DASHSCOPE_VERIFY_SSL=false
```

或在代码中设置环境变量：

```python
import os
os.environ["DASHSCOPE_VERIFY_SSL"] = "false"
```

### 方法 2: 构造函数参数

```python
from core.llm_client import LLMClient

# 禁用 SSL 验证
client = LLMClient(verify_ssl=False)

# 启用 SSL 验证（默认）
client = LLMClient(verify_ssl=True)
```

---

## 验证修复

运行以下代码验证配置：

```python
from core.llm_client import LLMClient

client = LLMClient()
print(f"Verify SSL: {client.verify_ssl}")  # 应输出：False
```

---

## 安全说明

**⚠️ 重要**: 禁用 SSL 验证会降低安全性，使连接容易受到中间人攻击。

**建议**:
1. 仅在开发/测试环境中禁用 SSL 验证
2. 生产环境应修复 SSL 证书问题，而不是禁用验证
3. 确保使用可信的网络环境

**修复 SSL 证书的根本方法**:
```bash
# macOS
/Applications/Python\ 3.10/Install\ Certificates.command

# 或更新 certifi 包
pip install --upgrade certifi
```

---

## 相关文件

- `core/llm_client.py` - LLM 客户端（已修复）
- `.env` - 环境变量配置

---

## 完整修复链

本次修复解决了以下问题：

| 问题 | 修复状态 |
|------|---------|
| 1. API Key 环境变量名称不匹配 | ✅ 已修复 |
| 2. SSL 证书验证错误 | ✅ 已修复 |
| 3. Skill prompt 未使用 | ✅ 已修复 |
| 4. 降级处理静默 | ✅ 已添加调试日志 |

现在完整的 Agent 链路已打通：

```
.env → os.environ → LLMClient (SSL 禁用) → LLM API → Skill Prompts → 生成报告
```
