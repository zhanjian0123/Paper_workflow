# Phase 0: 现状梳理与技术定稿

**日期**: 2026-04-07
**状态**: 技术定稿

---

## 1. 当前调用链

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLI Entry Point                                │
│                                 main.py                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MultiAgentSystem                                    │
│  - 初始化系统组件 (MessageBus, TaskMemory, AgentMemory, ToolsRegistry)      │
│  - 创建 6 个 Agent 实例                                                       │
│  - 调用 WorkflowEngine.run()                                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           WorkflowEngine                                    │
│  core/workflow_engine.py                                                    │
│  - run(user_request, year_range) → Dict                                     │
│  - 顺序执行 5 个阶段：Search → Analyst → Writer → Reviewer → Editor          │
│  - 每个阶段调用对应 Agent 的 run_once()                                       │
│  - 返回统一结构：{status, task_id, papers, analysis, draft, review,         │
│                  final_report}                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Agents (6 个)                                   │
│  agents/base.py → BaseAgent (抽象基类)                                      │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ Search Agent    │ agents/search.py    │ 文献搜索 (ArXiv/Google)      │   │
│  │ Analyst Agent   │ agents/analyst.py   │ 论文分析提取                  │   │
│  │ Writer Agent    │ agents/writer.py    │ 报告撰写                     │   │
│  │ Reviewer Agent  │ agents/reviewer.py  │ 质量审核                     │   │
│  │ Editor Agent    │ agents/editor.py    │ 最终编辑                     │   │
│  │ Coordinator     │ agents/coordinator.py│ 任务协调 (未完全使用)        │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│  共同特征：                                                                  │
│  - 继承 BaseAgent，实现 process_message() 和 execute_task()                   │
│  - 通过 ToolsRegistry 调用工具                                                │
│  - 通过 TaskMemory 保存任务状态                                              │
│  - 通过 AgentMemory 保存 Agent 状态和对话历史                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Tools (via ToolsRegistry)                        │
│  mcp/tools_registry.py → execute_tool(name, action, **kwargs)               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ arxiv          │ tools/arxiv_tool.py         │ ArXiv API 搜索/下载    │   │
│  │ google_scholar │ tools/google_scholar_tool.py│ Google Scholar 搜索    │   │
│  │ pdf_parser     │ tools/pdf_parser_tool.py    │ PDF 文本解析            │   │
│  │ filesystem     │ tools/filesystem_tool.py    │ 文件读写               │   │
│  │ web_search     │ tools/web_search_tool.py    │ Web 搜索               │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Memory Systems                                     │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ TaskMemory      │ memory/task_memory.py   │ SQLite, 任务状态追踪     │   │
│  │ AgentMemory     │ memory/agent_memory.py  │ SQLite, Agent 状态 + 历史  │   │
│  │ LongTermMemory  │ memory/long_term_memory.py│ Markdown 文件，长期记忆 │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 现有输入输出格式

### 2.1 请求参数 (WorkflowEngine.run)

```python
{
    "user_request": str,        # 用户研究主题，例如："搜索关于 transformer 的最新论文"
    "year_range": Optional[str], # 年份范围："2024-2026" 或 "2025"
    "max_papers": int,           # 最大论文数量：10 (默认)
    "source": str,               # 数据源："arxiv" | "google" | "both" (默认："arxiv")
    "download_dir": str,         # PDF 下载目录："output/papers" (默认)
}
```

### 2.2 论文结构 (Paper)

```python
{
    # ArXiv 数据源
    "id": str,                   # ArXiv URL
    "title": str,                # 论文标题
    "authors": List[str],        # 作者列表
    "summary": str,              # 摘要
    "published": str,            # 发表日期 (ISO 8601)
    "categories": List[str],     # ArXiv 分类
    "arxiv_id": str,             # ArXiv ID (e.g., "2401.00001")
    "doi": str,                  # DOI
    "url": str,                  # 链接
    "pdf_path": str,             # 本地 PDF 路径
    
    # Google Scholar 数据源特有
    "published_year": str,       # 发表年份
    "venue": str,                # 期刊/会议
    "citations": int,            # 引用数
    "source": str,               # "arxiv" | "google_scholar"
    
    # 分析后添加的字段
    "research_question": str,    # 研究问题
    "methodology": str,          # 方法论
    "key_contributions": List[str],  # 核心贡献
    "innovations": List[str],        # 创新点
    "limitations": List[str],        # 局限性
}
```

