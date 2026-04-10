# 长期记忆系统使用指南

## 概述

长期记忆系统用于保存"未来对协作仍然有价值、且无法稳定从当前代码库或仓库状态推导出来的信息"。

## 记忆类型

系统支持 4 类长期记忆：

### 1. user - 用户记忆

关于当前用户的角色、经验、偏好、职责、协作风格的信息。

**示例：**
- "用户是数据科学家，擅长 Python 但不熟悉前端开发"
- "用户偏好简洁的代码风格，不喜欢过度抽象"
- "用户正在调查日志系统，需要详细的错误追踪"

### 2. feedback - 反馈记忆

用户明确给出的协作反馈，包括纠正、禁忌、偏好的做法、被验证有效的非显然工作方式。

**示例：**
- "不要 Mock 数据库测试 - 之前发生过 Mock 测试通过但生产迁移失败的问题"
- "用户希望代码改动最小化，不要过度重构"
- "用户偏好单文件解决方案而不是分散的模块"

### 3. project - 项目记忆

无法从当前代码直接推导出的项目上下文，例如业务背景、约束、截止时间、组织协作方式、决策原因、事故背景。

**示例：**
- "法律合规要求：身份中间件重写是因为法律要求新的会话令牌存储方式"
- "3 月 15 日开始合并冻结 - 移动端团队要切割 release 分支"
- "这个模块的复杂历史原因：2023 年数据迁移事故后添加的防御性检查"

### 4. reference - 参考记忆

外部信息源的定位信息，例如文档地址、仪表盘、Slack 频道、工单系统、Linear 项目、内部平台入口。

**示例：**
- "Pipeline Bug 追踪：Linear 项目 'INGEST'"
- "Oncall 延迟仪表盘：grafana.internal/d/api-latency"
- "团队反馈渠道：#claude-feedback Slack 频道"

## 禁止保存的内容

以下内容**不应**进入长期记忆：

- ❌ 代码结构、架构、模块关系、文件路径、项目目录结构
- ❌ 可通过 `grep` / `read` / `code search` 得到的信息
- ❌ Git 历史、commit 信息、谁改了什么
- ❌ Bug 修复步骤本身
- ❌ 当前任务状态、计划、todo、执行状态
- ❌ PR 列表、活动日志、流水账
- ❌ 已写在 CLAUDE.md、AGENTS.md 等文件中的内容
- ❌ 敏感信息（token、密钥、密码、凭证、个人隐私）

## 使用方法

### 命令行操作

```bash
# 查看所有记忆
python main.py --memory list

# 保存用户记忆
python main.py --memory save \
  --memory-type user \
  --memory-name "用户角色" \
  --memory-content "用户是数据科学家，正在调查日志系统"

# 保存反馈记忆
python main.py --memory save \
  --memory-type feedback \
  --memory-name "测试策略" \
  --memory-content "集成测试必须使用真实数据库，不要 Mock"

# 保存项目记忆（带过期时间）
python main.py --memory save \
  --memory-type project \
  --memory-name "合并冻结" \
  --memory-content "3 月 15 日开始合并冻结，移动端 release 分支切割"

# 保存参考记忆
python main.py --memory save \
  --memory-type reference \
  --memory-name "Pipeline Bug 追踪" \
  --memory-content "Linear 项目 INGEST 追踪所有 Pipeline 相关 Bug"

# 删除记忆
python main.py --memory delete --memory-id <记忆 ID>

# 清理过期/过时记忆
python main.py --memory cleanup
```

### Python API

