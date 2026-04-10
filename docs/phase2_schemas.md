# Phase 2: 领域模型与接口契约

**日期**: 2026-04-07
**状态**: 设计稿

---

## 1. Pydantic Schema 定义

### 1.1 工作流 Schema (`backend/app/schemas/workflow.py`)

```python
"""
工作流相关的 Pydantic 模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class WorkflowStatus(str, Enum):
    """工作流状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowStage(str, Enum):
    """工作流阶段"""
    SEARCH = "search"
    ANALYST = "analyst"
    WRITER = "writer"
    REVIEWER = "reviewer"
    EDITOR = "editor"


class WorkflowCreateRequest(BaseModel):
    """
    创建工作流请求
    
    POST /api/workflows
    """
    query: str = Field(
        ..., 
        description="研究主题", 
        min_length=1,
        max_length=1000,
        examples=["搜索关于 transformer 的最新论文"]
    )
    year_range: Optional[str] = Field(
        None, 
        description="年份范围，如 2024-2026 或 2025",
        pattern=r"^\d{4}(-\d{4})?$",
        examples=["2024-2026", "2025"]
    )
    max_papers: int = Field(
        default=10, 
        ge=1, 
        le=100, 
        description="最大论文数量"
    )
    source: str = Field(
        default="arxiv", 
        pattern="^(arxiv|google|both)$",
        description="数据源：arxiv/google/both"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "搜索关于 transformer 的最新论文",
                "year_range": "2024-2026",
                "max_papers": 10,
                "source": "arxiv"
            }
        }


class WorkflowStageStatus(BaseModel):
    """阶段状态"""
    stage: WorkflowStage
    status: str = Field(
        ..., 
        pattern="^(pending|in_progress|completed|failed)$"
    )
    progress: int = Field(0, ge=0, le=100, description="阶段进度百分比")
    message: str
    papers_found: int = Field(0, ge=0, description="当前找到的论文数")
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "stage": "search",
                "status": "in_progress",
                "progress": 60,
                "message": "正在下载论文 PDF...",
                "papers_found": 8,
                "started_at": "2026-04-07T10:30:00",
                "completed_at": None
            }
        }


class WorkflowSummary(BaseModel):
    """
    工作流摘要 (列表项)
    
    GET /api/workflows
    """
    id: str
    query: str
    status: WorkflowStatus
    current_stage: Optional[WorkflowStage]
    progress: int = Field(0, ge=0, le=100, description="总体进度百分比")
    papers_found: int
    created_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class WorkflowDetail(BaseModel):
    """
    工作流详情
    
    GET /api/workflows/{id}
    """
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
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "wf_abc123",
                "query": "搜索关于 transformer 的最新论文",
                "year_range": "2024-2026",
                "max_papers": 10,
                "source": "arxiv",
                "status": "running",
                "current_stage": "analyst",
                "stages": [
                    {
                        "stage": "search",
                        "status": "completed",
                        "progress": 100,
                        "message": "找到 10 篇论文",
                        "papers_found": 10,
                        "started_at": "2026-04-07T10:30:00",
                        "completed_at": "2026-04-07T10:32:00"
                    },
                    {
                        "stage": "analyst",
                        "status": "in_progress",
                        "progress": 40,
                        "message": "正在分析论文...",
                        "papers_found": 10,
                        "started_at": "2026-04-07T10:32:00",
                        "completed_at": None
                    }
                ],
                "progress": 45,
                "message": "正在分析论文内容",
                "papers_found": 10,
                "result": None,
                "error": None,
                "created_at": "2026-04-07T10:30:00",
                "updated_at": "2026-04-07T10:33:00",
                "completed_at": None
            }
        }


class WorkflowEvent(BaseModel):
    """
    工作流事件 (WebSocket 推送)
    
    WS /ws/workflows/{id}
    """
    workflow_id: str
    event_type: str = Field(
        ..., 
        pattern="^(stage_started|stage_progress|stage_completed|workflow_completed|workflow_failed|workflow_cancelled)$"
    )
    stage: Optional[WorkflowStage]
    status: Optional[str]
    progress: int = Field(ge=0, le=100)
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "workflow_id": "wf_abc123",
                "event_type": "stage_progress",
                "stage": "analyst",
                "status": "in_progress",
                "progress": 40,
                "message": "正在分析第 4 篇论文",
                "data": {"current_paper_index": 4, "total": 10},
                "timestamp": "2026-04-07T10:33:00"
            }
        }


class WorkflowCancelRequest(BaseModel):
    """取消工作流请求"""
    reason: Optional[str] = Field(None, max_length=500)


class WorkflowCancelResponse(BaseModel):
    """取消工作流响应"""
    workflow_id: str
    status: str = Field(..., pattern="^(cancelled|already_completed|not_found)$")
    message: str


class WorkflowListResponse(BaseModel):
    """工作流列表响应"""
    items: List[WorkflowSummary]
    total: int
    page: int
    page_size: int
    has_more: bool
    
    class Config:
        json_schema_extra = {
            "example": {
                "items": [
                    {
                        "id": "wf_abc123",
                        "query": "搜索关于 transformer 的最新论文",
                        "status": "completed",
                        "current_stage": None,
                        "progress": 100,
                        "papers_found": 10,
                        "created_at": "2026-04-07T10:30:00",
                        "completed_at": "2026-04-07T10:45:00"
                    }
                ],
                "total": 1,
                "page": 1,
                "page_size": 20,
                "has_more": False
            }
        }
```