### 2.3 分析结构 (Analysis)

```python
{
    # 保留所有原始论文字段 (见 2.2)
    ...
    # 分析字段
    "research_question": str,    # 研究问题
    "methodology": str,          # 方法论
    "key_contributions": List[str],  # 核心贡献
    "innovations": List[str],        # 创新点
    "limitations": List[str],        # 局限性
}
```

### 2.4 报告结构 (Report)

```python
{
    "draft": str,               # 草稿 Markdown
    "review": List[Dict],       # 审核意见
    "final_report": str,        # 最终 Markdown 报告
}
```

**Markdown 报告格式**:
```markdown
# 文献分析报告

## 概述
本报告基于对所选文献的系统分析生成。
- **分析文献数量**: N 篇

---

## 文献详细列表

### 文献 1: 标题

**基本信息**
- **作者**: ...
- **发表日期**: ...
- **ArXiv ID**: ... / **期刊/会议**: ...
- **DOI**: ...
- **引用数**: ... (Google Scholar 特有)
- **链接**: ...
- **分类**: ... (ArXiv 特有)

**摘要**
...

**研究问题**
...

**方法论**
...

**核心贡献**
- ...

---

## 总结
...
```

### 2.5 错误结构

```python
# ToolResult (tools/base.py)
{
    "success": bool,
    "data": Any,
    "error": Optional[str],
    "metadata": Dict[str, Any],
}

# 工作流错误返回
{
    "status": "failed",
    "task_id": str,
    "error": str,
}
```

---

## 3. 产物落盘规则

### 3.1 当前落盘位置

```
output/
├── task_memory.db              # SQLite: 任务状态
├── agent_memory.db             # SQLite: Agent 状态 + 对话历史
├── papers/                     # 下载的论文 PDF
│   └── *.pdf                   # 以 ArXiv ID 命名
└── reports/                    # 生成的报告和结果
    ├── result_YYYYMMDD_HHMMSS.json  # 完整 JSON 结果
    └── report_YYYYMMDD_HHMMSS.md    # Markdown 报告
```

### 3.2 JSON 结果结构 (result_*.json)

```json
{
  "status": "completed",
  "task_id": "uuid",
  "papers": [...],
  "analysis": [...],
  "draft": "...",
  "review": [...],
  "final_report": "..."
}
```

### 3.3 问题

- 输出目录结构不统一，reports/ 和 papers/ 分散
- 没有工作流级别的目录组织
- 报告/论文与 Workflow ID 没有明确映射
- 重启服务后无法通过 ID 反查历史工作流

---

## 4. 技术栈定稿

### 4.1 后端技术栈

| 组件 | 技术选型 | 版本 | 用途 |
|------|----------|------|------|
| Web 框架 | **FastAPI** | 0.109+ | REST API + WebSocket |
| ASGI Server | **Uvicorn** | 0.27+ | 应用服务器 |
| 数据验证 | **Pydantic** | 2.x | Schema 定义 + 验证 |
| 任务队列 | **asyncio** | builtin | 后台任务管理 |
| 持久化 | **SQLite** + **aiosqlite** | 3.x | 工作流状态存储 |
| 文件服务 | **aiofiles** | 23.x | 异步文件 IO |
| CORS | **fastapi.middleware** | builtin | 跨域支持 |
| 事件总线 | 自定义实现 | - | WebSocket 推送 |

### 4.2 前端技术栈

| 组件 | 技术选型 | 版本 | 用途 |
|------|----------|------|------|
| 框架 | **Vue 3** | 3.4+ | Composition API |
| 构建工具 | **Vite** | 5.x | 快速开发服务器 |
| UI 库 | **Element Plus** | 2.x | 组件库 |
| 状态管理 | **Pinia** | 2.x | 状态管理 |
| HTTP 客户端 | **Axios** | 1.x | API 请求 |
| WebSocket | **@vueuse/core** | 10.x | WebSocket 组合式 API |
| Markdown 渲染 | **markdown-it** | 13.x | Markdown 解析 |
| 路由 | **Vue Router** | 4.x | 前端路由 |
| CSS 框架 | **Tailwind CSS** (可选) | 3.x | 原子化 CSS |