```python
from memory.long_term_memory import LongTermMemory, should_remember

# 初始化
memory = LongTermMemory()

# 判断是否值得保存
if should_remember("用户偏好简洁代码"):
    entry = memory.save(
        memory_type="user",
        name="代码风格偏好",
        description="用户偏好简洁直接的代码，不喜欢过度抽象和提前优化",
        tags=["coding-style", "preference"],
    )

# 获取记忆
all_memories = memory.get()
user_memories = memory.get(memory_type="user")
search_results = memory.get(query="数据库")

# 更新记忆
memory.update(
    entry_id="abc123",
    description="更新后的描述",
)

# 删除记忆
memory.delete("abc123")

# 清理
stats = memory.cleanup()
print(f"清理了 {stats['expired']} 条过期记忆，{stats['stale']} 条过时记忆")
```

## 记忆格式

每条记忆保存在独立的 Markdown 文件中，格式如下：

```markdown
---
name: 记忆名称
description: 简短描述（200 字符内）
type: user|feedback|project|reference
id: 唯一标识符
created_at: 2024-01-01T00:00:00
updated_at: 2024-01-01T00:00:00
expires_at: 2024-12-31T00:00:00  # 可选
source: 来源上下文  # 可选
tags: tag1, tag2  # 可选
---

记忆正文内容...
```

## 索引文件

`MEMORY.md` 是记忆索引，格式如下：

```markdown
# Memory Index

自动生成的长期记忆索引。最后更新：2024-01-01T00:00:00
共 42 条记录。

---

- [user: 用户角色](entries/user_用户角色_abc123.md) — 用户是数据科学家...
- [feedback: 测试策略](entries/user_测试策略_def456.md) — 集成测试必须使用真实数据库...
- [project: 合并冻结](entries/project_合并冻结_ghi789.md) — 3 月 15 日开始...
- [reference: Pipeline Bug 追踪](entries/reference_Pipeline_jkl012.md) — Linear 项目 INGEST...
```

## 记忆召回策略

系统采用"索引常驻 + 相关记忆按需召回"策略：

1. **默认只暴露索引** - 不将所有记忆正文一次性加载
2. **按需召回** - 当用户问题与某些记忆相关时，才加载少量最相关的记忆
3. **保守召回** - 不确定就不召回，避免噪音
4. **过期过滤** - 自动排除过期记忆
5. **过时标记** - 超过 180 天未更新的记忆标记为"过时"

## 记忆 freshness 机制

- **过期检查**：设置了 `expires_at` 的记忆会在过期后自动被清理
- **过时检查**：超过 180 天未更新的记忆标记为 stale
- **定期清理**：运行 `python main.py --memory cleanup` 清理过期和过时记忆

## 安全边界

系统内置以下安全保护：

1. **敏感信息检测** - 自动拒绝包含 API Key、Token、Password 等关键词的内容
2. **代码结构过滤** - 拒绝纯代码结构信息（可从代码推导）
3. **临时状态过滤** - 拒绝 Todo、In Progress 等临时状态信息
4. **路径穿越防护** - 校验记忆文件路径，防止逃逸

## 最佳实践

### ✅ 推荐

- 保存用户明确表达的偏好和反馈
- 保存无法从代码推导的业务背景和约束
- 保存外部系统的定位信息
- 为临时性项目记忆设置过期时间
- 定期清理过时记忆

### ❌ 避免

- 不要保存代码细节（文件路径、函数名等）
- 不要保存当前任务状态
- 不要保存 PR 列表或活动日志
- 不要保存可通过 inspect 得到的信息
- 不要保存敏感信息

## 记忆不是事实来源

**重要：** 记忆中提到的函数、文件、flag、代码行为、配置项、路径等信息都是"写入当时的观察"。

在给用户建议之前：
1. 如果记忆涉及当前代码状态，必须重新验证
2. 如果记忆与当前代码不一致，应信任当前代码
3. 发现记忆已过时，应更新或删除旧记忆

## 文件结构

```
memory/
├── long_term_memory.py    # 长期记忆系统实现
└── __init__.py            # 模块导出

.claude/
└── memory/
    ├── MEMORY.md          # 记忆索引
    └── entries/           # 记忆正文目录
        ├── user_*.md
        ├── feedback_*.md
        ├── project_*.md
        └── reference_*.md
```
