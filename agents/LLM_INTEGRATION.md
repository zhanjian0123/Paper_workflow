# Agent LLM 集成说明

## 修改概述

所有 6 个 Agent 已修改为实际调用 LLM，使用各自对应的技能 prompt（来自 SKILL.md 文件）。

## 核心修改

### 1. 调试日志增强 (`agents/base.py`)

在 `_call_llm` 方法中添加了调试日志，显示 system prompt 的来源和长度：

```python
async def _call_llm(self, user_message: str, system_prompt: Optional[str] = None, temperature: float = 0.7) -> str:
    if system_prompt:
        # 检查是否是 SKILL.md 格式（包含 # Role）
        is_skill_md = '# Role' in system_prompt or '## ' in system_prompt
        source = "SKILL.md" if is_skill_md else "YAML/其他"
        print(f"[{self.name}] LLM 调用：system_prompt 长度={len(system_prompt)}, 来源={source}...")
    messages = [{"role": "user", "content": user_message}]
    return await self.llm_client.chat(messages=messages, system=system_prompt, temperature=temperature)
```

### 2. User Message 优化

**重要发现**：虽然 skill prompt 被正确传递给 LLM 作为 system prompt，但 user message 中的指令与 SKILL.md 中的指导不一致，可能导致 SKILL.md 的指导没有被充分利用。

**解决方案**：更新所有 Agent 的 user message，使其明确引用 system prompt 中的指导原则，并强调关键要求。

## 各 Agent 修改详情

### 1. BaseAgent (`agents/base.py`)

新增调试日志，显示：
- system prompt 长度
- 来源判断（SKILL.md 或 YAML/其他）
- 开头内容预览

### 2. Coordinator Agent (`agents/coordinator.py`)

- 方法：`_decompose_task_llm()`
- 技能：`task_management`
- SKILL.md 关键指导：
  - 原子化与独立性
  - 契约化输入输出
  - 依赖拓扑构建
  - Agent 精准适配
  - 颗粒度适中、闭环反馈、上下文连续性
- User Message 优化：明确引用"系统提示中的任务编排指导原则"

### 3. Search Agent (`agents/search.py`)

- 方法：查询优化部分
- 技能：`literature_search`
- SKILL.md 关键指导：
  - 意图解构与术语扩展
  - 多路径布尔检索
  - 动态过滤与质量分级
  - 零幻觉红线、透明化溯源
- User Message 优化：强调术语扩展和同义词识别

### 4. Analyst Agent (`agents/analyst.py`)

- 方法：`_extract_key_info()`
- 技能：`critical_analysis` + `innovation_detection`（组合使用）
- SKILL.md 关键指导：
  - 研究问题与动机
  - 核心贡献与创新性
  - 方法论与逻辑严密性
  - 实验验证与结果稳健性
  - 局限性与潜在风险
  - 证据导向、去伪存真、不盲从权威
- User Message 优化：明确五个分析维度和重要原则

### 5. Writer Agent (`agents/writer.py`)

- 方法：`_generate_report_llm()`
- 技能：`academic_writing`
- SKILL.md 关键指导：
  - 多维文献解析
  - 横向对比分析
  - 专题化整合（Thematic Synthesis）
  - 精确引用归属
  - **整合写作标准**：非线性叙述、学术语气、结构化输出
  - 报告输出格式
- User Message 优化：
  - 强调"整合式"写法
  - 禁止"论文 A 说...论文 B 说..."的简单堆砌
  - 按"主题/议题"组织内容

### 6. Reviewer Agent (`agents/reviewer.py`)

- 方法：`_generate_review_llm()`
- 技能：`peer_review`
- SKILL.md 关键指导：
  - 技术正确性与严谨性
  - 实验设计与实证充分性
  - 论证逻辑与结论一致性
  - 表述清晰度与呈现质量
  - 可重复性与伦理
  - 建设性批判、证据导向、高标准严要求
- User Message 优化：明确五个评审维度

### 7. Editor Agent (`agents/editor.py`)

- 方法：`_incorporate_feedback_llm()`
- 技能：`academic_writing`
- User Message：已包含整合反馈的指导

## 温度参数设置

| Agent | Temperature | 说明 |
|-------|-------------|------|
| Coordinator | 0.3 | 任务分解需要一致性 |
| Search | 0.3 | 查询优化需要准确性 |
| Analyst | 0.3 | 信息提取需要精确性 |
| Writer | 0.5 | 写作需要适度创造性 |
| Reviewer | 0.3 | 审核需要客观性 |
| Editor | 0.5 | 编辑需要适度灵活性 |

## 技能 Prompt 加载验证

所有技能 prompt 均正确加载自 SKILL.md 文件：

```
task_management:      1594 字符  ✓ SKILL.md 格式
literature_search:    1516 字符  ✓ SKILL.md 格式
critical_analysis:    1287 字符  ✓ SKILL.md 格式
innovation_detection: 1512 字符  ✓ SKILL.md 格式
academic_writing:     1360 字符  ✓ SKILL.md 格式
peer_review:          1607 字符  ✓ SKILL.md 格式
comparison_analysis:  1206 字符  ✓ SKILL.md 格式
document_processing:  1225 字符  ✓ SKILL.md 格式
```

## 调用链路验证

```
用户请求
  ↓
WorkflowEngine.run()
  ↓
Agent._get_skill_prompt(skill_name)  ← 从 SKILL.md 加载
  ↓
Agent._call_llm(user_message, system_prompt=skill_prompt)
  ↓
LLMClient.chat(messages, system=skill_prompt)
  ↓
DashScope API 调用
```

## 测试建议

1. 端到端测试完整工作流
2. 观察调试日志，确认 system prompt 来源为 "SKILL.md"
3. 检查生成结果是否体现了 SKILL.md 中的指导原则
4. 验证降级模式是否正常工作

## 常见问题

**Q: 为什么感觉 SKILL.md 没有起作用？**

A: 可能原因：
1. API Key 未设置，无法真正调用 LLM
2. User message 的指令与 SKILL.md 指导不一致
3. LLM 没有遵循 system prompt（可能需要调整提示词）

**Q: 如何验证 SKILL.md 被使用了？**

A: 查看控制台日志，应该看到类似：
```
[Writer] LLM 调用：system_prompt 长度=1360, 来源=SKILL.md...
```

**Q: SKILL.md 和 YAML 文件同时存在，使用哪个？**

A: `skill_loader.py` 优先查找 `skill-name/SKILL.md`，如果不存在则回退到 `skill_name.yml`。
