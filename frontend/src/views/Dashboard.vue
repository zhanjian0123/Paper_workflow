<template>
  <Layout>
    <ContentContainer size="2xl">
      <PageContent spacing="loose" class="dashboard">
        <PageHeader
          title="仪表盘"
          subtitle="欢迎回来，这里是您的文献分析工作流中心"
        />

        <!-- 统计卡片 -->
        <el-row :gutter="16" class="stats-row">
      <el-col :xs="24" :sm="12" :lg="6">
        <div class="stat-card stat-card--workflow" @click="$router.push('/workflows')">
          <div class="stat-card-icon">
            <el-icon :size="28"><Finished /></el-icon>
          </div>
          <div class="stat-card-content">
            <span class="stat-card-label">工作流总数</span>
            <div class="stat-card-value">
              <el-statistic :value="workflowTotal">
                <template #suffix>个</template>
              </el-statistic>
            </div>
            <div class="stat-card-trend">
              <el-icon class="trend-icon up"><Top /></el-icon>
              <span class="trend-text">活跃进行中</span>
            </div>
          </div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="stat-card stat-card--paper" @click="$router.push('/papers')">
          <div class="stat-card-icon">
            <el-icon :size="28"><Document /></el-icon>
          </div>
          <div class="stat-card-content">
            <span class="stat-card-label">论文总数</span>
            <div class="stat-card-value">
              <el-statistic :value="paperTotal">
                <template #suffix>篇</template>
              </el-statistic>
            </div>
            <div class="stat-card-trend">
              <el-icon class="trend-icon up"><Top /></el-icon>
              <span class="trend-text">已收录</span>
            </div>
          </div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="stat-card stat-card--report" @click="$router.push('/reports')">
          <div class="stat-card-icon">
            <el-icon :size="28"><Reading /></el-icon>
          </div>
          <div class="stat-card-content">
            <span class="stat-card-label">报告总数</span>
            <div class="stat-card-value">
              <el-statistic :value="reportTotal">
                <template #suffix>份</template>
              </el-statistic>
            </div>
            <div class="stat-card-trend">
              <el-icon class="trend-icon up"><Top /></el-icon>
              <span class="trend-text">已生成</span>
            </div>
          </div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <div class="stat-card stat-card--memory" @click="$router.push('/memory')">
          <div class="stat-card-icon">
            <el-icon :size="28"><Collection /></el-icon>
          </div>
          <div class="stat-card-content">
            <span class="stat-card-label">记忆条目</span>
            <div class="stat-card-value">
              <el-statistic :value="memoryTotal">
                <template #suffix>条</template>
              </el-statistic>
            </div>
            <div class="stat-card-trend">
              <el-icon class="trend-icon"><TrendCharts /></el-icon>
              <span class="trend-text">持续积累中</span>
            </div>
          </div>
        </div>
      </el-col>
        </el-row>

        <!-- 创建工作流卡片 -->
        <el-card class="create-card feature-panel feature-panel--blue" id="create-section">
      <template #header>
        <div class="card-header">
          <div class="card-title-section">
            <div class="title-icon-wrapper">
              <el-icon :size="20"><FolderAdd /></el-icon>
            </div>
            <span class="card-title">创建新工作流</span>
          </div>
        </div>
      </template>

      <el-form :model="createForm" label-width="100px" size="large" class="form-shell">
        <el-form-item label="研究主题" required>
          <el-input
            v-model="createForm.query"
            placeholder="例如：搜索关于 transformer 的最新论文"
            clearable
            class="input-lg input-measure"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-form-item>

        <el-row :gutter="24">
          <el-col :span="8">
            <el-form-item label="年份范围">
              <el-input
                v-model="createForm.year_range"
                placeholder="2024-2025"
                clearable
              >
                <template #prefix>
                  <el-icon><Calendar /></el-icon>
                </template>
              </el-input>
            </el-form-item>
          </el-col>

          <el-col :span="8">
            <el-form-item label="论文数量">
              <el-input-number
                v-model="createForm.max_papers"
                :min="1"
                :max="100"
                class="input-number-full"
              />
            </el-form-item>
          </el-col>

          <el-col :span="8">
            <el-form-item label="数据源">
              <el-select v-model="createForm.source" class="select-full">
                <el-option label="ArXiv" value="arxiv" />
                <el-option label="Google Scholar" value="google" />
                <el-option label="Both" value="both" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item>
          <el-button
            type="primary"
            class="submit-btn"
            @click="createWorkflow"
            :loading="creating"
          >
            <el-icon><FolderAdd /></el-icon>
            {{ creating ? '启动中...' : '启动工作流' }}
          </el-button>
          <span class="form-hint">启动后将自动执行搜索、分析、撰写流程</span>
        </el-form-item>
      </el-form>
        </el-card>

        <!-- 最近工作流 -->
        <el-card class="recent-card feature-panel feature-panel--blue">
      <template #header>
        <div class="card-header">
          <div class="card-title-section">
            <div class="title-icon-wrapper">
              <el-icon :size="20"><Clock /></el-icon>
            </div>
            <span class="card-title">最近工作流</span>
          </div>
          <el-button link type="primary" @click="$router.push('/workflows')">
            查看全部
            <el-icon><ArrowRight /></el-icon>
          </el-button>
        </div>
      </template>

      <div v-if="recentWorkflows.length === 0" class="empty-state">
        <el-empty description="暂无工作流，创建一个吧！" :image-size="80" />
      </div>

      <div v-else class="table-shell table-shell--wide">
        <el-table :data="recentWorkflows" style="width: 100%" class="workflow-table">
        <el-table-column prop="id" label="ID" width="180">
          <template #default="{ row }">
            <span class="workflow-id">{{ truncateId(row.id) }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="query" label="研究主题" min-width="280">
          <template #default="{ row }">
            <div class="query-content">
              <span class="query-text">{{ row.query }}</span>
              <el-tag
                v-if="row.source"
                :type="row.source === 'arxiv' ? 'primary' : 'success'"
                size="small"
                effect="light"
              >
                {{ row.source }}
              </el-tag>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <status-tag :status="row.status" show-dot />
          </template>
        </el-table-column>

        <el-table-column prop="progress" label="进度" width="150">
          <template #default="{ row }">
            <div class="progress-cell">
              <el-progress
                :percentage="row.progress"
                :status="row.status === 'completed' ? 'success' : undefined"
                :stroke-width="6"
              />
            </div>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              type="primary"
              link
              @click="$router.push(`/workflows/${row.id}`)"
            >
              详情
            </el-button>
          </template>
        </el-table-column>
        </el-table>
      </div>
        </el-card>
      </PageContent>
    </ContentContainer>
  </Layout>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Search,
  Calendar,
  FolderAdd,
  Clock,
  ArrowRight,
  Finished,
  Document,
  Reading,
  Collection,
  Top,
  TrendCharts,
} from '@element-plus/icons-vue'
import { useWorkflowStore, usePaperStore, useReportStore, useMemoryStore } from '@/stores'
import StatusTag from '@/components/StatusTag.vue'
import { Layout, ContentContainer, PageContent, PageHeader } from '@/components/layout'

