<template>
  <Layout>
    <ContentContainer size="2xl">
      <PageContent spacing="loose" class="papers-page">
        <PageHeader
          title="论文库"
          subtitle="集中查看已有论文、上传新的 PDF，并基于已选论文快速发起工作流。"
        >
          <template #actions>
            <el-button class="page-nav-button" @click="$router.push('/dashboard')">返回仪表盘</el-button>
            <el-button type="primary" @click="scrollToUpload">
              <el-icon><Plus /></el-icon>
              上传论文
            </el-button>
          </template>
        </PageHeader>

        <el-card id="upload-section" class="upload-card feature-panel feature-panel--teal">
          <template #header>
            <div class="card-header">
              <div class="card-title-block">
                <span class="card-title">上传 PDF 论文</span>
                <span class="card-subtitle">上传后会直接进入下方论文库列表。</span>
              </div>
            </div>
          </template>

          <div class="upload-shell">
            <el-upload
              ref="uploadRef"
              drag
              multiple
              :auto-upload="false"
              :on-change="handleFileChange"
              :on-remove="handleFileRemove"
              accept=".pdf"
              class="upload-area"
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">
                拖拽文件到此处或<em>点击上传</em>
              </div>
              <template #tip>
                <div class="el-upload__tip">支持 PDF 格式，可一次上传多个文件。</div>
              </template>
            </el-upload>

            <div v-if="fileList.length > 0" class="pending-files">
              <div class="pending-files-title">待处理文件 ({{ fileList.length }})</div>
              <div class="pending-files-list">
                <div v-for="(file, index) in fileList" :key="index" class="pending-file-item">
                  <el-icon><Document /></el-icon>
                  <span class="pending-file-name">{{ file.name }}</span>
                  <el-tag size="small" :type="file.status === 'uploaded' ? 'success' : 'info'">
                    {{ file.status === 'uploaded' ? '已上传' : '待上传' }}
                  </el-tag>
                </div>
              </div>
            </div>

            <div class="upload-actions">
              <el-button
                type="primary"
                :loading="uploading"
                :disabled="fileList.length === 0"
                @click="handleUpload"
              >
                {{ uploading ? '上传中...' : '开始上传' }}
              </el-button>
              <el-button :disabled="fileList.length === 0" @click="handleClear">清空列表</el-button>
            </div>
          </div>
        </el-card>

        <el-card class="filter-card feature-panel feature-panel--blue">
          <el-form :inline="true" :model="filterForm" class="filter-form">
            <el-form-item label="工作流">
              <el-input
                v-model="filterForm.workflow_id"
                placeholder="工作流 ID"
                clearable
                class="filter-input"
              >
                <template #prefix>
                  <el-icon><Folder /></el-icon>
                </template>
              </el-input>
            </el-form-item>

            <el-form-item label="数据源">
              <el-select
                v-model="filterForm.source"
                placeholder="全部"
                clearable
                class="filter-select"
              >
                <el-option label="ArXiv" value="arxiv" />
                <el-option label="Google Scholar" value="google" />
                <el-option label="本地上传" value="local_upload" />
                <el-option label="恢复索引" value="recovered_file" />
              </el-select>
            </el-form-item>

            <el-form-item label="搜索">
              <el-input
                v-model="filterForm.search"
                placeholder="标题关键词"
                clearable
                class="filter-input filter-input--wide"
                @keyup.enter="loadPapers"
              >
                <template #prefix>
                  <el-icon><Search /></el-icon>
                </template>
              </el-input>
            </el-form-item>

            <el-form-item class="filter-actions">
              <el-button type="primary" @click="loadPapers">
                <el-icon><Search /></el-icon>
                搜索
              </el-button>
              <el-button @click="resetFilter">
                <el-icon><Refresh /></el-icon>
                重置
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <el-card class="batch-actions-card feature-panel feature-panel--emerald" v-if="selectedPapers.length > 0">
          <div class="batch-actions">
            <div class="selection-info">
              <el-icon class="selection-icon"><CircleCheckFilled /></el-icon>
              已选择 <strong>{{ selectedPapers.length }}</strong> 篇
            </div>
            <div class="action-buttons">
              <el-button type="success" @click="createWorkflowFromSelection">
                创建工作流
              </el-button>
              <el-button type="primary" @click="batchDownload">
                <el-icon><Download /></el-icon>
                批量下载
              </el-button>
              <el-button type="danger" @click="batchDelete">
                <el-icon><Delete /></el-icon>
                批量删除
              </el-button>
              <el-button link @click="selectedPapers = []">取消选择</el-button>
            </div>
          </div>
        </el-card>

        <el-card class="table-card feature-panel feature-panel--amber">
          <template #header>
            <div class="card-header">
              <div class="card-title-block">
                <span class="card-title">现有论文</span>
                <span class="card-subtitle">当前共 {{ total }} 篇，支持筛选、下载、解析与复用。</span>
              </div>
              <el-button @click="loadPapers">刷新列表</el-button>
            </div>
          </template>

          <div class="table-shell table-shell--wide">
            <el-table
              :data="papers"
              v-loading="loading"
              style="width: 100%"
              @selection-change="handleSelectionChange"
              class="papers-table"
            >
              <el-table-column type="selection" width="48" />

              <el-table-column prop="paper_id" label="ID" width="160">
                <template #default="{ row }">
                  <span class="paper-id">{{ truncateId(row.paper_id) }}</span>
                </template>
              </el-table-column>

              <el-table-column prop="title" label="标题" min-width="360">
                <template #default="{ row }">
                  <div class="paper-title-content">
                    <span class="paper-title">{{ row.title }}</span>
                    <div class="paper-tags">
                      <el-tag
                        :type="tagTypeMap[row.source] || 'info'"
                        size="small"
                        effect="light"
                      >
                        {{ row.source || 'unknown' }}
                      </el-tag>
                      <span v-if="row.year" class="year-tag">{{ row.year }}</span>
                    </div>
                  </div>
                </template>
              </el-table-column>

              <el-table-column prop="authors" label="作者" width="200">
                <template #default="{ row }">
                  <div class="authors-text">
                    {{ formatAuthors(row.authors) || '暂无作者信息' }}
                  </div>
                </template>
              </el-table-column>

              <el-table-column prop="workflow_id" label="来源工作流" width="170">
                <template #default="{ row }">
                  <span class="workflow-ref">{{ truncateId(row.workflow_id || 'unknown') }}</span>
                </template>
              </el-table-column>

              <el-table-column prop="pdf_available" label="PDF" width="90">
                <template #default="{ row }">
                  <el-tooltip :content="row.pdf_available ? '可下载' : '暂无 PDF'" placement="top">
                    <span class="pdf-status" :class="{ available: row.pdf_available }">
                      <el-icon :size="18">
                        <Check v-if="row.pdf_available" />
                        <Close v-else />
                      </el-icon>
                    </span>
                  </el-tooltip>
                </template>
              </el-table-column>

              <el-table-column label="操作" width="220" fixed="right">
                <template #default="{ row }">
                  <div class="row-actions">
                    <el-button
                      size="small"
                      type="primary"
                      link
                      @click="downloadPdf(row)"
                      :disabled="!row.pdf_available"
                    >
                      下载
                    </el-button>
                    <el-button
                      v-if="row.source === 'local_upload'"
                      size="small"
                      type="primary"
                      link
                      @click="parsePaper(row)"
                    >
                      解析
                    </el-button>
                    <el-button
                      size="small"
                      type="primary"
                      link
                      @click="previewPaper(row)"
                      :disabled="!row.pdf_available"
                    >
                      预览
                    </el-button>
                  </div>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <div class="pagination-wrapper">
            <el-pagination
              v-model:current-page="page"
              v-model:page-size="pageSize"
              :total="total"
              :page-sizes="[10, 20, 50, 100]"
              layout="total, sizes, prev, pager, next"
              @change="loadPapers"
              class="pagination"
            />
          </div>
        </el-card>
      </PageContent>
    </ContentContainer>

    <el-dialog v-model="parseDialogVisible" title="论文解析结果" width="60%">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="标题">{{ parseResult.title }}</el-descriptions-item>
        <el-descriptions-item label="摘要">{{ parseResult.abstract || '暂无' }}</el-descriptions-item>
        <el-descriptions-item label="页数">{{ parseResult.pages || 0 }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </Layout>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Plus,
  Search,
  Refresh,
  Folder,
  Download,
  Delete,
  CircleCheckFilled,
  Check,
  Close,
  UploadFilled,
  Document,
} from '@element-plus/icons-vue'
import { usePaperStore } from '@/stores'
import { uploadApi } from '@/api'
import { Layout, ContentContainer, PageContent, PageHeader } from '@/components/layout'