### 1.2 论文 Schema (`backend/app/schemas/paper.py`)

```python
"""
论文相关的 Pydantic 模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class PaperSummary(BaseModel):
    """
    论文摘要 (列表项)
    
    GET /api/papers
    """
    id: str
    paper_id: str  # ArXiv ID 或内部 ID
    title: str
    authors: List[str]
    year: Optional[str]
    source: str
    pdf_available: bool
    workflow_id: str
    
    class Config:
        from_attributes = True


class PaperDetail(BaseModel):
    """
    论文详情
    
    GET /api/papers/{id}
    """
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
    
    class Config:
        from_attributes = True


class PaperFilterRequest(BaseModel):
    """论文过滤请求"""
    workflow_id: Optional[str] = None
    source: Optional[str] = Field(None, pattern="^(arxiv|google)$")
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    search_query: Optional[str] = None


class PaperListResponse(BaseModel):
    """论文列表响应"""
    items: List[PaperSummary]
    total: int
    page: int
    page_size: int
    has_more: bool


class PaperDownloadResponse(BaseModel):
    """论文下载响应"""
    paper_id: str
    file_path: str
    file_size: int
    content_type: str = "application/pdf"
```

### 1.3 报告 Schema (`backend/app/schemas/report.py`)

```python
"""
报告相关的 Pydantic 模型
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ReportSummary(BaseModel):
    """
    报告摘要 (列表项)
    
    GET /api/reports
    """
    report_id: str
    workflow_id: str
    title: str  # 取报告第一行
    word_count: int
    paper_count: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class ReportDetail(BaseModel):
    """
    报告详情
    
    GET /api/reports/{id}
    """
    report_id: str
    workflow_id: str
    content_markdown: str
    file_path: Optional[str]
    word_count: int
    paper_count: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class ReportDownloadResponse(BaseModel):
    """报告下载响应"""
    report_id: str
    file_path: str
    file_size: int
    content_type: str  # text/markdown | application/pdf
```

### 1.4 记忆 Schema (`backend/app/schemas/memory.py`)

```python
"""
记忆相关的 Pydantic 模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class MemoryType(str, Enum):
    """记忆类型"""
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
    tags: Optional[List[str]]
    
    class Config:
        from_attributes = True


class MemoryCreateRequest(BaseModel):
    """创建记忆请求"""
    memory_type: MemoryType
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=50, max_length=5000)
    tags: Optional[List[str]] = None
    expires_days: Optional[int] = Field(None, ge=1, le=365)


class MemoryUpdateRequest(BaseModel):
    """更新记忆请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, min_length=50, max_length=5000)
    tags: Optional[List[str]] = None


class MemoryListResponse(BaseModel):
    """记忆列表响应"""
    items: List[MemoryEntrySchema]
    total: int
    by_type: dict[str, int]
    
    class Config:
        json_schema_extra = {
            "example": {
                "items": [
                    {
                        "id": "mem_abc123",
                        "memory_type": "user",
                        "name": "用户角色",
                        "description": "用户是数据科学家，擅长 Python",
                        "created_at": "2026-04-07T10:00:00",
                        "updated_at": "2026-04-07T10:00:00",
                        "expires_at": None,
                        "is_stale": False,
                        "is_expired": False,
                        "tags": ["user", "role"]
                    }
                ],
                "total": 1,
                "by_type": {"user": 1, "feedback": 0, "project": 0, "reference": 0}
            }
        }


class MemoryCleanupResponse(BaseModel):
    """记忆清理响应"""
    total: int
    expired: int
    stale: int
```

---

## 2. API 接口定义

### 2.1 工作流 API (`/api/workflows`)

```yaml
POST /api/workflows
  描述：创建新的工作流
  请求体：WorkflowCreateRequest
  响应：201 Created, WorkflowDetail
  错误：
    - 400 Bad Request: 参数验证失败
    - 500 Internal Error: 服务器错误

GET /api/workflows
  描述：获取工作流列表 (分页)
  查询参数：
    - page: int (default=1)
    - page_size: int (default=20, max=100)
    - status: WorkflowStatus (optional)
  响应：200 OK, WorkflowListResponse

GET /api/workflows/{id}
  描述：获取工作流详情
  路径参数：id (str)
  响应：200 OK, WorkflowDetail
  错误：
    - 404 Not Found: 工作流不存在

POST /api/workflows/{id}/cancel
  描述：取消运行中的工作流
  路径参数：id (str)
  请求体：WorkflowCancelRequest (optional)
  响应：200 OK, WorkflowCancelResponse
  错误：
    - 404 Not Found: 工作流不存在
    - 400 Bad Request: 工作流已完成/失败

WS /ws/workflows/{id}
  描述：订阅工作流实时事件
  路径参数：id (str)
  消息格式：WorkflowEvent
  关闭条件：
    - 工作流完成/失败/取消
    - 客户端断开
    - 超时 (30 分钟无活动)

GET /api/workflows/{id}/papers
  描述：获取工作流的论文列表
  路径参数：id (str)
  查询参数：
    - page: int
    - page_size: int
  响应：200 OK, PaperListResponse

GET /api/workflows/{id}/report
  描述：获取工作流的最终报告
  路径参数：id (str)
  响应：200 OK, ReportDetail
  错误：
    - 404 Not Found: 工作流或报告不存在
```