### 4.3 目录改造方案

```
projects/
├── backend/                      # 后端代码 (新增)
│   ├── app/
│   │   ├── main.py               # FastAPI 应用入口
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── workflows.py  # 工作流 API
│   │   │   │   ├── papers.py     # 论文 API
│   │   │   │   ├── reports.py    # 报告 API
│   │   │   │   └── memory.py     # 记忆 API
│   │   │   └── websocket.py      # WebSocket 管理器
│   │   ├── schemas/
│   │   │   ├── workflow.py       # Pydantic 模型
│   │   │   ├── paper.py
│   │   │   ├── report.py
│   │   │   └── memory.py
│   │   ├── services/
│   │   │   ├── workflow_runner.py    # 工作流运行器
│   │   │   ├── workflow_store.py     # 工作流存储
│   │   │   ├── paper_service.py      # 论文服务
│   │   │   ├── report_service.py     # 报告服务
│   │   │   └── memory_service.py     # 记忆服务
│   │   ├── core/
│   │   │   ├── deps.py           # 依赖注入
│   │   │   ├── config.py         # 配置
│   │   │   └── events.py         # 事件总线
│   │   └── adapters/
│   │       └── multi_agent_adapter.py  # 适配现有代码
│   ├── requirements.txt
│   └── README.md
├── frontend/                     # 前端代码 (新增)
│   ├── src/
│   │   ├── api/                  # API 封装
│   │   ├── stores/               # Pinia 状态
│   │   ├── router/               # 路由配置
│   │   ├── views/                # 页面
│   │   ├── components/           # 组件
│   │   ├── composables/          # 组合式函数
│   │   ├── utils/
│   │   ├── styles/
│   │   └── App.vue
│   ├── package.json
│   ├── vite.config.js
│   └── README.md
├── core/                         # 现有核心组件 (保留)
├── agents/                       # 现有 Agent (保留)
├── tools/                        # 现有工具 (保留)
├── memory/                       # 现有记忆系统 (保留)
├── mcp/                          # 现有 MCP (保留)
├── config/                       # 现有配置 (保留)
├── output/                       # 输出目录 (重构)
│   ├── workflows/                # 工作流输出 (新增)
│   │   └── {workflow_id}/
│   │       ├── result.json
│   │       ├── report.md
│   │       └── papers/
│   │           └── *.pdf
│   ├── workflow_store.db         # 工作流状态 DB (新增)
│   ├── task_memory.db            # 现有 (保留)
│   └── agent_memory.db           # 现有 (保留)
└── main.py                       # 现有 CLI (保留)
```

---

## 5. 接口契约草案 (Pydantic Schemas)

### 5.1 工作流模型 (schemas/workflow.py)

```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class WorkflowStage(str, Enum):
    SEARCH = "search"
    ANALYST = "analyst"
    WRITER = "writer"
    REVIEWER = "reviewer"
    EDITOR = "editor"

class WorkflowCreateRequest(BaseModel):
    """创建工作流请求"""
    query: str = Field(..., description="研究主题", min_length=1)
    year_range: Optional[str] = Field(None, description="年份范围，如 2024-2026")
    max_papers: int = Field(default=10, ge=1, le=100, description="最大论文数量")
    source: str = Field(default="arxiv", pattern="^(arxiv|google|both)$")

class WorkflowStageStatus(BaseModel):
    """阶段状态"""
    stage: WorkflowStage
    status: str  # pending/in_progress/completed/failed
    progress: int = Field(0, ge=0, le=100)
    message: str
    papers_found: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class WorkflowSummary(BaseModel):
    """工作流摘要 (列表项)"""
    id: str
    query: str
    status: WorkflowStatus
    current_stage: Optional[WorkflowStage]
    progress: int  # 总体进度 0-100
    papers_found: int
    created_at: datetime
    completed_at: Optional[datetime]

class WorkflowDetail(BaseModel):
    """工作流详情"""
    id: str
    query: str
    year_range: Optional[str]
    max_papers: int
    source: str
    status: WorkflowStatus
    current_stage: Optional[WorkflowStage]
    stages: List[WorkflowStageStatus]
    progress: int
    message: str
    papers_found: int
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]

class WorkflowEvent(BaseModel):
    """工作流事件 (WebSocket 推送)"""
    workflow_id: str
    event_type: str  # stage_started/stage_progress/stage_completed/workflow_completed/workflow_failed
    stage: Optional[WorkflowStage]
    status: Optional[str]
    progress: int
    message: str
    data: Optional[Dict[str, Any]]
    timestamp: datetime

class WorkflowCancelResponse(BaseModel):
    """取消工作流响应"""
    workflow_id: str
    status: str  # cancelled/already_completed/not_found
    message: str
```

