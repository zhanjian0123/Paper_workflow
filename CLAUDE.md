# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Multi-Agent 文献工作流系统 - 基于多 Agent 协作的学术论文智能处理系统

## 核心架构

### 6 个 Agent
- **Coordinator**: 工作流协调器，负责任务分解和分配
- **Search**: 文献搜索专家，负责 ArXiv 搜索和下载
- **Analyst**: 文献分析专家，提取关键信息和方法论
- **Writer**: 学术报告撰写专家
- **Reviewer**: 质量审核专家
- **Editor**: 最终编辑，整合反馈生成终稿

### 组件结构
```
projects/
├── core/              # 核心组件
│   ├── message_bus.py   # Agent 间消息总线 (asyncio.Queue)
│   ├── skill_loader.py  # YAML 技能配置加载器
│   ├── llm_client.py    # LLM 调用封装
│   └── config_loader.py # 项目配置加载
├── agents/            # Agent 实现
│   ├── base.py        # BaseAgent 抽象基类
│   ├── coordinator.py # 协调器
│   ├── search.py      # 搜索 Agent
│   ├── analyst.py     # 分析 Agent
│   ├── writer.py      # 写作 Agent
│   ├── reviewer.py    # 审核 Agent
│   └── editor.py      # 编辑 Agent
├── tools/             # 工具实现
│   ├── base.py        # BaseTool 抽象基类
│   ├── arxiv_tool.py  # ArXiv 搜索/下载
│   ├── filesystem_tool.py  # 文件操作
│   ├── pdf_parser_tool.py  # PDF 解析
│   └── web_search_tool.py  # Web 搜索
├── mcp/               # MCP 集成
│   ├── client.py      # MCP 客户端
│   └── tools_registry.py  # 工具注册表
├── memory/            # 记忆系统 (SQLite)
│   ├── task_memory.py   # 任务状态持久化
│   └── agent_memory.py  # Agent 状态和对话历史
├── config/            # YAML 配置
│   ├── agents.yml       # Agent 配置
│   ├── mcp_servers.yml  # MCP 服务器配置
│   └── skills/          # 技能 prompts
├── output/            # 输出目录
│   ├── papers/          # 下载的论文
│   └── reports/         # 生成的报告
└── main.py            # 主程序入口
```

## 常用命令

### 安装依赖
```bash
pip install -r requirements.txt
```

### 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 设置 ANTHROPIC_API_KEY
```

### 运行系统
```bash
# 完整工作流（默认从 ArXiv 搜索，下载 10 篇论文）
python main.py -r "搜索关于 transformer 的最新论文"

# 从 Google Scholar 搜索
python main.py -r "Deep Learning" -s google

# 同时从 ArXiv 和 Google Scholar 搜索
python main.py -r "machine learning" -s both

# 带年份范围搜索
python main.py -r "Deep Learning" -y "2023-2025"

# 指定下载论文数量
python main.py -r "reinforcement learning" -m 5

# 组合使用：年份范围 + 论文数量 + 数据源
python main.py -r "deep learning" -y "2024-2026" -m 20 -s google

# 直接运行特定 Agent
python main.py -a search -r "machine learning"

# 列出所有 Agent
python main.py --list-agents

# 交互模式
python main.py
```

### 参数说明
- `-r, --request`: 用户请求
- `-a, --agent`: 直接运行特定 Agent (coordinator/search/analyst/writer/reviewer/editor)
- `-y, --year-range`: 年份范围，如 `2020-2024` 或 `2023`
- `-m, --max-papers`: 搜索并下载的最大论文数量（默认：10）
- `-s, --source`: 论文数据源 - `arxiv`（仅 ArXiv）, `google`（仅 Google Scholar）, `both`（两者）（默认：arxiv）
- `--api-key`: 覆盖 API Key
- `--base-url`: 覆盖 Base URL
- `--model`: 模型名称 (默认 qwen3.5-plus)

## 数据流

1. 用户请求 → WorkflowEngine
2. Search Agent 执行 ArXiv 搜索（支持年份过滤）
3. 下载指定数量的论文 PDF 到 `output/papers/`（由 `--max-papers/-m` 参数控制，默认 10 篇）
4. Analyst Agent 分析论文内容
5. Writer Agent 生成报告草稿
6. Reviewer Agent 审核质量
7. Editor Agent 生成最终报告
8. 任务状态存入 TaskMemory (SQLite)
9. Agent 状态和对话历史存入 AgentMemory (SQLite)
10. 最终报告保存到 output/reports/

## 技能系统

技能定义在 `config/skills/` 目录的 YAML 文件中：
- `task_management.yml` - 任务分解
- `literature_search.yml` - 文献搜索策略
- `critical_analysis.yml` - 关键信息提取
- `innovation_detection.yml` - 创新点检测
- `academic_writing.yml` - 学术写作规范
- `comparison_analysis.yml` - 对比分析
- `peer_review.yml` - 质量审核
- `document_processing.yml` - 文档处理

**重要：** 技能文件中包含保守原则提示词，要求 Agent 不编造数据，如实报告搜索结果。

## Tool 系统

内置工具通过 `ToolsRegistry` 管理：
- `arxiv` - ArXiv API 搜索和下载
- `filesystem` - 文件读写
- `pdf_parser` - PDF 文本提取
- `web_search` - Web 搜索

## 关键实现细节

### ArXiv API 年份过滤格式

`tools/arxiv_tool.py` 中的年份过滤必须使用正确的格式：
```python
# 正确格式：TO 前后有空格，14 位 datetime 格式
year_filter = f"+AND+submittedDate:[{start_year}0101000000 TO {end_year}1231235959]"

# 错误格式：缺少空格会导致 API 返回错误
# year_filter = f"+AND+submittedDate:[{start_year}0101TO{end_year}1231]"
```

### 输出控制

`main.py` 已优化控制台输出：
- 不打印完整 JSON（数据保存到文件）
- 只显示摘要信息：状态、论文数量、论文列表（前 5 篇）、报告预览（1000 字符）

## 开发注意事项

1. 新增 Agent 需继承 `agents/base.py:BaseAgent`
2. 新增工具需继承 `tools/base.py:BaseTool` 并在 `ToolsRegistry` 注册
3. Agent 通信统一使用 `MessageBus`
4. 状态持久化使用 `TaskMemory` 和 `AgentMemory`
5. 技能 prompts 放在 `config/skills/` 目录
6. 参考 `debug.md` 了解已修复的 Bug 和改动历史
