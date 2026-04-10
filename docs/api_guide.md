# API 使用指南

## 基础信息

- **Base URL**: `http://localhost:8000/api`
- **WebSocket URL**: `ws://localhost:8000/ws`
- **文档地址**: `http://localhost:8000/docs`

## 认证

当前版本无需认证，生产环境建议添加 JWT 认证。

## 工作流 API

### 创建工作流

```bash
POST /api/workflows
Content-Type: application/json

{
  "query": "transformer architecture",
  "year_range": "2024-2026",
  "max_papers": 10,
  "source": "arxiv"
}
```

响应：
```json
{
  "id": "wf_20260407123456_xxx",
  "query": "transformer architecture",
  "year_range": "2024-2026",
  "max_papers": 10,
  "source": "arxiv",
  "status": "pending",
  "progress": 0,
  "papers_found": 0,
  "created_at": "2026-04-07T12:34:56",
  "updated_at": "2026-04-07T12:34:56"
}
```

### 获取工作流列表

```bash
GET /api/workflows?page=1&page_size=20&status_filter=running
```

响应：
```json
{
  "items": [
    {
      "id": "wf_xxx",
      "query": "transformer",
      "status": "running",
      "progress": 50,
      "papers_found": 5,
      "created_at": "2026-04-07T12:34:56"
    }
  ],
  "total": 10,
  "page": 1,
  "page_size": 20,
  "has_more": false
}
```

### 获取工作流详情

```bash
GET /api/workflows/{workflow_id}
```

### 取消工作流

```bash
POST /api/workflows/{workflow_id}/cancel
Content-Type: application/json

{
  "reason": "用户取消"
}
```

### 获取工作流的论文

```bash
GET /api/workflows/{workflow_id}/papers?page=1&page_size=20
```

### 获取工作流的报告

```bash
GET /api/workflows/{workflow_id}/report
```

## 论文 API

### 获取论文列表

```bash
GET /api/papers?page=1&page_size=20&workflow_id=wf_xxx&source=arxiv&search=transformer
```

响应：
```json
{
  "items": [
    {
      "paper_id": "2301.12345",
      "workflow_id": "wf_xxx",
      "title": "Attention Is All You Need",
      "authors": ["Vaswani A", "Shazeer N", ...],
      "abstract": "...",
      "year": "2023",
      "source": "arxiv",
      "pdf_available": true,
      "download_status": "downloaded"
    }
  ],
  "total": 10,
  "page": 1,
  "page_size": 20
}
```

### 获取论文详情

```bash
GET /api/papers/{paper_id}
```

### 下载论文 PDF

```bash
GET /api/papers/{paper_id}/pdf
```

返回 PDF 文件（blob）

## 报告 API

### 获取报告列表

```bash
GET /api/reports?page=1&page_size=20&workflow_id=wf_xxx
```

### 获取报告详情

```bash
GET /api/reports/{report_id}
```

响应：
```json
{
  "report_id": "rpt_xxx",
  "workflow_id": "wf_xxx",
  "title": "文献分析报告",
  "word_count": 5000,
  "paper_count": 10,
  "content_markdown": "# 报告内容...",
  "created_at": "2026-04-07T12:34:56"
}
```

### 下载报告

```bash
GET /api/reports/{report_id}/download?format=markdown
```

支持格式：`markdown`, `pdf`（PDF 需要后端实现转换）

## 记忆 API

### 获取记忆列表

```bash
GET /api/memory?type_filter=user&page=1&page_size=20
```

响应：
```json
{
  "items": [
    {
      "id": "mem_xxx",
      "memory_type": "user",
      "name": "用户偏好",
      "description": "用户偏好简洁的代码风格...",
      "tags": ["preference", "coding"],
      "is_expired": false,
      "is_stale": false,
      "updated_at": "2026-04-07T12:34:56"
    }
  ],
  "total": 5,
  "by_type": {
    "user": 2,
    "feedback": 1,
    "project": 1,
    "reference": 1
  }
}
```

### 保存记忆

```bash
POST /api/memory
Content-Type: application/json

{
  "memory_type": "feedback",
  "name": "测试策略",
  "description": "集成测试必须使用真实数据库，不要 Mock",
  "tags": ["testing", "preference"],
  "expires_days": 90
}
```

