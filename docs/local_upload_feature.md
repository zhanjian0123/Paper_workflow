# 本地论文上传和解析功能实现总结

## 实现日期
2026-04-09

## 概述

实现了本地论文上传和解析功能，支持用户上传本地 PDF 论文并跳过搜索阶段直接进行分析、写作、审核和编辑。

---

## 主要功能

### 1. 论文上传

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/upload/papers` | POST | 上传单篇论文 PDF |
| `/api/upload/papers/batch` | POST | 批量上传论文 PDF |
| `/api/upload/papers/{paper_id}/parse` | POST | 解析论文元数据和摘要 |
| `/api/upload/papers/{paper_id}/full-parse` | POST | 完整解析论文全文 |
| `/api/upload/create-workflow` | POST | 从上传的论文创建工作流 |
| `/api/workflows/from-local-papers` | POST | 从本地论文启动工作流（跳过搜索） |

### 2. 工作流支持

- 从本地论文启动工作流时跳过搜索阶段
- 自动从 PDF 中提取摘要（如果未提供）
- 支持 5 阶段完整流程：加载→分析→写作→审核→编辑

---

## 新增文件

| 文件 | 行数 | 说明 |
|------|------|------|
| `backend/app/api/routes/upload.py` | ~350 | 上传 API 路由 |

---

## 修改文件

| 文件 | 改动 |
|------|------|
| `backend/app/main.py` | 注册上传路由 |
| `backend/app/adapters/multi_agent_adapter.py` | 添加 `load_local_papers()` 方法 |
| `backend/app/services/workflow_runner.py` | 添加 `start_workflow_with_local_papers()` 方法 |
| `backend/app/api/routes/workflows.py` | 添加 `from-local-papers` 端点 |

---

## API 使用示例

### 上传单篇论文

```bash
curl -X POST http://localhost:8000/api/upload/papers \
  -F "file=@/path/to/paper.pdf" \
  -F "title=My Paper Title"
```

响应：
```json
{
  "paper_id": "uploaded_a1b2c3d4",
  "title": "My Paper Title",
  "file_path": "output/uploads/uploaded_a1b2c3d4.pdf",
  "file_size": 1234567,
  "message": "上传成功"
}
```

### 批量上传

```bash
curl -X POST http://localhost:8000/api/upload/papers/batch \
  -F "files=@paper1.pdf" \
  -F "files=@paper2.pdf" \
  -F "files=@paper3.pdf"
```

响应：
```json
{
  "uploaded": 3,
  "failed": 0,
  "results": [
    {"paper_id": "uploaded_xxx", "title": "Paper 1", "file_path": "..."},
    {"paper_id": "uploaded_yyy", "title": "Paper 2", "file_path": "..."},
    {"paper_id": "uploaded_zzz", "title": "Paper 3", "file_path": "..."}
  ],
  "errors": []
}
```

### 解析论文

```bash
curl -X POST http://localhost:8000/api/upload/papers/{paper_id}/parse
```

响应：
```json
{
  "paper_id": "uploaded_xxx",
  "title": "论文标题",
  "authors": "[\"作者 1\", \"作者 2\"]",
  "abstract": "提取的摘要内容...",
  "metadata": {...},
  "pages": 10
}
```

### 从本地论文创建工作流

```bash
curl -X POST http://localhost:8000/api/workflows/from-local-papers \
  -H "Content-Type: application/json" \
  -d '{
    "paper_ids": ["uploaded_xxx", "uploaded_yyy"],
    "query": "深度学习在 NLP 中的应用"
  }'
```

---

## 核心类设计

### MultiAgentAdapter 新增方法

```python
async def load_local_papers(
    self,
    paper_ids: List[str],
    workflow_id: str,
    on_progress: Optional[Callable] = None,
) -> Dict[str, Any]:
    """
    从本地文件加载论文（跳过搜索阶段）
    
    功能：
    - 从数据库获取论文记录
    - 解析 PDF 获取摘要（如果需要）
    - 转换为标准论文格式
    - 缓存到内存供后续阶段使用
    """
```

### WorkflowRunner 新增方法

```python
async def start_workflow_with_local_papers(
    self,
    workflow_id: str,
    adapter: Any,
    paper_ids: list[str],
    timeout_seconds: Optional[int] = None,
) -> None:
    """
    从本地论文启动工作流（跳过搜索阶段）
    
    流程：
    1. 加载本地论文
    2. 分析论文
    3. 撰写报告
    4. 审核报告
    5. 编辑最终报告
    """
```

---

## 摘要提取逻辑

使用启发式规则从 PDF 全文中提取摘要：

1. 查找包含 "Abstract" 或 "摘要" 的行
2. 收集后续行直到遇到空行或新章节
3. 如果未找到摘要，返回前 500 字

```python
def _extract_abstract_from_text(self, full_text: str) -> str:
    lines = full_text.split('\n')
    abstract_lines = []
    in_abstract = False

    for line in lines:
        line_lower = line.lower().strip()
        
        # 检测摘要开始
        if 'abstract' in line_lower or '摘要' in line_lower:
            in_abstract = True
            continue
        
        # 检测摘要结束
        if in_abstract:
            if line.strip() == '' and abstract_lines:
                break
            abstract_lines.append(line)

    return '\n'.join(abstract_lines).strip()
```

---

## 数据库设计

### PaperRecord 新增字段

```python
@dataclass
class PaperRecord:
    paper_id: str
    workflow_id: str  # "uploaded" 标记为上传论文
    title: str
    authors: str  # JSON array
    abstract: str
    year: Optional[str]
    source: str  # "local_upload" 标记来源
    pdf_path: Optional[str]
    download_status: str  # "downloaded" 表示已上传
    created_at: str
```

---

## 工作流程

### 从本地论文启动工作流

```
1. 上传 PDF → /api/upload/papers
   ↓
2. （可选）解析摘要 → /api/upload/papers/{id}/parse
   ↓
3. 创建工作流 → /api/workflows/from-local-papers
   ↓
4. 后台执行:
   - 加载本地论文 (search 阶段)
   - 分析论文 (analyst 阶段)
   - 撰写报告 (writer 阶段)
   - 审核报告 (reviewer 阶段)
   - 编辑报告 (editor 阶段)
   ↓
5. 完成
```

---

## 错误处理

| 场景 | 处理 |
|------|------|
| 非 PDF 文件 | 返回 400 错误 |
| 文件过大 | FastAPI 默认限制（可配置） |
| PDF 解析失败 | 返回警告，使用文件名作为标题 |
| 论文不存在 | 返回 404 错误 |
| 工作流启动失败 | 更新状态为 failed，记录错误 |

---

## 向后兼容性

所有改动都是向后兼容的：
- 新增 API 端点不影响现有功能
- 工作流系统仍支持从 ArXiv 搜索
- `source` 字段新增 `local_upload` 值

---

## 下一步建议

1. **前端 UI** - 实现文件拖拽上传界面
2. **进度显示** - 上传进度条和解析状态
3. **批量操作** - 支持选择多篇上传的论文启动工作流
4. **元数据增强** - 使用 LLM 从全文提取更准确的元数据
5. **PDF 预览** - 在上传后提供 PDF 在线预览

---

**实现完成日期**: 2026-04-09  
**新增代码行数**: ~600 行  
**API 端点数量**: 6 个