const router = useRouter()
const workflowStore = useWorkflowStore()
const paperStore = usePaperStore()
const reportStore = useReportStore()
const memoryStore = useMemoryStore()

const workflowTotal = ref(0)
const paperTotal = ref(0)
const reportTotal = ref(0)
const memoryTotal = ref(0)

const creating = ref(false)
const createForm = reactive({
  query: '',
  year_range: '',
  max_papers: 10,
  source: 'arxiv',
})

const recentWorkflows = ref([])

const truncateId = (id) => {
  if (!id) return ''
  return id.length > 12 ? `${id.slice(0, 6)}...${id.slice(-6)}` : id
}

const getStatusType = (status) => {
  const types = {
    pending: 'info',
    running: 'warning',
    completed: 'success',
    failed: 'danger',
    cancelled: 'info',
  }
  return types[status] || 'info'
}

const createWorkflow = async () => {
  if (!createForm.query) {
    ElMessage.warning('请输入研究主题')
    return
  }

  creating.value = true
  try {
    const workflow = await workflowStore.createWorkflow(createForm)
    ElMessage.success('工作流创建成功')
    router.push(`/workflows/${workflow.id}`)
  } catch (err) {
    ElMessage.error('创建工作流失败：' + err.message)
  } finally {
    creating.value = false
  }
}

const loadStats = async () => {
  try {
    const [wfRes, paperRes, reportRes, memoryRes] = await Promise.all([
      fetch('/api/workflows?page=1&page_size=1').then((r) => r.json()),
      fetch('/api/papers?page=1&page_size=1').then((r) => r.json()),
      fetch('/api/reports?page=1&page_size=1').then((r) => r.json()),
      fetch('/api/memory?page=1&page_size=1').then((r) => r.json()),
    ])

    workflowTotal.value = wfRes.total || 0
    paperTotal.value = paperRes.total || 0
    reportTotal.value = reportRes.total || 0
    memoryTotal.value = memoryRes.total || 0
  } catch (err) {
    console.error('加载统计数据失败:', err)
  }
}

const loadRecentWorkflows = async () => {
  try {
    const res = await fetch('/api/workflows?page=1&page_size=5')
    const data = await res.json()
    recentWorkflows.value = data.items || []
  } catch (err) {
    console.error('加载最近工作流失败:', err)
  }
}

