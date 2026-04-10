# Paper Workflow

一个面向学术文献场景的多 Agent 工作流系统，提供命令行与 Web 两种使用方式。它可以围绕一个研究主题执行论文检索、PDF 获取、本地论文上传、内容分析、报告生成与结果管理，并通过实时事件流展示工作流进度。

## 项目概览

- 多 Agent 协作执行文献分析流程，包含 `search`、`analyst`、`writer`、`reviewer`、`editor` 等角色
- 支持 `ArXiv`、`Google Scholar` 和本地上传 PDF 三种论文来源
- 提供 FastAPI 后端与 Vue 3 前端，可在浏览器中创建、跟踪和管理工作流
- 提供 CLI 入口，适合脚本化执行和本地调试
- 内置工作流存储、报告管理、论文批量下载/删除、WebSocket 实时状态推送

## 主要能力

### 文献获取

- 根据研究主题检索论文
- 按年份范围过滤结果
- 限制下载论文数量
- 支持单篇或批量上传本地 PDF
- 支持对上传 PDF 进行元数据和文本解析

### 工作流处理

- 搜索阶段：检索并准备论文材料
- 分析阶段：提取研究问题、方法、贡献与关键信息
- 撰写阶段：生成结构化综述或分析报告
- 审核阶段：检查内容质量与逻辑完整性
- 编辑阶段：整合修改意见，生成最终结果

### 结果管理

- 工作流状态与阶段进度可视化
- 论文列表筛选、PDF 下载、ZIP 批量下载
- 报告查看、Markdown 下载、ZIP 批量下载
- 工作流取消、批量删除及关联文件清理

## 技术栈

### 后端

- Python 3.10+
- FastAPI
- Pydantic / pydantic-settings
- SQLite
- WebSocket
- aiohttp / aiofiles

### 前端

- Vue 3
- Vite
- Pinia
- Vue Router
- Element Plus

### AI 与流程层

- 多 Agent 架构
- Skill 配置系统
- Tool Registry / MCP 集成
- 长短期记忆模块

## 仓库结构

```text
.
├── agents/                  # 多 Agent 实现
├── backend/                 # FastAPI 后端
│   └── app/
│       ├── adapters/        # 工作流适配层
│       ├── api/             # REST / WebSocket 接口
│       ├── core/            # 配置与依赖
│       ├── schemas/         # 数据模型
│       └── services/        # 业务服务
├── config/                  # Agent、Skill、MCP 配置
├── core/                    # CLI / 工作流核心引擎
├── docs/                    # 补充文档
├── frontend/                # Vue 前端
├── mcp/                     # MCP 客户端与工具注册
├── memory/                  # 记忆系统
├── output/                  # 工作流输出、数据库、上传文件
├── scripts/                 # 辅助脚本
├── tests/                   # 测试
├── tools/                   # 检索、PDF、文件等工具
└── main.py                  # CLI 入口
```

## 环境要求

- Python `3.10+`
- Node.js `18+`
- npm `9+` 或兼容版本
- 可用的 LLM API Key

## 环境变量

项目根目录的 `.env` 会被后端自动加载。可以直接参考 `.env.example`：

```bash
ANTHROPIC_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
ANTHROPIC_API_KEY=sk-your-api-key-here
MODEL_ID=qwen3.5-plus
```

说明：

- `ANTHROPIC_BASE_URL`：当前示例使用 DashScope 的 Anthropic 兼容接口
- `ANTHROPIC_API_KEY`：模型调用密钥
- `MODEL_ID`：默认模型名

## 本地开发

### 1. 安装依赖

```bash
pip install -r requirements.txt
pip install -r backend/requirements.txt

cd frontend
npm install
cd ..
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

按需修改 `.env` 中的模型地址、Key 与模型名。

### 3. 启动后端

```bash
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

后端启动后可访问：

- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`
- `http://localhost:8000/health`

### 4. 启动前端

```bash
cd frontend
npm run dev
```

默认开发地址通常为 `http://localhost:5173`。

## Docker 启动

项目提供了前后端的 Docker Compose 配置：

```bash
docker compose up --build
```

默认映射：

- 前端：`http://localhost`
- 后端：`http://localhost:8000`

## CLI 用法

命令行入口为项目根目录的 `main.py`。

### 运行完整工作流

```bash
python main.py -r "搜索 transformer 方向的最新研究" -y "2024-2026" -m 10 -s arxiv
```

### 指定数据源

```bash
python main.py -r "multimodal reasoning" -s both -m 5
```

### 直接运行某个 Agent

```bash
python main.py -a search -r "graph neural networks"
```

### 常用参数

| 参数 | 说明 |
|------|------|
| `-r, --request` | 用户请求 / 研究主题 |
| `-a, --agent` | 直接运行指定 Agent |
| `-y, --year-range` | 年份范围，如 `2024-2026` |
| `-m, --max-papers` | 最大论文数 |
| `-s, --source` | `arxiv` / `google` / `both` |
| `--model` | 指定模型名称 |
| `--api-key` | 覆盖环境变量中的 API Key |
| `--base-url` | 覆盖环境变量中的 Base URL |

## Web API 概览

### 工作流

- `POST /api/workflows`：创建工作流
- `GET /api/workflows`：获取工作流列表
- `GET /api/workflows/{id}`：获取工作流详情
- `POST /api/workflows/{id}/cancel`：取消工作流
- `POST /api/workflows/batch-delete`：批量删除工作流
- `POST /api/workflows/from-local-papers`：基于本地上传论文创建工作流

### 上传

- `POST /api/upload/papers`：上传单个 PDF
- `POST /api/upload/papers/batch`：批量上传 PDF
- `POST /api/upload/papers/{paper_id}/parse`：解析上传论文

### 论文

- `GET /api/papers`：分页查询论文
- `GET /api/papers/{paper_id}`：获取论文详情
- `GET /api/papers/{paper_id}/pdf`：下载单篇 PDF
- `POST /api/papers/batch-download`：批量下载 PDF ZIP
- `POST /api/papers/batch-delete`：批量删除论文

### 报告

- `GET /api/reports`：获取报告列表
- `GET /api/reports/{report_id}`：获取报告详情
- `GET /api/reports/{report_id}/download`：下载 Markdown 或 PDF
- `GET /api/reports/workflow/{workflow_id}`：按工作流获取报告
- `POST /api/reports/batch-download`：批量下载报告 ZIP
- `POST /api/reports/batch-delete`：批量删除报告

### 实时事件

- `WS /ws/workflows/{workflow_id}`：订阅工作流进度事件

## 输出目录

运行过程中生成的数据默认写入 `output/`：

- `output/workflows/`：工作流产物
- `output/papers/`：下载的论文 PDF
- `output/uploads/`：用户上传的 PDF
- `output/workflow_store.db`：工作流与索引数据库

## 测试

```bash
pytest
```

当前仓库中已有的测试覆盖了部分工具、查询改写与工作流取消逻辑。

## 补充文档

- `docs/api_guide.md`
- `docs/deployment.md`
- `docs/local_upload_feature.md`
- `docs/workflow_cancel_improvement.md`

## 许可证

MIT
