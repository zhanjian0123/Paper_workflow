# 工作流取消功能改进总结

## 改进日期
2026-04-09

## 改进概述

本次改进增强了工作流取消功能，使其更加可靠、灵活和及时。

---

## 主要改进

### 1. WorkflowContext 增强

#### 新增功能

| 功能 | 说明 |
|------|------|
| `asyncio.Event` 取消信号 | 使用异步事件进行取消通知，支持 `await ctx.wait_for_cancel()` |
| 取消原因记录 | `cancel_reason` 字段记录取消原因 |
| 优雅关闭标志 | `is_graceful_shutdown` 标志支持优雅关闭 |
| 超时监控 | `start_timeout_monitor()` 自动监控工作流超时 |
| `is_cancelled()` 方法 | 统一的取消检查接口 |

#### 修改的方法

```python
# 旧代码
def request_cancel(self) -> None:
    self.cancel_requested = True

# 新代码
async def request_cancel(self, reason: str = "用户请求取消", graceful: bool = False) -> None:
    self.cancel_requested = True
    self.cancel_reason = reason
    self.is_graceful_shutdown = graceful
    self._cancel_event.set()
```

---

### 2. WorkflowRunner 增强

#### 新增功能

| 功能 | 说明 |
|------|------|
| 默认超时配置 | `default_timeout_seconds` 参数（默认 1 小时） |
| 启动时超时设置 | `start_workflow(timeout_seconds=...)` |
| 优雅关闭 | `cancel_workflow(graceful=True, graceful_timeout=30.0)` |
| 取消锁 | 防止重复取消的 `asyncio.Lock` |
| 资源清理 | `_cleanup_workflow()` 统一清理资源 |
| 取消处理 | `_handle_cancelled_workflow()` 处理取消逻辑 |

#### 修改的方法

```python
# 旧代码
async def cancel_workflow(self, workflow_id: str) -> bool:
    # 简单取消

# 新代码
async def cancel_workflow(
    self,
    workflow_id: str,
    reason: str = "用户请求取消",
    graceful: bool = False,
    graceful_timeout: float = 30.0,
) -> bool:
    # 支持优雅关闭、取消原因记录、资源清理
```

---

### 3. API 路由增强

#### 修改的文件

- `backend/app/schemas/workflow.py` - 取消请求模型
- `backend/app/api/routes/workflows.py` - 取消端点

#### 新增参数

```python
class WorkflowCancelRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=500, description="取消原因")
    graceful: bool = Field(default=False, description="是否优雅关闭")
    graceful_timeout: float = Field(default=30.0, ge=0, le=300, description="优雅关闭超时时间")
```

---

### 4. WorkflowEngine 增强

#### 修改的文件

- `core/workflow_engine.py`

#### 改进内容

- 使用 `is_cancelled()` 替代直接检查 `cancel_requested`
- 取消原因传递到错误消息
- 更详细的取消日志

---

## 使用示例

### 基本取消

```python
# 创建工作流
workflow_id = await runner.create_workflow(query="transformer")

# 启动工作流
await runner.start_workflow(workflow_id, adapter)

# 取消工作流
await runner.cancel_workflow(workflow_id, reason="用户请求")
```

### 优雅关闭

```python
# 优雅关闭：等待当前操作完成（最多 30 秒）
await runner.cancel_workflow(
    workflow_id,
    reason="用户请求",
    graceful=True,
    graceful_timeout=30.0,
)
```

### 超时配置

```python
# 创建时配置默认超时
runner = WorkflowRunner(workflow_store, default_timeout_seconds=1800)

# 启动时覆盖超时
await runner.start_workflow(workflow_id, adapter, timeout_seconds=3600)
```

### API 调用

```bash
# 基本取消
curl -X POST http://localhost:8000/api/workflows/{id}/cancel

# 带参数取消
curl -X POST http://localhost:8000/api/workflows/{id}/cancel \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "用户请求",
    "graceful": true,
    "graceful_timeout": 60
  }'
```

---

## 新增文件

```
projects/
└── tests/
    └── test_workflow_cancel.py    # 取消功能单元测试（18 个测试）
```

---

## 修改文件列表

| 文件 | 改动说明 |
|------|----------|
| `backend/app/services/workflow_runner.py` | 增强 WorkflowContext 和 WorkflowRunner |
| `backend/app/schemas/workflow.py` | 取消请求模型新增参数 |
| `backend/app/api/routes/workflows.py` | 取消端点支持新参数 |
| `core/workflow_engine.py` | 使用新的取消检查接口 |
| `tests/test_workflow_cancel.py` | 新增单元测试 |

---

## 测试覆盖

运行测试：
```bash
pytest tests/test_workflow_cancel.py -v
```

18 个测试全部通过：
- ✅ `test_cancel_event` - 取消事件触发
- ✅ `test_wait_for_cancel` - 等待取消请求
- ✅ `test_wait_for_cancel_timeout` - 等待超时
- ✅ `test_timeout_monitor` - 超时监控
- ✅ `test_no_timeout_without_monitor` - 无监控不超时
- ✅ `test_cleanup` - 资源清理
- ✅ `test_progress_calculation` - 进度计算
- ✅ `test_graceful_shutdown_flag` - 优雅关闭标志
- ✅ `test_create_workflow` - 创建工作流
- ✅ `test_cancel_nonexistent_workflow` - 取消不存在
- ✅ `test_cancel_completed_workflow` - 取消已完成
- ✅ `test_cancel_running_workflow` - 取消运行中
- ✅ `test_graceful_shutdown` - 优雅关闭
- ✅ `test_is_running` - 检查运行状态
- ✅ `test_get_running_workflows` - 获取运行列表
- ✅ `test_shutdown` - 关闭运行器
- ✅ `test_concurrent_cancel_requests` - 并发取消
- ✅ `test_cancel_during_completion` - 完成中取消

---

## 向后兼容性

所有改动都是向后兼容的：

- `cancel_workflow()` 的新参数都有默认值
- 旧的取消调用方式仍然有效
- API 端点的新参数都是可选的

---

## 下一步建议

1. **Agent 内部取消检查** - 在 Agent 的 `run_once()` 方法中添加定期取消检查
2. **PDF 下载取消** - 确保长时间运行的 PDF 下载操作响应取消
3. **WebSocket 实时推送** - 将取消状态通过 WebSocket 推送给前端
4. **取消统计** - 记录取消原因和取消率分析

---

**改进完成日期**: 2026-04-09  
**测试通过率**: 100% (18/18)  
**新增代码行数**: ~400 行  
**修改代码行数**: ~200 行
