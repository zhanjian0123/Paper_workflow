# 重复下载问题修复

**修复日期**: 2026-04-08  
**问题**: 运行过程中后端会一直输出 "Downloaded" 不同 PDF 的命令

---

## 问题描述

用户在运行工作流时发现，每次执行都会重新下载所有论文 PDF，即使这些文件已经存在于输出目录中。

**症状**:
```
  ✓ Downloaded: 2301.00001.pdf
  ✓ Downloaded: 2301.00002.pdf
  ✓ Downloaded: 2301.00003.pdf
  ...
```

**影响**:
1. 浪费时间等待下载
2. 增加网络流量
3. 可能触发 ArXiv 的频率限制
4. 控制台输出混乱

---

## 根本原因

### 1. ArXiv Tool 未检查文件是否存在

**修复前** (`tools/arxiv_tool.py`):
```python
async def download(self, arxiv_id: str, save_dir: Optional[str] = None) -> ToolResult:
    """下载论文 PDF"""
    file_path = download_dir / f"{arxiv_id}.pdf"

    # ❌ 没有检查文件是否已存在，直接下载
    async with session.get(pdf_url) as response:
        # ...
```

### 2. Search Agent 未处理已存在情况

**修复前** (`agents/search.py`):
```python
for i, paper in enumerate(self._search_results):
    download_result = await self.tools_registry.execute_tool(
        "arxiv", "download", arxiv_id=arxiv_id, save_dir=download_dir
    )
    # ❌ 没有检查结果中的 skipped 标记
    print(f"  ✓ Downloaded: {arxiv_id}.pdf")
```

---

## 修复方案

### 1. ArXiv Tool 添加文件存在检查

**修复后** (`tools/arxiv_tool.py:173-192`):
```python
async def download(self, arxiv_id: str, save_dir: Optional[str] = None) -> ToolResult:
    """下载论文 PDF - 如果文件已存在则跳过下载"""
    file_path = download_dir / f"{arxiv_id}.pdf"

    # ✅ 检查文件是否已存在，如果存在则直接返回
    if file_path.exists():
        print(f"  ⏭️  文件已存在，跳过下载：{arxiv_id}.pdf")
        return ToolResult(
            success=True,
            data={"file_path": str(file_path), "arxiv_id": arxiv_id},
            metadata={"url": pdf_url, "skipped": True}
        )

    # 继续下载逻辑...
```

### 2. Search Agent 处理跳过下载

**修复后** (`agents/search.py:153-205`):
```python
downloaded = 0
skipped = 0  # ✅ 新增跳过计数器

for i, paper in enumerate(self._search_results):
    download_result = await self.tools_registry.execute_tool(
        "arxiv", "download", arxiv_id=arxiv_id, save_dir=download_dir
    )
    if download_result.success:
        paper["pdf_path"] = download_result.data.get("file_path")
        # ✅ 检查是否是跳过下载（文件已存在）
        if download_result.metadata and download_result.metadata.get("skipped"):
            skipped += 1
            print(f"  ⏭️  已跳过：{arxiv_id}.pdf (文件已存在)")
        else:
            downloaded += 1
            print(f"  ✓ Downloaded: {arxiv_id}.pdf")

# ✅ 下载完成输出
on_progress("search", 95, f"下载完成，新下载 {downloaded} 篇，跳过 {skipped} 篇")
```

---

## 修复效果

### 修复前
```
[Search] Searching for: transformer...
  ✓ Downloaded: 2301.00001.pdf
  ✓ Downloaded: 2301.00002.pdf
  ✓ Downloaded: 2301.00003.pdf
  ✓ Downloaded: 2301.00004.pdf
  ✓ Downloaded: 2301.00005.pdf
  ... (每次都重新下载)
```

### 修复后（首次运行）
```
[Search] Searching for: transformer...
  ✓ Downloaded: 2301.00001.pdf
  ✓ Downloaded: 2301.00002.pdf
  ✓ Downloaded: 2301.00003.pdf
  ✓ Downloaded: 2301.00004.pdf
  ✓ Downloaded: 2301.00005.pdf
```

### 修复后（再次运行，使用相同论文）
```
[Search] Searching for: transformer...
  ⏭️  已跳过：2301.00001.pdf (文件已存在)
  ⏭️  已跳过：2301.00002.pdf (文件已存在)
  ⏭️  已跳过：2301.00003.pdf (文件已存在)
  ⏭️  已跳过：2301.00004.pdf (文件已存在)
  ⏭️  已跳过：2301.00005.pdf (文件已存在)
下载完成，新下载 0 篇，跳过 10 篇
```

---

## 相关文件

- `tools/arxiv_tool.py` - ArXiv 下载工具（已修复）
- `agents/search.py` - Search Agent（已修复）

---

## 额外优化建议

### 1. 添加手动清理命令

如果需要强制重新下载，可以先清理输出目录：

```bash
rm -rf output/papers/*.pdf
```

### 2. 添加下载超时配置

对于下载慢的情况，可以在 `.env` 中添加配置：

```bash
ARXIV_DOWNLOAD_TIMEOUT=120
```

### 3. 批量下载优化

未来可以考虑使用批量下载工具（如 `aria2c`）来提高下载速度。

---

## 验证方法

运行两次相同的工作流，观察输出：

**第一次运行**:
```
✓ Downloaded: xxx.pdf (所有论文)
```

**第二次运行**:
```
⏭️  已跳过：xxx.pdf (文件已存在)
下载完成，新下载 0 篇，跳过 10 篇
```

如果看到以上输出，说明修复成功。