### 2.2 论文 API (`/api/papers`)

```yaml
GET /api/papers
  描述：获取所有论文 (全局)
  查询参数：
    - page: int
    - page_size: int
    - workflow_id: str (optional)
    - source: str (optional)
    - year_from: int (optional)
    - year_to: int (optional)
    - search: str (optional)
  响应：200 OK, PaperListResponse

GET /api/papers/{id}
  描述：获取论文详情
  路径参数：id (str)
  响应：200 OK, PaperDetail
  错误：
    - 404 Not Found: 论文不存在

GET /api/papers/{id}/pdf
  描述：下载论文 PDF
  路径参数：id (str)
  响应：200 OK, application/pdf (文件流)
  错误：
    - 404 Not Found: PDF 不存在
```

### 2.3 报告 API (`/api/reports`)

```yaml
GET /api/reports
  描述：获取所有报告列表
  查询参数：
    - page: int
    - page_size: int
  响应：200 OK, ReportListResponse

GET /api/reports/{id}
  描述：获取报告详情
  路径参数：id (str)
  响应：200 OK, ReportDetail
  错误：
    - 404 Not Found: 报告不存在

GET /api/reports/{id}/download
  描述：下载报告文件
  路径参数：id (str)
  查询参数：format (markdown|pdf, default=markdown)
  响应：200 OK, file stream
  错误：
    - 404 Not Found: 报告文件不存在
```

### 2.4 记忆 API (`/api/memory`)

```yaml
GET /api/memory
  描述：获取记忆列表
  查询参数：
    - type: MemoryType (optional)
    - search: str (optional)
    - exclude_expired: bool (default=true)
    - exclude_stale: bool (default=false)
  响应：200 OK, MemoryListResponse

POST /api/memory
  描述：保存新记忆
  请求体：MemoryCreateRequest
  响应：201 Created, MemoryEntrySchema
  错误：
    - 400 Bad Request: 参数验证失败/包含敏感信息

DELETE /api/memory/{id}
  描述：删除记忆
  路径参数：id (str)
  响应：204 No Content
  错误：
    - 404 Not Found: 记忆不存在

POST /api/memory/cleanup
  描述：清理过期/过时记忆
  响应：200 OK, MemoryCleanupResponse
```

---

## 3. 统一错误响应格式

```python
class ErrorResponse(BaseModel):
    """统一错误响应"""
    error: str
    message: str
    details: Optional[dict] = None
    timestamp: datetime
    request_id: str


# HTTP 状态码约定
# 200 OK - 成功
# 201 Created - 创建成功
# 204 No Content - 删除成功
# 400 Bad Request - 参数错误
# 404 Not Found - 资源不存在
# 409 Conflict - 状态冲突 (如取消已完成的工作流)
# 422 Unprocessable Entity - 验证错误 (Pydantic)
# 500 Internal Server Error - 服务器错误
```

---

## 4. WebSocket 事件类型

```python
# 阶段事件
STAGE_STARTED = "stage_started"      # 阶段开始
STAGE_PROGRESS = "stage_progress"    # 阶段进度更新
STAGE_COMPLETED = "stage_completed"  # 阶段完成
STAGE_FAILED = "stage_failed"        # 阶段失败

# 工作流事件
WORKFLOW_COMPLETED = "workflow_completed"  # 工作流完成
WORKFLOW_FAILED = "workflow_failed"        # 工作流失败
WORKFLOW_CANCELLED = "workflow_cancelled"  # 工作流取消

# 心跳
HEARTBEAT = "heartbeat"  # 心跳 (每 30 秒)
```

---

## 5. 数据验证规则

### 5.1 工作流创建

```python
# query
- 必须非空
- 最大长度 1000 字符
- 不允许纯空白字符

# year_range
- 可选
- 格式：YYYY 或 YYYY-YYYY
- 结束年份不能小于开始年份

# max_papers
- 默认值：10
- 范围：1-100

# source
- 默认值："arxiv"
- 允许值："arxiv" | "google" | "both"
```

### 5.2 记忆创建

```python
# 自动拒绝的内容
- 包含敏感关键词 (api_key, token, password 等)
- 纯代码结构信息 (def, class, import 等模式)
- 临时状态信息 (todo, in progress, task:等)
- 长度小于 50 字符

# 类型限制
- name: 1-200 字符
- description: 50-5000 字符
- expires_days: 1-365 天
```

---

**审批状态**: 待用户确认
