<template>
  <Layout>
    <ContentContainer size="2xl">
      <PageContent spacing="loose" class="workflows-page">
        <PageHeader
          title="工作流"
          subtitle="管理和监控所有文献分析工作流"
        >
          <template #actions>
            <el-button class="page-nav-button" @click="$router.push('/dashboard')">返回仪表盘</el-button>
          </template>
        </PageHeader>

        <!-- 批量操作栏 -->
        <el-card class="batch-actions-card feature-panel feature-panel--rose" v-if="selectedWorkflows.length > 0">
      <div class="batch-actions">
        <div class="selection-info">
          <el-icon class="selection-icon"><CircleCheckFilled /></el-icon>
          已选择 <strong>{{ selectedWorkflows.length }}</strong> 项
        </div>
        <div class="action-buttons">
          <el-button type="danger" @click="batchDelete">
            <el-icon><Delete /></el-icon>
            批量删除
          </el-button>
          <el-button link @click="selectedWorkflows = []">
            取消选择
          </el-button>
        </div>
      </div>
        </el-card>

        <!-- 工作流列表 -->
        <el-card class="table-card feature-panel feature-panel--blue">
      <div class="table-shell table-shell--wide">
      <el-table
        :data="workflows"
        v-loading="loading"
        style="width: 100%"
        @selection-change="handleSelectionChange"
        class="workflow-table"
        header-cell-class-name="table-header"
      >
        <el-table-column type="selection" width="48" />

        <el-table-column prop="id" label="ID" width="200">
          <template #default="{ row }">
            <span class="workflow-id" @click="$router.push(`/workflows/${row.id}`)">
              {{ truncateId(row.id) }}
              <el-icon class="copy-icon"><CopyDocument /></el-icon>
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="query" label="研究主题" min-width="280">
          <template #default="{ row }">
            <div class="query-content">
              <span class="query-text">{{ row.query }}</span>
              <el-tag
                v-if="row.year_range"
                type="info"
                size="small"
                effect="light"
              >
                {{ row.year_range }}
              </el-tag>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="source" label="数据源" width="100">
          <template #default="{ row }">
            <span :class="['source-badge', `source-${row.source}`]">
              {{ row.source }}
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <status-tag :status="row.status" show-dot />
          </template>
        </el-table-column>

        <el-table-column prop="progress" label="进度" width="140">
          <template #default="{ row }">
            <div class="progress-cell">
              <el-progress
                :percentage="row.progress"
                :status="row.status === 'completed' ? 'success' : undefined"
                :stroke-width="8"
              />
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="papers_found" label="论文" width="80">
          <template #default="{ row }">
            <span class="count-value">{{ row.papers_found }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="created_at" label="创建时间" width="170">
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
                @click="$router.push(`/workflows/${row.id}`)"
              >
                详情
              </el-button>
              <el-button
                v-if="row.status === 'running' || row.status === 'pending'"
                size="small"
                type="danger"
                link
                @click="cancelWorkflow(row)"
              >
                取消
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
          @change="loadWorkflows"
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
import { Delete, CircleCheckFilled, CopyDocument } from '@element-plus/icons-vue'
import { useWorkflowStore } from '@/stores'
import StatusTag from '@/components/StatusTag.vue'
import { Layout, ContentContainer, PageContent, PageHeader } from '@/components/layout'

const router = useRouter()
const workflowStore = useWorkflowStore()

const workflows = ref([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const selectedWorkflows = ref([])

const truncateId = (id) => {
  if (!id) return ''
  return id.length > 16 ? `${id.slice(0, 8)}...${id.slice(-8)}` : id
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

const loadWorkflows = async () => {
  loading.value = true
  try {
    await workflowStore.fetchWorkflows({ page: page.value, page_size: pageSize.value })
    workflows.value = workflowStore.workflows
    total.value = workflowStore.total
  } finally {
    loading.value = false
  }
}

const handleSelectionChange = (rows) => {
  selectedWorkflows.value = rows
}

const cancelWorkflow = async (row) => {
  if (!confirm(`确定要取消工作流 "${row.query.substring(0, 30)}..." 吗？`)) return

  try {
    await workflowStore.cancelWorkflow(row.id)
    await loadWorkflows()
  } catch (err) {
    alert('取消失败：' + err.message)
  }
}

const batchDelete = async () => {
  if (!confirm(`确定删除选中的 ${selectedWorkflows.value.length} 个工作流吗？此操作不可恢复。`)) {
    return
  }

  try {
    await workflowStore.batchDeleteWorkflows(
      selectedWorkflows.value.map((workflow) => workflow.id)
    )
    selectedWorkflows.value = []
    await loadWorkflows()
  } catch (err) {
    alert('批量删除失败：' + err.message)
  }
}

onMounted(() => {
  loadWorkflows()
})
</script>

<style scoped>
@import '@/styles/variables.css';

.workflows-page {
  animation: fadeInUp 0.5s var(--ease-out);
}

/* =============================================
   批量操作卡片
   ============================================= */
.batch-actions-card {
  background: var(--danger-bg);
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

.workflow-table {
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.workflow-table :deep(.el-table__header th) {
  background-color: var(--brand-table-header);
  color: var(--slate-700);
  font-weight: var(--font-semibold);
  font-size: var(--text-sm);
  padding: 12px 16px;
  border-bottom: 1px solid var(--brand-header-border);
}

.workflow-table :deep(.el-table__body td) {
  padding: 16px;
  border-bottom-color: var(--border-secondary);
}

.workflow-table :deep(.el-table__row:hover) {
  background-color: var(--brand-table-row-hover);
}

/* ID 样式 */
.workflow-id {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--slate-700);
  background: rgba(239, 246, 255, 0.9);
  border: 1px solid rgba(37, 99, 235, 0.14);
  padding: 2px 8px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: var(--transition-base);
}

.workflow-id:hover {
  background: rgba(219, 234, 254, 0.96);
}

.copy-icon {
  font-size: 12px;
  opacity: 0.6;
}

.workflow-id:hover .copy-icon {
  opacity: 1;
}

/* 查询内容 */
.query-content {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.query-text {
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
}

/* 数据源徽章 */
.source-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
}

.source-arxiv {
  background: var(--info-light);
  color: var(--info-dark);
}

.source-google {
  background: var(--success-light);
  color: var(--success-dark);
}

.source-both {
  background: var(--warning-light);
  color: var(--warning-dark);
}

/* 进度单元格 */
.progress-cell {
  width: 120px;
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
  color: var(--text-secondary);
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