### 5.2 论文模型 (schemas/paper.py)

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class PaperSummary(BaseModel):
    """论文摘要 (列表项)"""
    id: str
    paper_id: str  # ArXiv ID 或内部 ID
    title: str
    authors: List[str]
    year: Optional[str]
    source: str
    pdf_available: bool
    workflow_id: str

class PaperDetail(BaseModel):
    """论文详情"""
    paper_id: str
    workflow_id: str
    title: str
    authors: List[str]
    abstract: str
    year: Optional[str]
    source: str
    categories: Optional[List[str]]
    venue: Optional[str]
    citations: Optional[int]
    doi: Optional[str]
    url: str
    pdf_path: Optional[str]
    download_status: str  # pending/downloaded/failed
    created_at: datetime

class PaperListResponse(BaseModel):
    """论文列表响应"""
    items: List[PaperSummary]
    total: int
    page: int
    page_size: int
    has_more: bool
```

### 5.3 报告模型 (schemas/report.py)

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class ReportSummary(BaseModel):
    """报告摘要 (列表项)"""
    report_id: str
    workflow_id: str
    title: str  # 取报告第一行
    word_count: int
    created_at: datetime

class ReportDetail(BaseModel):
    """报告详情"""
    report_id: str
    workflow_id: str
    content_markdown: str
    file_path: Optional[str]
    word_count: int
    created_at: datetime

class ReportDownloadResponse(BaseModel):
    """报告下载响应"""
    report_id: str
    file_path: str
    content_type: str  # text/markdown | application/pdf
```

### 5.4 记忆模型 (schemas/memory.py)

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class MemoryType(str, Enum):
    USER = "user"
    FEEDBACK = "feedback"
    PROJECT = "project"
    REFERENCE = "reference"

class MemoryEntrySchema(BaseModel):
    """记忆条目"""
    id: str
    memory_type: MemoryType
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime]
    is_stale: bool
    is_expired: bool

class MemoryCreateRequest(BaseModel):
    """创建记忆请求"""
    memory_type: MemoryType
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=50)
    tags: Optional[List[str]] = None

class MemoryListResponse(BaseModel):
    """记忆列表响应"""
    items: List[MemoryEntrySchema]
    total: int
    by_type: dict[str, int]
```

---

## 6. 工作流状态模型草案

### 6.1 状态机

```
┌─────────────┐
│   PENDING   │  ← 刚创建，等待启动
└──────┬──────┘
       │ start()
       ▼
┌─────────────┐
│   RUNNING   │  ← 正在执行
└──────┬──────┘
       │
       ├──────────────┬──────────────┬──────────────┐
       │              │              │              │
       ▼              ▼              ▼              ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  COMPLETED  │ │   FAILED    │ │  CANCELLED  │ │   TIMEOUT   │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

### 6.2 阶段进度

```python
STAGE_PROGRESS_WEIGHTS = {
    "search": 25,      # 搜索占 25%
    "analyst": 25,     # 分析占 25%
    "writer": 25,      # 写作占 25%
    "reviewer": 15,    # 审核占 15%
    "editor": 10,      # 编辑占 10%
}
```

### 6.3 数据库表结构 (SQLite)