onMounted(() => {
  loadStats()
  loadRecentWorkflows()
})
</script>

<style scoped>
@import '@/styles/variables.css';

.dashboard {
  animation: fadeInUp 0.5s var(--ease-out);
}

/* =============================================
   统计卡片
   ============================================= */
.stat-card {
  background: var(--bg-primary);
  border-radius: var(--radius-xl);
  padding: var(--space-5);
  display: flex;
  align-items: center;
  gap: var(--space-4);
  border: 1px solid var(--border-primary);
  box-shadow: var(--shadow-sm);
  transition: var(--transition-base);
  cursor: pointer;
  position: relative;
  overflow: hidden;
}

.stat-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: var(--gradient-primary);
  opacity: 0;
  transition: var(--transition-base);
}

.stat-card--workflow::before { background: linear-gradient(90deg, #667eea, #764ba2); }
.stat-card--paper::before { background: linear-gradient(90deg, #10b981, #059669); }
.stat-card--report::before { background: linear-gradient(90deg, #f59e0b, #d97706); }
.stat-card--memory::before { background: linear-gradient(90deg, #3b82f6, #2563eb); }

.stat-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
  border-color: transparent;
}

.stat-card:hover::before {
  opacity: 1;
}

.stat-card-icon {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: var(--transition-base);
}

.stat-card--workflow .stat-card-icon { background: linear-gradient(135deg, #667eea1a, #764ba21a); color: #667eea; }
.stat-card--paper .stat-card-icon { background: linear-gradient(135deg, #10b9811a, #0596691a); color: #10b981; }
.stat-card--report .stat-card-icon { background: linear-gradient(135deg, #f59e0b1a, #d977061a); color: #f59e0b; }
.stat-card--memory .stat-card-icon { background: linear-gradient(135deg, #3b82f61a, #2563eb1a); color: #3b82f6; }

.stat-card:hover .stat-card-icon {
  transform: scale(1.1) rotate(5deg);
}

.stat-card-content {
  flex: 1;
  min-width: 0;
}

.stat-card-label {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  font-weight: var(--font-medium);
  display: block;
  margin-bottom: var(--space-2);
}

.stat-card-value {
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  line-height: 1;
  margin-bottom: var(--space-2);
}

.stat-card-value :deep(.el-statistic__content) {
  font-size: var(--text-3xl);
}

.stat-card-value :deep(.el-statistic__title) {
  display: none;
}

.stat-card-trend {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}

.trend-icon {
  font-size: 14px;
}

.trend-icon.up {
  color: var(--success-base);
}

/* =============================================
   创建卡片
   ============================================= */
.create-card {
  background: var(--bg-primary);
  border-radius: var(--radius-2xl);
  border: 1px solid var(--border-primary);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.create-card :deep(.el-card__header) {
  background: var(--brand-header-bg);
  border-bottom: 1px solid var(--brand-header-border);
  padding: var(--space-4) var(--space-5);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title-section {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.title-icon-wrapper {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: var(--brand-accent-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--brand-primary);
  box-shadow: inset 0 0 0 1px rgba(37, 99, 235, 0.06);
}

.card-title {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.form-hint {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  margin-left: var(--space-3);
}

.submit-btn {
  height: 44px;
  padding: 0 var(--space-6);
  border-radius: var(--radius-lg);
  font-weight: var(--font-semibold);
  box-shadow: var(--shadow-sm);
  transition: var(--transition-base);
}

.submit-btn:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.input-lg :deep(.el-input__wrapper) {
  height: 44px;
  border-radius: var(--radius-lg);
}

.input-number-full {
  width: 100%;
}

.select-full {
  width: 100%;
}

/* =============================================
   最近工作流卡片
   ============================================= */
.recent-card {
  background: var(--bg-primary);
  border-radius: var(--radius-2xl);
  border: 1px solid var(--border-primary);
  box-shadow: var(--shadow-sm);
}

.recent-card :deep(.el-card__header) {
  background: var(--brand-header-bg);
  border-bottom: 1px solid var(--brand-header-border);
  padding: var(--space-4) var(--space-5);
}

.empty-state {
  padding: var(--space-10);
  text-align: center;
}

.workflow-table {
  --el-table-border-radius: var(--radius-xl);
}

.workflow-id {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--slate-700);
  background: rgba(239, 246, 255, 0.9);
  border: 1px solid rgba(37, 99, 235, 0.14);
  padding: 2px 8px;
  border-radius: var(--radius-md);
}

.query-content {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.query-text {
  color: var(--text-primary);
  font-size: var(--text-sm);
}

.progress-cell {
  width: 120px;
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
  .stat-card {
    padding: var(--space-4);
  }

  .stat-card-icon {
    width: 48px;
    height: 48px;
  }
}
</style>
