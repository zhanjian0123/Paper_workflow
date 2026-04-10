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
    """创建工作流请求"""
    query: str = Field(
        ...,
        description="研究主题",
        min_length=1,
        max_length=1000,
    )
    year_range: Optional[str] = Field(
        None,
        description="年份范围，如 2024-2026 或 2025",
        pattern=r"^\d{4}(-\d{4})?$",
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


class WorkflowStageStatus(BaseModel):
    """阶段状态"""
    stage: WorkflowStage
    status: str = Field(..., pattern="^(pending|in_progress|completed|failed)$")
    progress: int = Field(0, ge=0, le=100, description="阶段进度百分比")
    message: str
    papers_found: int = Field(0, ge=0, description="当前找到的论文数")
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class WorkflowSummary(BaseModel):
    """工作流摘要 (列表项)"""
    id: str
    query: str
    year_range: Optional[str] = None
    source: str
    status: WorkflowStatus
    current_stage: Optional[WorkflowStage]
    progress: int = Field(0, ge=0, le=100, description="总体进度百分比")
    papers_found: int
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class WorkflowDetail(BaseModel):
    """工作流详情"""
    id: str
    query: str
    rewritten_query: Optional[str] = None  # LLM 提炼后的关键词
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


class WorkflowEvent(BaseModel):
    """工作流事件 (WebSocket 推送)"""
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


class WorkflowCancelRequest(BaseModel):
    """取消工作流请求"""
    reason: Optional[str] = Field(None, max_length=500, description="取消原因")
    graceful: bool = Field(default=False, description="是否优雅关闭（等待当前操作完成）")
    graceful_timeout: float = Field(default=30.0, ge=0, le=300, description="优雅关闭等待超时（秒）")


class WorkflowCancelResponse(BaseModel):
    """取消工作流响应"""
    workflow_id: str
    status: str = Field(..., pattern="^(cancelled|already_completed|not_found)$")
    message: str


class WorkflowBatchRequest(BaseModel):
    """工作流批量操作请求"""
    workflow_ids: List[str] = Field(..., min_length=1)


class WorkflowBatchDeleteResponse(BaseModel):
    """工作流批量删除响应"""
    deleted_count: int
    deleted_paper_file_count: int
    deleted_report_file_count: int


class WorkflowListResponse(BaseModel):
    """工作流列表响应"""
    items: List[WorkflowSummary]
    total: int
    page: int
    page_size: int
    has_more: bool


# ========== 工作流模板相关模型 ==========

class WorkflowTemplateType(str, Enum):
    """内置模板类型"""
    LITERATURE_REVIEW = "literature_review"  # 标准文献综述
    QUICK_SURVEY = "quick_survey"  # 快速调研
    DEEP_ANALYSIS = "deep_analysis"  # 深度分析
    COMPARISON_STUDY = "comparison_study"  # 对比研究


class WorkflowStageConfig(BaseModel):
    """阶段配置"""
    stage: WorkflowStage
    enabled: bool = True
    weight: int = Field(25, ge=0, le=100, description="阶段权重")
    description: str = ""
    extra_params: Optional[Dict[str, Any]] = None


class WorkflowTemplate(BaseModel):
    """工作流模板"""
    id: str
    name: str
    template_type: WorkflowTemplateType
    description: str
    icon: str = "📄"
    stages: List[WorkflowStageConfig]
    default_config: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime


class WorkflowTemplateConfig(BaseModel):
    """用户自定义模板配置"""
    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field("", max_length=1000)
    base_template: Optional[str] = None  # 基于的模板 ID
    stages: List[WorkflowStageConfig]
    default_config: Dict[str, Any] = {}
    is_public: bool = False  # 是否公开


class WorkflowTemplateCreateRequest(BaseModel):
    """创建自定义模板请求"""
    name: str = Field(..., min_length=1, max_length=200, description="模板名称")
    description: str = Field("", max_length=1000, description="模板描述")
    base_template: Optional[str] = Field(None, description="基于的模板 ID")
    stages: Optional[List[WorkflowStageConfig]] = None
    default_config: Optional[Dict[str, Any]] = None
    is_public: bool = False


class WorkflowTemplateUpdateRequest(BaseModel):
    """更新模板请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    stages: Optional[List[WorkflowStageConfig]] = None
    default_config: Optional[Dict[str, Any]] = None
    is_public: Optional[bool] = None


class WorkflowFromTemplateRequest(BaseModel):
    """从模板创建工作流请求"""
    template_id: str = Field(..., description="模板 ID")
    query: str = Field(..., min_length=1, max_length=1000, description="研究主题")
    year_range: Optional[str] = Field(None, description="年份范围")
    max_papers: int = Field(default=10, ge=1, le=100, description="最大论文数量")
    source: str = Field(default="arxiv", pattern="^(arxiv|google|both)$")
    custom_params: Optional[Dict[str, Any]] = None  # 自定义参数覆盖


class WorkflowTemplateListResponse(BaseModel):
    """模板列表响应"""
    items: List[WorkflowTemplate]
    total: int
    builtin_count: int
    custom_count: int


class WorkflowTemplateDetail(BaseModel):
    """模板详情"""
    id: str
    name: str
    template_type: Optional[WorkflowTemplateType]
    description: str
    icon: str
    stages: List[WorkflowStageConfig]
    default_config: Dict[str, Any]
    is_builtin: bool
    is_public: bool
    created_at: datetime
    updated_at: datetime
    usage_count: int = 0  # 使用次数
