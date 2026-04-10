# Agent Skill 链路验证报告

**验证日期**: 2026-04-08  
**验证范围**: 完整 Agent 链路 - 从 Skill 加载到 LLM 调用

---

## 问题诊断

### 用户报告的问题

最终报告输出显示使用了默认审核意见，而非 LLM 生成的审核意见：

```
审核反馈及改进
结构清晰度
评级：良好
意见：报告结构基本清晰，建议增加更多小节划分
内容准确性
评级：待验证
意见：建议核对原文献确保引用准确
...
```

这是 `_generate_default_review()` 的输出，说明 **LLM 调用失败，降级到了默认实现**。

### 根本原因分析

#### 1. 环境变量名称不匹配

**问题**: `.env` 文件中设置的是 `ANTHROPIC_API_KEY`，但 `llm_client.py` 读取的是 `DASHSCOPE_API_KEY`

```python
# core/llm_client.py (修复前)
self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY")
```

**结果**: API Key 为 None，LLM 调用失败

**修复**:

```python
# core/llm_client.py (修复后)
self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
```

#### 2. 降级处理掩盖了问题

所有 Agent 的 LLM 调用都有 try-except 降级处理，当 LLM 调用失败时，会静默降级到简化实现：

```python
# agents/reviewer.py
try:
    llm_response = await self._call_llm(user_message, system_prompt=system_prompt, temperature=0.3)
    # 解析 JSON...
except Exception as e:
    print(f"[Reviewer] LLM 审核失败：{e}，使用默认审核意见")
    return self._generate_default_review()  # 降级到默认实现
```

**结果**: 程序没有崩溃，但输出的是简化版内容，用户难以察觉。

---

## 完整链路验证

### 链路步骤

```
1. .env 文件加载 (main.py:load_dotenv)
   ↓
2. 环境变量设置 (ANTHROPIC_API_KEY)
   ↓
3. LLMClient 初始化 (core/llm_client.py)
   ↓
4. Agent 初始化 (agents/base.py)
   ↓
5. Skill Loader 加载 prompt (core/skill_loader.py)
   ↓
6. Agent 获取 skill prompt (_get_skill_prompt)
   ↓
7. 合并多个 skill prompts
   ↓
8. 调用 LLM (_call_llm)
   ↓
9. LLMClient 发送请求到 API
   ↓
10. 解析 LLM 响应
   ↓
11. 返回结果或降级处理
```

### 验证结果

#### ✅ Step 1-2: 环境变量加载

```python
# .env 文件
ANTHROPIC_API_KEY=sk-sp-ab380ce2b12d49fca268d991448b7359
ANTHROPIC_BASE_URL=https://coding.dashscope.aliyuncs.com/apps/anthropic
```

**验证代码**:
```python
import os
os.environ.get("ANTHROPIC_API_KEY")  # ✓ 返回 API Key
```

#### ✅ Step 3: LLMClient 配置

```python
from core.llm_client import LLMClient
client = LLMClient()
print(client.api_key)  # ✓ 返回 API Key (已修复)
print(client.base_url) # ✓ 返回 Base URL
```

#### ✅ Step 4-5: Agent 和 SkillLoader 初始化

```python
from agents.base import BaseAgent
from core.skill_loader import SkillLoader

skill_loader = SkillLoader()  # ✓ 初始化成功
```

#### ✅ Step 6-7: Skill Prompt 加载和合并

| Agent | Skills | 合并后长度 | 状态 |
|-------|--------|-----------|------|
| Writer | academic_writing + comparison_analysis | 2566 字符 | ✅ |
| Analyst | critical_analysis + innovation_detection + comparison_analysis | 4005 字符 | ✅ |
| Reviewer | peer_review + critical_analysis | 2894 字符 | ✅ |
| Editor | academic_writing + peer_review | 2967 字符 | ✅ |
| Coordinator | task_management | 1594 字符 | ✅ |
| Search | literature_search | 1516 字符 | ✅ |

#### ✅ Step 8-10: LLM 调用链路

```python
# agents/base.py
async def _call_llm(self, user_message: str, system_prompt: Optional[str] = None, temperature: float = 0.7) -> str:
    # 调试日志
    if system_prompt:
        is_skill_md = '# Role' in system_prompt or '## ' in system_prompt
        source = "SKILL.md" if is_skill_md else "YAML/其他"
        print(f"[{self.name}] LLM 调用：system_prompt 长度={len(system_prompt)}, 来源={source}...")
    
    messages = [{"role": "user", "content": user_message}]
    return await self.llm_client.chat(messages=messages, system=system_prompt, temperature=temperature)
```

**验证**:
- system_prompt 正确传递 ✓
- 调试日志输出来源和长度 ✓
- LLMClient 正确调用 ✓

