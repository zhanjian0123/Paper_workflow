# 文献分析工作流系统

基于多 Agent 协作的学术论文智能处理系统，支持从 ArXiv 和 Google Scholar 搜索、下载、分析论文，并自动生成学术报告。

## 快速开始

### 系统要求

- Node.js >= 18
- Python >= 3.10
- 环境变量：`ANTHROPIC_API_KEY` 或其他 LLM API Key

### 安装

```bash
# 克隆项目
git clone <repository-url>
cd literature-workflow

# 安装 Python 依赖
pip install -r requirements.txt

# 安装前端依赖
cd frontend
npm install
```

### 配置

```bash
# 复制环境变量配置
cp .env.example .env

# 编辑 .env 文件，设置 API Key
# ANTHROPIC_API_KEY=your_api_key_here
```

### 启动服务

```bash
# 终端 1 - 启动后端
cd backend
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

# 终端 2 - 启动前端
cd frontend
npm run dev
```

访问 http://localhost:5173 使用 Web 界面。

## 功能特性

### 核心功能

- **多数据源搜索**: 支持 ArXiv 和 Google Scholar
- **智能分析**: Agent 自动提取论文关键信息
- **报告生成**: 自动生成学术报告
- **实时进度**: WebSocket 实时推送工作流状态
- **长期记忆**: 保存用户偏好和反馈

### 工作流阶段

| 阶段 | 权重 | 说明 |
|------|------|------|
| 文献搜索 | 25% | 从 ArXiv/Google Scholar 搜索并下载论文 |
| 文献分析 | 25% | 提取研究问题、方法、创新点 |
| 报告撰写 | 25% | 生成报告草稿 |
| 质量审核 | 15% | 审核报告质量 |
| 最终编辑 | 10% | 整合反馈生成终稿 |

## 项目结构

```
projects/
├── backend/              # 后端服务 (FastAPI)
│   └── app/
│       ├── api/         # API 路由
│       ├── schemas/     # Pydantic 模型
│       ├── services/    # 业务服务
│       ├── core/        # 核心配置
│       └── adapters/    # 适配器
├── frontend/            # 前端应用 (Vue 3)
│   └── src/
│       ├── api/        # API 客户端
│       ├── components/ # 通用组件
│       ├── composables/# 组合式函数
│       ├── stores/     # Pinia 状态
│       ├── views/      # 页面组件
│       └── utils/      # 工具函数
├── core/               # 核心引擎
├── agents/             # Agent 实现
├── tools/              # 工具实现
├── memory/             # 记忆系统
├── config/             # 配置文件
└── output/             # 输出目录
```

## API 文档

启动后端后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 主要端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/workflows` | POST | 创建工作流 |
| `/api/workflows` | GET | 获取工作流列表 |
| `/api/workflows/{id}` | GET | 获取工作流详情 |
| `/api/workflows/{id}/cancel` | POST | 取消工作流 |
| `/api/papers` | GET | 获取论文列表 |
| `/api/reports` | GET | 获取报告列表 |
| `/api/memory` | GET/POST | 记忆管理 |
| `/ws/workflows/{id}` | WS | WebSocket 订阅 |

## CLI 使用

```bash
# 完整工作流
python main.py -r "搜索 transformer 相关论文" -y "2024-2026" -m 10

# 指定数据源
python main.py -r "deep learning" -s google -m 5

# 直接运行 Agent
python main.py -a search -r "machine learning"

# 交互模式
python main.py
```

### 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-r, --request` | 用户请求 | - |
| `-a, --agent` | 直接运行 Agent | - |
| `-y, --year-range` | 年份范围 | - |
| `-m, --max-papers` | 最大论文数 | 10 |
| `-s, --source` | 数据源 | arxiv |

## 技术栈

### 后端
- FastAPI - Web 框架
- Pydantic - 数据验证
- SQLite - 数据持久化
- WebSocket - 实时通信
- asyncio - 异步编程

### 前端
- Vue 3 - UI 框架
- Vite - 构建工具
- Pinia - 状态管理
- Element Plus - UI 组件
- Axios - HTTP 客户端
- markdown-it - Markdown 渲染

### AI 集成
- Multi-Agent 系统 - 6 个协作 Agent
- Tool 系统 - 可扩展工具集
- 技能系统 - YAML 配置技能
- 记忆系统 - 长期记忆存储

## 开发指南

### 添加新路由

```python
# backend/app/api/routes/custom.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/custom", tags=["custom"])

@router.get("")
async def get_custom():
    return {"data": "custom"}
```

```python
# backend/app/main.py
from backend.app.api.routes import custom
app.include_router(custom.router)
```

### 添加新组件

```vue
<!-- frontend/src/components/Custom.vue -->
<template>
  <div class="custom">{{ text }}</div>
</template>

<script setup>
defineProps({ text: String })
</script>
```

## 常见问题

### API 调用失败

1. 检查 `.env` 文件中 API Key 配置
2. 确认网络连接正常
3. 查看后端日志

### 前端无法连接后端

1. 确认后端服务运行在 8000 端口
2. 检查 Vite 代理配置 (`vite.config.js`)
3. 清除浏览器缓存

### 工作流执行失败

1. 查看工作流日志
2. 检查输出目录权限
3. 确认模型配置正确

## 许可证

MIT
