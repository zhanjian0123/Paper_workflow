"""
FastAPI 应用入口
"""
from fastapi import FastAPI, Request, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime
import logging

from backend.app.core.config import get_settings, Settings
from backend.app.core.deps import generate_request_id, create_error_response
from backend.app.api.routes import workflows, papers, reports, memory, upload
from backend.app.api.websocket import websocket_handler
from backend.app.core.events import get_event_bus, Event

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例"""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="文献分析工作流系统 API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # 注册 HTTP 中间件（在 CORS 之前，确保 CORS 能正确处理 OPTIONS）
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        """添加 Request ID 到响应头"""
        response = await call_next(request)
        request_id = f"req_{datetime.now().strftime('%Y%m%d%H%M%S')}_{hash(request) & 0xFFFFFFFF:08x}"
        response.headers["X-Request-ID"] = request_id
        return response

    # 配置 CORS（必须在 HTTP 中间件之后注册，确保最外层）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(workflows.router)
    app.include_router(papers.router)
    app.include_router(reports.router)
    app.include_router(memory.router)
    app.include_router(upload.router)

    # 注册异常处理
    register_exception_handlers(app)

    # 注册事件处理
    register_events(app, settings)

    return app


def register_exception_handlers(app: FastAPI) -> None:
    """注册异常处理器"""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """处理 HTTP 异常"""
        request_id = request.headers.get("X-Request-ID", "unknown")

        return JSONResponse(
            status_code=exc.status_code,
            content=create_error_response(
                error=exc.detail,
                message=exc.detail,
                request_id=request_id,
            ),
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """处理未捕获的异常"""
        request_id = request.headers.get("X-Request-ID", "unknown")

        logger.exception(f"未捕获的异常：{exc}")

        return JSONResponse(
            status_code=500,
            content=create_error_response(
                error="internal_server_error",
                message=f"服务器内部错误：{str(exc)}",
                request_id=request_id,
            ),
        )


def register_events(app: FastAPI, settings: Settings) -> None:
    """注册应用生命周期事件"""

    @app.on_event("startup")
    async def startup_event():
        """应用启动时执行"""
        logger.info(f"启动 {settings.app_name}")
        logger.info(f"环境：{'development' if settings.debug else 'production'}")
        logger.info(f"端口：{settings.port}")

        # 初始化全局组件
        from backend.app.core.deps import get_workflow_store
        get_workflow_store()  # 初始化数据库

        from backend.app.core.events import get_event_bus
        get_event_bus()  # 初始化事件总线

        from backend.app.services.output_index_sync import (
            merge_legacy_workflow_store,
            sync_output_indexes,
        )

        merge_stats = merge_legacy_workflow_store(
            primary_db_path=settings.workflow_store_db_path,
            legacy_db_path=settings.legacy_workflow_store_db_path,
        )
        sync_stats = sync_output_indexes(store=get_workflow_store(), settings=settings)

        logger.info(f"历史数据库合并完成：{merge_stats}")
        logger.info(f"输出目录索引同步完成：{sync_stats}")
        logger.info("全局组件初始化完成")

    @app.on_event("shutdown")
    async def shutdown_event():
        """应用关闭时执行"""
        logger.info("应用关闭中...")

        # 清理资源
        from backend.app.services.workflow_runner import WorkflowRunner
        # TODO: 清理运行中的工作流

        logger.info("应用已关闭")


# 创建应用实例
app = create_app()


# WebSocket 路由
@app.websocket("/ws/workflows/{workflow_id}")
async def websocket_workflow(websocket: WebSocket, workflow_id: str):
    """订阅工作流实时事件"""
    await websocket_handler(websocket, workflow_id, get_event_bus())


# 健康检查
@app.get("/health", tags=["health"])
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
    }


# 根路径
@app.get("/", tags=["root"])
async def root():
    """根路径"""
    return {
        "name": "Literature Workflow API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()

    uvicorn.run(
        "backend.app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
