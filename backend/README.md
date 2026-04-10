# Backend API

文献分析工作流系统的后端 API 服务。

## 技术栈

- **FastAPI** - 现代高性能 Web 框架
- **Pydantic** - 数据验证
- **Uvicorn** - ASGI 服务器
- **SQLite** - 数据持久化
- **WebSocket** - 实时事件推送

## 快速开始

### 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 配置环境变量

```bash
cp ../.env.example .env
# 编辑 .env 配置
```

### 启动服务

```bash
# 开发模式（自动重载）
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### API 文档

启动后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 目录结构

```
backend/app/
├── main.py                    # FastAPI 应用入口
├── api/
│   ├── routes/
│   │   ├── workflows.py       # 工作流 API
│   │   ├── papers.py          # 论文 API
│   │   ├── reports.py         # 报告 API
│   │   └── memory.py          # 记忆 API
│   └── websocket.py           # WebSocket 管理器
├── schemas/
│   ├── workflow.py            # 工作流 Schema
│   ├── paper.py               # 论文 Schema
│   ├── report.py              # 报告 Schema
│   ├── memory.py              # 记忆 Schema
│   └── common.py              # 通用 Schema
├── services/
│   ├── workflow_runner.py     # 工作流运行器
│   ├── workflow_store.py      # 工作流存储
│   ├── paper_service.py       # 论文服务
│   ├── report_service.py      # 报告服务
│   └── memory_service.py      # 记忆服务
├── core/
│   ├── config.py              # 配置管理
│   ├── deps.py                # 依赖注入
│   └── events.py              # 事件总线
└── adapters/
    └── multi_agent_adapter.py # 现有代码适配器
```

## API 端点

### 工作流

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/workflows | 创建工作流 |
| GET | /api/workflows | 获取工作流列表 |
| GET | /api/workflows/{id} | 获取工作流详情 |
| POST | /api/workflows/{id}/cancel | 取消工作流 |
| GET | /api/workflows/{id}/papers | 获取论文列表 |
| GET | /api/workflows/{id}/report | 获取报告 |
| WS | /ws/workflows/{id} | 订阅实时事件 |

### 论文

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/papers | 获取论文列表 |
| GET | /api/papers/{id} | 获取论文详情 |
| GET | /api/papers/{id}/pdf | 下载 PDF |

### 报告

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/reports | 获取报告列表 |
| GET | /api/reports/{id} | 获取报告详情 |
| GET | /api/reports/{id}/download | 下载报告 |

### 记忆

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/memory | 获取记忆列表 |
| POST | /api/memory | 保存记忆 |
| DELETE | /api/memory/{id} | 删除记忆 |
| POST | /api/memory/cleanup | 清理记忆 |

## 配置项

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| host | HOST | 0.0.0.0 | 监听地址 |
| port | PORT | 8000 | 监听端口 |
| debug | DEBUG | false | 调试模式 |
| cors_origins | CORS_ORIGINS | [...] | CORS 白名单 |
| output_dir | OUTPUT_DIR | output | 输出目录 |
| log_level | LOG_LEVEL | INFO | 日志级别 |

## 错误处理

统一错误响应格式：

```json
{
  "error": "error_code",
  "message": "错误描述",
  "details": {},
  "timestamp": "2026-04-07T10:30:00",
  "request_id": "req_xxx"
}
```

## WebSocket 事件

事件格式：

```json
{
  "event_type": "stage_progress",
  "workflow_id": "wf_xxx",
  "stage": "search",
  "status": "in_progress",
  "progress": 60,
  "message": "正在下载论文 PDF...",
  "data": {"papers_found": 8},
  "timestamp": "2026-04-07T10:30:00"
}
```

事件类型：
- `stage_started` - 阶段开始
- `stage_progress` - 阶段进度更新
- `stage_completed` - 阶段完成
- `stage_failed` - 阶段失败
- `workflow_completed` - 工作流完成
- `workflow_failed` - 工作流失败
- `workflow_cancelled` - 工作流取消
- `heartbeat` - 心跳

## 开发指南

### 添加新路由

1. 在 `api/routes/` 创建新模块
2. 定义 Router 和端点
3. 在 `main.py` 中注册路由

### 添加新 Schema

1. 在 `schemas/` 创建新模块
2. 定义 Pydantic 模型
3. 在路由中引用

### 添加新服务

1. 在 `services/` 创建新模块
2. 实现业务逻辑
3. 在路由中通过依赖注入使用
