<template>
  <Layout>
    <ContentContainer size="2xl">
      <PageContent spacing="loose" class="reports-page">
        <PageHeader
          title="报告"
          subtitle="查看和下载已生成的文献分析报告"
        >
          <template #actions>
            <el-button class="page-nav-button" @click="$router.push('/dashboard')">返回仪表盘</el-button>
          </template>
        </PageHeader>

        <!-- 批量操作栏 -->
        <el-card class="batch-actions-card feature-panel feature-panel--emerald" v-if="selectedReports.length > 0">
      <div class="batch-actions">
        <div class="selection-info">
          <el-icon class="selection-icon"><CircleCheckFilled /></el-icon>
          已选择 <strong>{{ selectedReports.length }}</strong> 份
        </div>
        <div class="action-buttons">
          <el-button type="primary" @click="batchDownload">
            <el-icon><Download /></el-icon>
            批量下载
          </el-button>
          <el-button type="danger" @click="batchDelete">
            <el-icon><Delete /></el-icon>
            批量删除
          </el-button>
          <el-button link @click="selectedReports = []">取消选择</el-button>
        </div>
      </div>
        </el-card>

        <!-- 报告列表 -->
        <el-card class="table-card feature-panel feature-panel--amber">
      <div class="table-shell table-shell--wide">
      <el-table
        :data="reports"
        v-loading="loading"
        style="width: 100%"
        @selection-change="handleSelectionChange"
        class="reports-table"
      >
        <el-table-column type="selection" width="48" />

        <el-table-column prop="report_id" label="ID" width="200">
          <template #default="{ row }">
            <span class="report-id">{{ truncateId(row.report_id) }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="workflow_id" label="工作流 ID" width="200">
          <template #default="{ row }">
            <span class="workflow-id-link" @click="$router.push(`/workflows/${row.workflow_id}`)">
              {{ truncateId(row.workflow_id) }}
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="title" label="标题" min-width="300">
          <template #default="{ row }">
            <div class="report-title">{{ row.title }}</div>
          </template>
        </el-table-column>

        <el-table-column prop="word_count" label="字数" width="100">
          <template #default="{ row }">
            <span class="count-value">{{ formatNumber(row.word_count) }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="paper_count" label="论文数" width="90">
          <template #default="{ row }">
            <span class="count-value">{{ row.paper_count }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            <span class="time-text">{{ formatDate(row.created_at) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons-cell">
              <el-button
                size="small"
                type="primary"
                link
                @click="$router.push(`/reports/${row.workflow_id}`)"
              >
                查看
              </el-button>
              <el-button
                size="small"
                type="primary"
                link
                @click="downloadReport(row.report_id)"
              >
                下载
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
      </div>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @change="loadReports"
          class="pagination"
        />
      </div>
        </el-card>
      </PageContent>
    </ContentContainer>
  </Layout>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Download, Delete, CircleCheckFilled } from '@element-plus/icons-vue'
import { useReportStore } from '@/stores'
import { Layout, ContentContainer, PageContent, PageHeader } from '@/components/layout'

const router = useRouter()
const reportStore = useReportStore()

const reports = ref([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const selectedReports = ref([])

const truncateId = (id) => {
  if (!id) return ''
  return id.length > 16 ? `${id.slice(0, 8)}...${id.slice(-8)}` : id
}

const formatNumber = (num) => {
  if (!num) return '0'
  if (num >= 10000) {
    return `${(num / 10000).toFixed(1)}w`
  }
  if (num >= 1000) {
    return `${(num / 1000).toFixed(1)}k`
  }
  return num.toString()
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now - date
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  if (hours < 24) return `${hours} 小时前`
  if (days < 7) return `${days} 天前`
  return date.toLocaleDateString('zh-CN')
}

const loadReports = async () => {
  loading.value = true
  try {
    await reportStore.fetchReports({ page: page.value, page_size: pageSize.value })
    reports.value = reportStore.reports
    total.value = reportStore.total
  } finally {
    loading.value = false
  }
}

const handleSelectionChange = (rows) => {
  selectedReports.value = rows
}

const downloadReport = async (reportId) => {
  try {
    await reportStore.downloadReport(reportId, 'markdown')
    ElMessage.success('下载已开始')
  } catch (err) {
    ElMessage.error('下载失败：' + err.message)
  }
}

const batchDownload = async () => {
  try {
    await reportStore.batchDownload(selectedReports.value.map((report) => report.report_id))
    ElMessage.success('批量下载已开始')
  } catch (err) {
    ElMessage.error('批量下载失败：' + err.message)
  }
}

const batchDelete = async () => {
  if (!confirm(`确定删除选中的 ${selectedReports.value.length} 份报告吗？此操作不可恢复。`)) {
    return
  }

  try {
    await reportStore.batchDelete(selectedReports.value.map((report) => report.report_id))
    selectedReports.value = []
    await loadReports()
    ElMessage.success('删除成功')
  } catch (err) {
    ElMessage.error('批量删除失败：' + err.message)
  }
}

onMounted(() => {
  loadReports()
})
</script>

<style scoped>
@import '@/styles/variables.css';

.reports-page {
  animation: fadeInUp 0.5s var(--ease-out);
}

/* =============================================
   批量操作卡片
   ============================================= */
.batch-actions-card {
  background: var(--info-bg);
  border-radius: var(--radius-xl);
  border: 1px solid var(--border-primary);
  box-shadow: var(--shadow-sm);
}

.batch-actions-card :deep(.el-card__body) {
  padding: var(--space-3) var(--space-4);
}

.batch-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
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
  font-weight: var(--font-semibold);
}

.action-buttons {
  display: flex;
  gap: var(--space-2);
}

/* =============================================
   表格卡片
   ============================================= */
.table-card {
  background: var(--bg-primary);
  border-radius: var(--radius-2xl);
  border: 1px solid var(--border-primary);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.table-card :deep(.el-card__body) {
  padding: var(--space-5);
}

.reports-table {
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.reports-table :deep(.el-table__header th) {
  background-color: var(--brand-table-header);
  color: var(--slate-700);
  font-weight: var(--font-semibold);
  font-size: var(--text-sm);
  padding: 12px 16px;
  border-bottom: 1px solid var(--brand-header-border);
}

.reports-table :deep(.el-table__body td) {
  padding: 16px;
  border-bottom-color: var(--border-secondary);
}

.reports-table :deep(.el-table__row:hover) {
  background-color: var(--brand-table-row-hover);
}

/* 报告 ID */
.report-id {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--slate-700);
  background: rgba(239, 246, 255, 0.9);
  border: 1px solid rgba(37, 99, 235, 0.14);
  padding: 2px 8px;
  border-radius: var(--radius-md);
}

/* 工作流 ID 链接 */
.workflow-id-link {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--brand-primary);
  cursor: pointer;
  transition: var(--transition-base);
}

.workflow-id-link:hover {
  color: var(--brand-primary-hover);
  text-decoration: underline;
}

/* 报告标题 */
.report-title {
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: var(--leading-relaxed);
}

/* 计数值 */
.count-value {
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

/* 时间文本 */
.time-text {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
}

/* 操作按钮 */
.action-buttons-cell {
  display: flex;
  gap: var(--space-1);
}

/* 分页 */
.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: var(--space-5);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-secondary);
}

/* =============================================
   动画
   ============================================= */
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

/* =============================================
   响应式
   ============================================= */
@media (max-width: 768px) {
  .batch-actions {
    flex-direction: column;
    gap: var(--space-3);
  }
}
</style>