### 更新记忆

```bash
PUT /api/memory/{memory_id}
Content-Type: application/json

{
  "name": "更新后的名称",
  "description": "更新后的描述",
  "tags": ["new", "tags"]
}
```

### 删除记忆

```bash
DELETE /api/memory/{memory_id}
```

### 清理记忆

```bash
POST /api/memory/cleanup
```

响应：
```json
{
  "expired": 2,
  "stale": 1
}
```

## WebSocket 实时事件

### 订阅工作流事件

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/workflows/{workflow_id}')

ws.onmessage = (event) => {
  const data = JSON.parse(event.data)
  console.log('事件类型:', data.event_type)
  console.log('阶段:', data.stage)
  console.log('进度:', data.progress)
  console.log('消息:', data.message)
}
```

事件类型：
- `stage_started` - 阶段开始
- `stage_progress` - 进度更新
- `stage_completed` - 阶段完成
- `stage_failed` - 阶段失败
- `workflow_completed` - 工作流完成
- `workflow_failed` - 工作流失败
- `workflow_cancelled` - 工作流取消
- `heartbeat` - 心跳

事件格式：
```json
{
  "event_type": "stage_progress",
  "workflow_id": "wf_xxx",
  "stage": "search",
  "status": "in_progress",
  "progress": 60,
  "message": "正在下载论文 PDF...",
  "data": {
    "papers_found": 5
  },
  "timestamp": "2026-04-07T12:34:56"
}
```

## 错误处理

错误响应格式：
```json
{
  "error": "error_code",
  "message": "错误描述",
  "details": {},
  "timestamp": "2026-04-07T12:34:56",
  "request_id": "req_xxx"
}
```

常见错误码：
- `validation_error` - 参数验证失败
- `not_found` - 资源不存在
- `already_exists` - 资源已存在
- `invalid_state` - 状态无效（如取消已完成的工作流）
- `internal_server_error` - 服务器内部错误

HTTP 状态码：
- `200` - 成功
- `201` - 创建成功
- `400` - 请求参数错误
- `404` - 资源不存在
- `409` - 冲突（资源已存在）
- `500` - 服务器内部错误

## 使用示例

### Python 示例

```python
import requests
import json

# 创建工作流
response = requests.post(
    'http://localhost:8000/api/workflows',
    json={
        'query': 'transformer',
        'year_range': '2024-2026',
        'max_papers': 5,
        'source': 'arxiv'
    }
)
workflow = response.json()
print(f"工作流 ID: {workflow['id']}")

# 获取状态
response = requests.get(
    f"http://localhost:8000/api/workflows/{workflow['id']}"
)
status = response.json()
print(f"状态：{status['status']}, 进度：{status['progress']}%")

# WebSocket 订阅
import websocket
import json

def on_message(ws, message):
    data = json.loads(message)
    print(f"收到事件：{data['event_type']} - {data['message']}")

ws = websocket.WebSocketApp(
    f"ws://localhost:8000/ws/workflows/{workflow['id']}",
    on_message=on_message
)
ws.run_forever()
```

### JavaScript 示例

```javascript
const API_BASE = 'http://localhost:8000/api'

// 创建工作流
async function createWorkflow(query, yearRange, maxPapers, source) {
  const response = await fetch(`${API_BASE}/workflows`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      year_range: yearRange,
      max_papers: maxPapers,
      source
    })
  })
  return await response.json()
}

// 获取工作流状态
async function getWorkflowStatus(id) {
  const response = await fetch(`${API_BASE}/workflows/${id}`)
  return await response.json()
}

// WebSocket 订阅
function subscribeWorkflow(id, onEvent) {
  const ws = new WebSocket(`ws://localhost:8000/ws/workflows/${id}`)
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    onEvent(data)
  }
  
  return ws
}

// 使用示例
const workflow = await createWorkflow('transformer', '2024-2026', 5, 'arxiv')
console.log('工作流已创建:', workflow.id)

const ws = subscribeWorkflow(workflow.id, (data) => {
  console.log(`${data.stage}: ${data.progress}% - ${data.message}`)
  
  if (data.event_type === 'workflow_completed') {
    console.log('工作流完成！')
    ws.close()
  }
})
```