```sql
-- 工作流表
CREATE TABLE workflows (
    id TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    year_range TEXT,
    max_papers INTEGER DEFAULT 10,
    source TEXT DEFAULT 'arxiv',
    status TEXT NOT NULL,  -- pending/running/completed/failed/cancelled
    current_stage TEXT,
    progress INTEGER DEFAULT 0,
    message TEXT,
    papers_found INTEGER DEFAULT 0,
    result TEXT,           -- JSON
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- 工作流事件表
CREATE TABLE workflow_events (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    stage TEXT,
    status TEXT,
    progress INTEGER,
    message TEXT,
    data TEXT,             -- JSON
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (workflow_id) REFERENCES workflows(id)
);

-- 论文索引表
CREATE TABLE papers (
    paper_id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    title TEXT NOT NULL,
    authors TEXT,          -- JSON array
    abstract TEXT,
    year TEXT,
    source TEXT,
    pdf_path TEXT,
    download_status TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (workflow_id) REFERENCES workflows(id)
);

-- 报告索引表
CREATE TABLE reports (
    report_id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    content_markdown TEXT,
    file_path TEXT,
    word_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (workflow_id) REFERENCES workflows(id)
);
```

---

## 7. 风险清单

### 7.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| WebSocket 断连 | 前端无法实时更新 | 中 | HTTP 轮询降级 + 自动重连 |
| 长时间任务超时 | 工作流中断 | 中 | 状态持久化，支持断点续跑 |
| 大文件下载失败 | PDF 缺失 | 中 | 重试机制 + 失败标记 |
| 并发工作流冲突 | 资源竞争 | 低 | 任务队列 + 信号量控制 |
| SQLite 锁竞争 | 写入阻塞 | 低 | WAL 模式 + 连接池 |
| 内存泄漏 | 服务崩溃 | 中 | 定期 GC + 任务清理 |
| LLM API 限流 | 请求被拒 | 高 | 指数退避重试 + 队列缓冲 |

### 7.2 架构风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 现有代码耦合 | 难以拆分 | 高 | 适配器模式，最小化改动 |
| 状态不一致 | 数据错误 | 中 | 事务操作 + 事件溯源 |
| 单点故障 | 服务不可用 | 低 | 健康检查 + 优雅降级 |
| 前端过度依赖 | 体验下降 | 中 | Loading 状态 + 错误边界 |

### 7.3 性能风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 工作流响应慢 | 体验差 | 高 | 后台任务 + 异步处理 |
| 大量论文存储 | 磁盘占用 | 高 | 定期清理 + 配置上限 |
| 数据库膨胀 | 查询变慢 | 中 | 分页 + 索引优化 |
| WebSocket 连接过多 | 资源耗尽 | 低 | 连接池 + 最大连接数 |

---

## 8. 代码复用决策

### 8.1 完全保留 (无需修改)

| 模块 | 文件 | 说明 |
|------|------|------|
| Tools | tools/*.py | 工具实现与 API 层解耦 |
| Skills | config/skills/*.yaml | 技能 prompts |
| Base Agent | agents/base.py | 基类保持不变 |
| Base Tool | tools/base.py | 基类保持不变 |

### 8.2 适配后使用 (新增适配器)

| 模块 | 适配方式 |
|------|----------|
| WorkflowEngine | 封装为 WorkflowRunner，添加事件回调 |
| 6 Agents | 通过 MultiAgentAdapter 调用，不直接实例化 |
| TaskMemory | 新增 WorkflowStore，TaskMemory 作为补充 |
| AgentMemory | 保留，仅内部使用 |
| LongTermMemory | 保留，通过 MemoryService 访问 |

### 8.3 需要重构

| 模块 | 重构内容 |
|------|----------|
| main.py | CLI 逻辑与业务逻辑分离 |
| workflow_engine.py | 添加事件发布器 + 取消令牌 |
| agents/*.py | 添加进度回调钩子 |

---

## 9. 下一步

Phase 0 完成后，进入 **Phase 1: 后端架构分层**。

Phase 1 主要任务：
1. 创建 `backend/` 目录结构
2. 实现 `backend/app/adapters/multi_agent_adapter.py`
3. 实现 `backend/app/services/workflow_runner.py`
4. 实现 `backend/app/services/workflow_store.py`
5. 实现 `backend/app/core/events.py` (事件总线)
6. 改造 `WorkflowEngine` 支持事件回调和取消

---

**审批状态**: 待用户确认

如对本方案有疑问或需要调整，请提出。