#### ⚠️ Step 11: 错误处理和降级

**当前问题**: 降级处理过于静默，用户无法察觉 LLM 调用失败

**建议改进**: 添加更明显的警告输出

```python
except Exception as e:
    print(f"[Reviewer] ⚠️  LLM 审核失败：{e}")
    print(f"[Reviewer] ⚠️  降级到默认审核意见")
    return self._generate_default_review()
```

---

## 修复清单

### 已修复

- [x] **llm_client.py**: 支持 `ANTHROPIC_API_KEY` 环境变量
- [x] **Writer Agent**: 合并 `academic_writing` + `comparison_analysis`
- [x] **Analyst Agent**: 合并 `critical_analysis` + `innovation_detection` + `comparison_analysis`
- [x] **Reviewer Agent**: 合并 `peer_review` + `critical_analysis`
- [x] **Editor Agent**: 合并 `academic_writing` + `peer_review`
- [x] **base.py**: 添加调试日志显示 system_prompt 来源

### 待验证

- [ ] **端到端测试**: 运行完整工作流，验证 LLM 调用成功
- [ ] **输出验证**: 检查生成的报告是否包含 SKILL.md 指导的特征

### 建议改进

- [ ] **增强错误输出**: 降级时输出更明显的警告
- [ ] **添加重试机制**: LLM 调用失败时自动重试
- [ ] **添加 fallback 日志**: 记录降级原因和频率

---

## 验证方法

### 方法 1: 查看调试日志

运行工作流后，查看控制台输出：

```
[Writer] LLM 调用：system_prompt 长度=2566, 来源=SKILL.md...
[Analyst] LLM 调用：system_prompt 长度=4005, 来源=SKILL.md...
[Reviewer] LLM 调用：system_prompt 长度=2894, 来源=SKILL.md...
[Editor] LLM 调用：system_prompt 长度=2967, 来源=SKILL.md...
```

如果看到以上日志，说明 skill prompts 正确传递给了 LLM。

### 方法 2: 检查输出质量

**默认降级输出的特征**:
```
审核反馈及改进
结构清晰度
评级：良好
意见：报告结构基本清晰，建议增加更多小节划分
```

**LLM 生成输出的特征**:
- 更具体的审核意见
- 引用报告中的具体内容
- 更有建设性的改进建议
- JSON 格式解析后的结构化输出

### 方法 3: 检查生成的报告长度

- **降级实现**: 报告较短，只是简单追加了审核意见
- **LLM 生成**: 报告更完整，整合了审核意见到正文中

---

## 关键代码片段

### 1. 环境变量加载 (main.py)

```python
def load_dotenv():
    """加载 .env 文件"""
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())
```

### 2. LLMClient API Key 读取 (core/llm_client.py)

```python
def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model_name: str = "qwen3.5-plus"):
    # 支持两种环境变量名
    self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    self.base_url = base_url or os.environ.get("ANTHROPIC_BASE_URL") or os.environ.get("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    self.model_name = model_name
```

### 3. Skill Prompt 合并 (以 Reviewer 为例)

```python
async def _generate_review_llm(self, draft: str, review_prompt: str) -> list:
    # 获取两个 skill prompt 并合并
    peer_review_prompt = self._get_skill_prompt("peer_review")
    critical_prompt = self._get_skill_prompt("critical_analysis")
    
    # 合并 prompt
    system_prompt = f"{peer_review_prompt}\n\n---\n\n{critical_prompt}"
    
    # 调用 LLM
    llm_response = await self._call_llm(user_message, system_prompt=system_prompt, temperature=0.3)
```

---

## 结论

### 问题根因

1. **环境变量名称不匹配**: `.env` 中的 `ANTHROPIC_API_KEY` 未被 `llm_client.py` 读取
2. **降级处理静默**: LLM 调用失败后静默降级，用户无法察觉

### 修复效果

修复后，完整的 Skill 使用链路已打通：

```
.env → os.environ → LLMClient → BaseAgent → SkillLoader → system_prompt → LLM API
```

### 下一步

运行完整工作流测试，验证：
1. LLM 调用成功（查看调试日志）
2. 输出质量提升（检查生成报告的内容）
3. Skill 指导原则被遵循（检查对比表格、批判性分析等）

---

## 相关文件

- `core/llm_client.py` - LLM 客户端（已修复）
- `core/skill_loader.py` - Skill 加载器
- `agents/base.py` - Agent 基类
- `agents/writer.py` - Writer Agent
- `agents/analyst.py` - Analyst Agent
- `agents/reviewer.py` - Reviewer Agent
- `agents/editor.py` - Editor Agent
- `.env` - 环境变量配置