const router = useRouter()
const paperStore = usePaperStore()

const uploadRef = ref(null)
const papers = ref([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const selectedPapers = ref([])
const fileList = ref([])
const uploading = ref(false)
const parseDialogVisible = ref(false)
const parseResult = ref({})

const filterForm = reactive({
  workflow_id: '',
  source: '',
  search: '',
})

const tagTypeMap = {
  arxiv: 'primary',
  google: 'success',
  local_upload: 'warning',
  recovered_file: 'info',
}

const truncateId = (id) => {
  if (!id) return ''
  return id.length > 14 ? `${id.slice(0, 7)}...${id.slice(-7)}` : id
}

const formatAuthors = (authors) => {
  if (!authors) return ''
  if (Array.isArray(authors)) {
    if (authors.length === 0) return ''
    if (authors.length <= 2) return authors.join(', ')
    return `${authors.slice(0, 2).join(', ')} 等 ${authors.length} 人`
  }

  if (typeof authors === 'string') {
    try {
      const parsed = JSON.parse(authors)
      return formatAuthors(parsed)
    } catch {
      return authors
    }
  }

  return ''
}

const scrollToUpload = () => {
  document.getElementById('upload-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const resetFilter = () => {
  filterForm.workflow_id = ''
  filterForm.source = ''
  filterForm.search = ''
  page.value = 1
  loadPapers()
}

const loadPapers = async () => {
  loading.value = true
  try {
    await paperStore.fetchPapers({
      ...filterForm,
      page: page.value,
      page_size: pageSize.value,
    })
    papers.value = paperStore.papers
    total.value = paperStore.total
  } catch (err) {
    ElMessage.error('加载论文失败：' + err.message)
  } finally {
    loading.value = false
  }
}

const handleSelectionChange = (rows) => {
  selectedPapers.value = rows
}

const handleFileChange = (file) => {
  if (!fileList.value.find((item) => item.name === file.name)) {
    fileList.value.push({
      name: file.name,
      raw: file.raw,
      status: 'pending',
    })
  }
}

const handleFileRemove = (file) => {
  fileList.value = fileList.value.filter((item) => item.name !== file.name)
}

const handleClear = () => {
  fileList.value = []
  uploadRef.value?.clearFiles()
}

const handleUpload = async () => {
  const pendingFiles = fileList.value.filter((file) => file.status === 'pending')
  if (pendingFiles.length === 0) {
    ElMessage.info('没有待上传的文件')
    return
  }

  uploading.value = true
  try {
    const res = await uploadApi.uploadPapersBatch(pendingFiles.map((file) => file.raw))
    const { results, uploaded } = res.data

    fileList.value.forEach((file) => {
      const uploadedFile = results.find((item) => item.title === file.name.replace('.pdf', ''))
      if (uploadedFile) {
        file.status = 'uploaded'
        file.paperId = uploadedFile.paper_id
      }
    })

    ElMessage.success(`成功上传 ${uploaded} 篇论文`)
    await loadPapers()
  } catch (err) {
    ElMessage.error('上传失败：' + (err.response?.data?.detail || err.message))
  } finally {
    uploading.value = false
  }
}

const parsePaper = async (paper) => {
  try {
    const res = await uploadApi.parsePaper(paper.paper_id)
    parseResult.value = res.data
    parseDialogVisible.value = true
    ElMessage.success('解析成功')
    await loadPapers()
  } catch (err) {
    ElMessage.error('解析失败：' + (err.response?.data?.detail || err.message))
  }
}

const previewPaper = (paper) => {
  window.open(`/api/papers/${paper.paper_id}/pdf`, '_blank')
}

const downloadPdf = async (paper) => {
  if (!paper.pdf_available) {
    ElMessage.warning('该论文暂无 PDF 可用')
    return
  }

  try {
    await paperStore.downloadPdf(paper.paper_id)
    ElMessage.success('下载已开始')
  } catch (err) {
    ElMessage.error('下载失败：' + err.message)
  }
}

const createWorkflowFromSelection = async () => {
  if (selectedPapers.value.length === 0) {
    ElMessage.warning('请先选择论文')
    return
  }

  try {
    const res = await uploadApi.createWorkflowFromPapers(
      selectedPapers.value.map((paper) => paper.paper_id),
      '基于已选论文的分析工作流'
    )
    ElMessage.success('工作流创建成功')
    router.push(`/workflows/${res.data.id}`)
  } catch (err) {
    ElMessage.error('创建失败：' + (err.response?.data?.detail || err.message))
  }
}

const batchDownload = async () => {
  try {
    await paperStore.batchDownload(selectedPapers.value.map((paper) => paper.paper_id))
    ElMessage.success('批量下载已开始')
  } catch (err) {
    ElMessage.error('批量下载失败：' + err.message)
  }
}

const batchDelete = async () => {
  if (!confirm(`确定删除选中的 ${selectedPapers.value.length} 篇论文吗？此操作不可恢复。`)) {
    return
  }

  try {
    await paperStore.batchDelete(selectedPapers.value.map((paper) => paper.paper_id))
    selectedPapers.value = []
    await loadPapers()
    ElMessage.success('删除成功')
  } catch (err) {
    ElMessage.error('批量删除失败：' + err.message)
  }
}

onMounted(() => {
  loadPapers()
})
</script>

<style scoped>
@import '@/styles/variables.css';

.papers-page {
  animation: fadeInUp 0.5s var(--ease-out);
}

.upload-card,
.filter-card,
.batch-actions-card,
.table-card {
  background: var(--bg-primary);
  border-radius: var(--radius-2xl);
  border: 1px solid var(--border-primary);
  box-shadow: var(--shadow-sm);
}

.upload-card :deep(.el-card__body),
.filter-card :deep(.el-card__body),
.table-card :deep(.el-card__body) {
  padding: var(--space-5);
}

.upload-card :deep(.el-card__header) {
  background: var(--brand-header-bg);
  border-bottom: 1px solid var(--brand-header-border);
}

.table-card :deep(.el-card__header) {
  background: var(--brand-header-bg);
  border-bottom: 1px solid var(--brand-header-border);
}

.batch-actions-card {
  background: var(--info-bg);
}

.batch-actions-card :deep(.el-card__body) {
  padding: var(--space-3) var(--space-4);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
}

.card-title-block {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.card-title {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.card-subtitle {
  color: var(--text-secondary);
  font-size: var(--text-sm);
}

.upload-shell {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.upload-area {
  width: 100%;
}

.pending-files {
  border-radius: var(--radius-xl);
  background: var(--bg-secondary);
  padding: var(--space-4);
}

.pending-files-title {
  margin-bottom: var(--space-3);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
}

.pending-files-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.pending-file-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.pending-file-name {
  flex: 1;
  min-width: 0;
  color: var(--text-primary);
}

.upload-actions {
  display: flex;
  gap: var(--space-3);
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.filter-input,
.filter-select {
  min-width: 180px;
  max-width: 360px;
}

.filter-input--wide {
  max-width: 460px;
}

.filter-input :deep(.el-input__wrapper),
.filter-select :deep(.el-select__wrapper) {
  border-radius: var(--radius-lg);
}

.filter-actions {
  margin-left: auto;
}

.filter-actions .el-button {
  border-radius: var(--radius-lg);
  padding: var(--space-2) var(--space-4);
}

.batch-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-4);
}

.selection-info {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.selection-icon {
  color: var(--brand-primary);
  font-size: 18px;
}

.selection-info strong {
  color: var(--text-primary);
}

.action-buttons,
.row-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.table-card {
  overflow: hidden;
}

.papers-table {
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.papers-table :deep(.el-table__header th) {
  background-color: var(--brand-table-header);
  color: var(--slate-700);
  font-weight: var(--font-semibold);
  font-size: var(--text-sm);
  padding: 12px 16px;
  border-bottom: 1px solid var(--brand-header-border);
}

.papers-table :deep(.el-table__body td) {
  padding: 16px;
  border-bottom-color: var(--border-secondary);
}

.papers-table :deep(.el-table__row:hover) {
  background-color: var(--brand-table-row-hover);
}

.paper-id,
.workflow-ref {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--slate-700);
  background: rgba(239, 246, 255, 0.9);
  border: 1px solid rgba(37, 99, 235, 0.14);
  padding: 2px 8px;
  border-radius: var(--radius-md);
}

.paper-title-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.paper-title {
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  line-height: var(--leading-relaxed);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.paper-tags {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.year-tag {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  background: var(--bg-tertiary);
  padding: 2px 8px;
  border-radius: var(--radius-md);
}

.authors-text {
  color: var(--text-secondary);
  font-size: var(--text-sm);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.pdf-status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--text-disabled);
  transition: var(--transition-base);
}

.pdf-status.available {
  color: var(--success-base);
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: var(--space-5);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-secondary);
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 768px) {
  .upload-actions,
  .batch-actions,
  .action-buttons,
  .row-actions,
  .filter-form {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-actions {
    margin-left: 0;
  }

  .card-header {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
