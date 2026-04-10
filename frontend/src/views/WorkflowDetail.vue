<template>
  <Layout>
    <ContentContainer size="2xl">
      <div class="workflow-detail-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <el-page-header @back="$router.push('/workflows')">
        <template #content>
          <div class="page-header-content">
            <div class="header-main">
              <h1 class="workflow-title">工作流详情</h1>
              <div class="workflow-meta">
                <span class="workflow-id-badge">
                  <el-icon><Link /></el-icon>
                  {{ workflowId }}
                </span>
                <status-tag :status="workflow?.status" show-dot size="default" />
              </div>
            </div>
            <el-button class="page-nav-button" @click="$router.push('/dashboard')">返回仪表盘</el-button>
          </div>
        </template>
      </el-page-header>
    </div>

    <el-row :gutter="24" class="content-grid">
      <!-- 左侧主要内容 -->
      <el-col :span="16">
        <!-- 基本信息 -->
        <el-card class="info-card feature-panel feature-panel--blue">
          <template #header>
            <div class="card-header">
              <el-icon class="header-icon"><Document /></el-icon>
              <span class="card-title">基本信息</span>
            </div>
          </template>

          <el-descriptions :column="2" border class="workflow-descriptions">
            <el-descriptions-item label="研究主题" :span="2">
              <span class="description-value">{{ workflow?.query }}</span>
            </el-descriptions-item>

            <el-descriptions-item label="🔑 提炼关键词" :span="2">
              <div class="rewritten-query-container">
                <el-tag
                  v-if="workflow?.rewritten_query"
                  type="success"
                  effect="plain"
                  class="rewritten-query-tag"
                >
                  {{ workflow?.rewritten_query }}
                </el-tag>
                <span v-else class="rewritten-query-pending">
                  <el-icon class="spin"><Loading /></el-icon>
                  等待提炼...
                </span>
              </div>
            </el-descriptions-item>

            <el-descriptions-item label="年份范围">
              <span class="description-value">{{ workflow?.year_range || '不限' }}</span>
            </el-descriptions-item>

            <el-descriptions-item label="论文数量">
              <span class="description-value">{{ workflow?.max_papers }} 篇</span>
            </el-descriptions-item>

            <el-descriptions-item label="数据源">
              <span class="description-value">{{ workflow?.source }}</span>
            </el-descriptions-item>

            <el-descriptions-item label="进度">
              <div class="progress-with-value">
                <el-progress
                  :percentage="workflow?.progress || 0"
                  :stroke-width="10"
                  :show-text="false"
                  class="inline-progress"
                />
                <span class="progress-value">{{ workflow?.progress }}%</span>
              </div>
            </el-descriptions-item>

            <el-descriptions-item label="论文数">
              <span class="description-value">{{ workflow?.papers_found }} 篇</span>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>

        <!-- 阶段进度 -->
        <el-card class="stage-card feature-panel feature-panel--amber">
          <template #header>
            <div class="card-header">
              <el-icon class="header-icon"><TrendCharts /></el-icon>
              <span class="card-title">阶段进度</span>
            </div>
          </template>

          <div class="stage-progress-container">
            <div
              v-for="(stage, index) in stages"
              :key="stage.key"
              class="stage-item"
              :class="{
                'stage-active': index === currentStageIndex,
                'stage-completed': index < currentStageIndex,
              }"
            >
              <div class="stage-header">
                <div class="stage-icon-wrapper" :class="`stage-icon--${getStageColorClass(stage)}`">
                  <el-icon :size="18">
                    <component :is="stage.icon" />
                  </el-icon>
                </div>
                <span class="stage-title">{{ stage.title }}</span>
                <span class="stage-status" v-if="stage.description">
                  {{ stage.description }}
                </span>
              </div>
              <el-progress
                :percentage="getStageProgress(stage.key)"
                :status="index < currentStageIndex ? 'success' : undefined"
                :stroke-width="6"
                class="stage-progress"
              />
            </div>
          </div>
        </el-card>

        <!-- 运行日志 -->
        <el-card class="log-card feature-panel feature-panel--violet">
          <template #header>
            <div class="card-header">
              <el-icon class="header-icon"><Notebook /></el-icon>
              <span class="card-title">运行日志</span>
            </div>
          </template>

          <div class="log-container" ref="logContainerRef">
            <div v-if="logs.length === 0" class="log-empty">
              <el-empty description="暂无日志" :image-size="60" />
            </div>
            <div v-else class="log-content">
              <div v-for="(log, i) in logs" :key="i" class="log-item" :class="`log-${log.type}`">
                <span class="log-time">{{ log.time }}</span>
                <span class="log-message">{{ log.message }}</span>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧边栏 -->
      <el-col :span="8">
        <!-- 总体进度 -->
        <el-card class="progress-card feature-panel feature-panel--emerald">
          <template #header>
            <div class="card-header">
              <el-icon class="header-icon"><PieChart /></el-icon>
              <span class="card-title">总体进度</span>
            </div>
          </template>

          <div class="progress-circle-wrapper">
            <el-progress
              type="circle"
              :percentage="workflow?.progress || 0"
              :status="
                workflow?.status === 'completed'
                  ? 'success'
                  : workflow?.status === 'failed'
                  ? 'exception'
                  : undefined
              "
              :width="180"
              :stroke-width="14"
            />
          </div>

          <div class="progress-status-text">
            <status-tag :status="workflow?.status" text="状态" />
          </div>
        </el-card>

        <!-- 论文列表 -->
        <el-card class="papers-card feature-panel feature-panel--teal">
          <template #header>
            <div class="card-header">
              <el-icon class="header-icon"><Document /></el-icon>
              <span class="card-title">
                论文列表
                <span class="count-badge">{{ papers.length }}</span>
              </span>
            </div>
          </template>

          <el-scrollbar height="400px" class="papers-scroll">
            <div v-if="papers.length === 0" class="papers-empty">
              <el-empty description="暂无论文" :image-size="50" />
            </div>
            <div v-else class="papers-list">
              <div v-for="paper in papers" :key="paper.paper_id" class="paper-item">
                <div class="paper-title">{{ paper.title }}</div>
                <div class="paper-meta">
                  <el-tag
                    :type="paper.source === 'arxiv' ? 'primary' : 'success'"
                    size="small"
                    effect="light"
                  >
                    {{ paper.source }}
                  </el-tag>
                  <span v-if="paper.year" class="paper-year">{{ paper.year }}</span>
                </div>
              </div>
            </div>
          </el-scrollbar>
        </el-card>

        <!-- 操作按钮 -->
        <el-card class="actions-card feature-panel feature-panel--rose">
          <template #header>
            <div class="card-header">
              <el-icon class="header-icon"><Setting /></el-icon>
              <span class="card-title">操作</span>
            </div>
          </template>

          <div class="actions-list">
            <el-button
              v-if="workflow?.status === 'running' || workflow?.status === 'pending'"
              type="danger"
              @click="cancelWorkflow"
              block
              class="action-btn"
            >
              <el-icon><CircleClose /></el-icon>
              取消工作流
            </el-button>

            <el-button
              v-if="workflow?.status === 'completed'"
              type="primary"
              @click="viewReport"
              block
              class="action-btn"
            >
              <el-icon><Document /></el-icon>
              查看报告
            </el-button>

            <el-button
              v-if="workflow?.status === 'completed'"
              @click="downloadReport"
              block
              class="action-btn"
            >
              <el-icon><Download /></el-icon>
              下载报告
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
      </div>
    </ContentContainer>
  </Layout>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useWorkflowStore, usePaperStore } from '@/stores'
import { ElMessage } from 'element-plus'
import StatusTag from '@/components/StatusTag.vue'
import { Layout, ContentContainer } from '@/components/layout'
import {
  Search,
  Document,
  Edit,
  Checked,
  DocumentCopy,
  Link,
  TrendCharts,
  Notebook,
  PieChart,
  Setting,
  CircleClose,
  Download,
  Loading,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const workflowStore = useWorkflowStore()
const paperStore = usePaperStore()

const workflowId = route.params.id
const workflow = ref(null)
const papers = ref([])
const logs = ref([])
const eventHistory = ref([])
const currentStageIndex = ref(0)
const logContainerRef = ref(null)
const isCancelling = ref(false)  // 标记是否正在取消

const stages = reactive([
  { key: 'search', title: '文献搜索', description: '', icon: Search, color: '#409EFF' },
  { key: 'analyst', title: '文献分析', description: '', icon: Document, color: '#10b981' },
  { key: 'writer', title: '报告撰写', description: '', icon: Edit, color: '#f59e0b' },
  { key: 'reviewer', title: '质量审核', description: '', icon: Checked, color: '#64748b' },
  { key: 'editor', title: '最终编辑', description: '', icon: DocumentCopy, color: '#ef4444' },
])

let ws = null
let pollTimer = null

const getWebSocketBase = () => {
  const apiBase = import.meta.env.VITE_API_BASE_URL

  if (apiBase) {
    const httpUrl = new URL(apiBase, window.location.origin)
    httpUrl.protocol = httpUrl.protocol === 'https:' ? 'wss:' : 'ws:'
    httpUrl.pathname = ''
    return httpUrl.toString().replace(/\/$/, '')
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}`
}

const stageProgress = ref({
  search: 0,
  analyst: 0,
  writer: 0,
  reviewer: 0,
  editor: 0,
})

const getStageColorClass = (stage) => {
  const colorMap = {
    Search: 'blue',
    Document: 'green',
    Edit: 'orange',
    Checked: 'gray',
    DocumentCopy: 'red',
  }
  return colorMap[stage.icon?.name] || 'default'
}

const getStageProgress = (stageKey) => {
  return stageProgress.value[stageKey] || 0
}

const resetStageState = () => {
  Object.keys(stageProgress.value).forEach((key) => {
    stageProgress.value[key] = 0
  })
  stages.forEach((stage) => {
    stage.description = ''
  })
  currentStageIndex.value = 0
}

const normalizeEvent = (rawEvent = {}) => {
  const payload = rawEvent.data || {}
  const eventType = rawEvent.event_type || rawEvent.type || payload.event_type
  const stage = rawEvent.stage ?? payload.stage ?? null
  const status = rawEvent.status ?? payload.status ?? null
  const progress = rawEvent.progress ?? payload.progress ?? 0
  const message = rawEvent.message || payload.message || '收到工作流事件'
  const timestamp = rawEvent.timestamp || payload.timestamp || new Date().toISOString()

  return {
    id: rawEvent.id || `${eventType}-${timestamp}-${stage || 'workflow'}`,
    eventType,
    stage,
    status,
    progress,
    message,
    timestamp,
    raw: rawEvent,
  }
}

const rebuildStageStateFromEvents = (events = []) => {
  resetStageState()

  if (!events.length) {
    return
  }

  for (const event of events) {
    const { eventType, stage, status, progress, message } = event

    if (eventType === 'workflow_completed') {
      stages.forEach((item) => {
        stageProgress.value[item.key] = 100
        item.description = '已完成'
      })
      currentStageIndex.value = stages.length
      continue
    }

    if (!stage) {
      continue
    }

    const index = stages.findIndex((item) => item.key === stage)
    if (index < 0) {
      continue
    }

    if (eventType === 'stage_started') {
      stageProgress.value[stage] = 0
      stages[index].description = message || '开始执行'
      currentStageIndex.value = index
      continue
    }

    if (eventType === 'stage_completed' || status === 'completed') {
      stageProgress.value[stage] = 100
      stages[index].description = '已完成'
      currentStageIndex.value = Math.max(currentStageIndex.value, index + 1)
      continue
    }

    if (eventType === 'stage_failed' || status === 'failed') {
      stageProgress.value[stage] = progress || stageProgress.value[stage] || 0
      stages[index].description = message || '执行失败'
      currentStageIndex.value = index
      continue
    }

    if (eventType === 'stage_progress' || eventType === 'stage_started' || status === 'in_progress') {
      stageProgress.value[stage] = progress || 0
      stages[index].description = message || `${progress || 0}%`
      currentStageIndex.value = index
    }
  }
}

const formatLogTime = (timestamp) => {
  const date = timestamp ? new Date(timestamp) : new Date()
  return date.toLocaleTimeString('zh-CN')
}

const addLog = (message, type = 'info', timestamp = null, dedupeKey = null) => {
  const time = formatLogTime(timestamp)
  const key = dedupeKey || `${time}-${type}-${message}`

  if (logs.value.some((log) => log.key === key)) {
    return
  }

  logs.value.push({ key, time, message, type })
  if (logs.value.length > 100) {
    logs.value.shift()
  }

  nextTick(() => {
    if (logContainerRef.value) {
      logContainerRef.value.scrollTop = logContainerRef.value.scrollHeight
    }
  })
}

const getLogTypeFromEvent = (eventType, status) => {
  if (eventType === 'workflow_failed' || eventType === 'stage_failed' || status === 'failed') {
    return 'error'
  }
  if (eventType === 'workflow_cancelled') {
    return 'warning'
  }
  if (eventType === 'workflow_completed' || eventType === 'stage_completed' || status === 'completed') {
    return 'success'
  }
  return 'info'
}

const updateStageState = (stage, progress = 0, status = 'in_progress', description = '') => {
  const index = stages.findIndex((item) => item.key === stage)
  if (index < 0) return

  if (status === 'completed') {
    stageProgress.value[stage] = 100
    stages[index].description = description || '已完成'
    currentStageIndex.value = Math.max(currentStageIndex.value, index + 1)
    return
  }

  stageProgress.value[stage] = progress
  stages[index].description = description || `${progress}%`
  currentStageIndex.value = index
}

const syncStageStateFromWorkflow = () => {
  if (!workflow.value) return

  if (eventHistory.value.length > 0) {
    rebuildStageStateFromEvents(eventHistory.value)
    return
  }

  resetStageState()

  const activeIndex = workflow.value.current_stage
    ? stages.findIndex((stage) => stage.key === workflow.value.current_stage)
    : -1

  if (workflow.value.status === 'completed') {
    stages.forEach((stage) => {
      stageProgress.value[stage.key] = 100
      stage.description = '已完成'
    })
    currentStageIndex.value = stages.length
    return
  }

  if (activeIndex >= 0) {
    stages.forEach((stage, index) => {
      if (index < activeIndex) {
        stageProgress.value[stage.key] = 100
        stage.description = '已完成'
      } else if (index === activeIndex) {
        stageProgress.value[stage.key] = workflow.value.progress || 0
        stage.description = workflow.value.message || `${workflow.value.progress || 0}%`
      }
    })
    currentStageIndex.value = activeIndex
  }
}

const loadEventLogs = async () => {
  try {
    const res = await fetch(`/api/workflows/${workflowId}/events`)
    if (!res.ok) return

    const data = await res.json()
    const normalizedEvents = (data.items || []).map(normalizeEvent)
    eventHistory.value = normalizedEvents
    rebuildStageStateFromEvents(normalizedEvents)
    logs.value = normalizedEvents
      .filter((event) => event.eventType !== 'heartbeat' && event.eventType !== 'connected')
      .map((event) => ({
        key: event.id,
        time: formatLogTime(event.timestamp),
        message: event.message,
        type: getLogTypeFromEvent(event.eventType, event.status),
      }))

    nextTick(() => {
      if (logContainerRef.value) {
        logContainerRef.value.scrollTop = logContainerRef.value.scrollHeight
      }
    })
  } catch (err) {
    addLog(`加载日志失败：${err.message}`, 'error')
  }
}

const applyRealtimeEvent = (event) => {
  const normalizedEvent = normalizeEvent(event)
  const { eventType, stage, message, progress, status } = normalizedEvent

  eventHistory.value = [...eventHistory.value, normalizedEvent]
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
    .slice(-500)

  if (stage) {
    if (eventType === 'stage_completed') {
      updateStageState(stage, 100, 'completed', message)
    } else {
      updateStageState(stage, progress, status, message)
    }
  }

  if (eventType !== 'heartbeat' && eventType !== 'connected') {
    addLog(
      message,
      getLogTypeFromEvent(eventType, status),
      normalizedEvent.timestamp,
      normalizedEvent.id
    )
  }
}

const connectWebSocket = () => {
  const wsUrl = `${getWebSocketBase()}/ws/workflows/${workflowId}`

  ws = new WebSocket(wsUrl)

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    const eventType = data.event_type || data.type

    if (eventType === 'connected') {
      return
    } else if (eventType === 'heartbeat') {
      return
    } else {
      applyRealtimeEvent(data)
      if (eventType === 'workflow_completed') {
        loadWorkflow()
        loadPapers()
      } else if (eventType === 'workflow_failed' || eventType === 'workflow_cancelled') {
        loadWorkflow()
      } else if (eventType === 'stage_progress' || eventType === 'stage_completed') {
        loadWorkflow()
      }
    }

    if (eventType === 'workflow_completed') {
      loadWorkflow()
      loadPapers()
    }
  }

  ws.onerror = () => {
    addLog('WebSocket 连接错误', 'error')
  }

  ws.onclose = () => {
    addLog('WebSocket 连接已关闭', 'warning')
  }
}

const loadWorkflow = async () => {
  try {
    workflow.value = await workflowStore.fetchWorkflow(workflowId)
    syncStageStateFromWorkflow()
  } catch (err) {
    addLog(`加载工作流失败：${err.message}`, 'error')
  }
}

const loadPapers = async () => {
  try {
    const res = await fetch(`/api/workflows/${workflowId}/papers`)
    const data = await res.json()
    papers.value = data.items || []
  } catch (err) {
    console.error('加载论文失败:', err)
  }
}

const cancelWorkflow = async () => {
  if (!confirm('确定要取消此工作流吗？')) return

  try {
    isCancelling.value = true  // 标记正在取消
    await workflowStore.cancelWorkflow(workflowId)
    ElMessage.warning('已请求取消工作流')

    // 取消后手动更新本地状态，避免立即刷新
    workflow.value.status = 'cancelled'

    // 等待一小段时间后加载最新状态
    setTimeout(() => {
      isCancelling.value = false
      loadWorkflow()
    }, 1000)
  } catch (err) {
    isCancelling.value = false
    addLog(`取消失败：${err.message}`, 'error')
  }
}

const viewReport = () => {
  window.open(`/reports/${workflowId}`, '_blank')
}

const downloadReport = async () => {
  try {
    await fetch(`/api/reports/${workflowId}/download?format=markdown`)
    ElMessage.success('下载已开始')
  } catch (err) {
    ElMessage.error('下载失败')
  }
}

const startPolling = () => {
  pollTimer = setInterval(() => {
    // 正在取消时不轮询，避免状态冲突
    if (isCancelling.value) return

    if (workflow.value?.status === 'running' || workflow.value?.status === 'pending') {
      loadWorkflow()
    }
  }, 5000)
}

const initializePage = async () => {
  addLog('正在加载工作流...', 'info')
  await loadWorkflow()
  await loadPapers()
  await loadEventLogs()

  try {
    connectWebSocket()
  } catch (err) {
    addLog('WebSocket 不可用，使用轮询模式', 'warning')
  }

  startPolling()
}

onMounted(() => {
  initializePage()
})

onUnmounted(() => {
  if (ws) ws.close()
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
@import '@/styles/variables.css';

.workflow-detail-page {
  animation: fadeInUp 0.5s var(--ease-out);
}

/* =============================================
   页面头部
   ============================================= */
.page-header {
  margin-bottom: var(--space-6);
}

.page-header :deep(.el-page-header__header) {
  padding: var(--space-4) 0;
  border-bottom: 1px solid var(--border-secondary);
}

.page-header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-4);
}

.header-main {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  min-width: 0;
}

.workflow-title {
  font-size: var(--text-xl);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin: 0;
}

.workflow-meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.workflow-id-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--slate-700);
  background: rgba(239, 246, 255, 0.9);
  border: 1px solid rgba(37, 99, 235, 0.14);
  padding: 4px 10px;
  border-radius: var(--radius-md);
}

/* =============================================
   内容网格
   ============================================= */
.content-grid {
  margin: 0;
}

/* =============================================
   通用卡片样式
   ============================================= */
.info-card,
.stage-card,
.log-card,
.progress-card,
.papers-card,
.actions-card {
  margin-bottom: var(--space-4);
  border-radius: var(--radius-2xl);
  border: 1px solid var(--border-primary);
  box-shadow: var(--shadow-sm);
  transition: var(--transition-base);
}

.card-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.header-icon {
  color: var(--brand-primary);
  font-size: 18px;
}

.card-title {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

/* =============================================
   基本信息卡片
   ============================================= */
.workflow-descriptions {
  border-radius: var(--radius-lg);
}

.workflow-descriptions :deep(.el-descriptions__header) {
  margin-bottom: var(--space-4);
}

.workflow-descriptions :deep(.el-descriptions__label) {
  font-weight: var(--font-medium);
  color: var(--text-secondary);
  background-color: var(--bg-secondary);
  border-radius: var(--radius-md);
  border-color: var(--border-secondary);
}

.workflow-descriptions :deep(.el-descriptions__content) {
  border-color: var(--border-secondary);
}

.description-value {
  color: var(--text-primary);
  font-weight: var(--font-medium);
}

/* 提炼关键词 */
.rewritten-query-container {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.rewritten-query-tag {
  font-size: var(--text-sm);
  padding: 6px 12px;
  font-weight: var(--font-medium);
  border-radius: var(--radius-lg);
}

.rewritten-query-pending {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  color: var(--text-tertiary);
  font-size: var(--text-sm);
  font-style: italic;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  100% {
    transform: rotate(360deg);
  }
}

/* 进度条 */
.progress-with-value {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.inline-progress {
  flex: 1;
}

.progress-value {
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  min-width: 45px;
  text-align: right;
}

/* =============================================
   阶段进度卡片
   ============================================= */
.stage-progress-container {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.stage-item {
  padding: var(--space-3) var(--space-4);
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
  transition: var(--transition-base);
  border: 1px solid transparent;
}

.stage-item.stage-active {
  background: var(--info-bg);
  border-color: var(--brand-primary);
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.1);
}

.stage-item.stage-completed {
  background: var(--success-bg);
  border-color: var(--success-base);
}

.stage-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}

.stage-icon-wrapper {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stage-icon--blue { background: var(--info-light); color: var(--info-dark); }
.stage-icon--green { background: var(--success-light); color: var(--success-dark); }
.stage-icon--orange { background: var(--warning-light); color: var(--warning-dark); }
.stage-icon--gray { background: var(--slate-100); color: var(--slate-600); }
.stage-icon--red { background: var(--danger-light); color: var(--danger-dark); }

.stage-title {
  font-weight: var(--font-semibold);
  font-size: var(--text-sm);
  color: var(--text-primary);
}

.stage-status {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  margin-left: auto;
  font-weight: var(--font-medium);
}

.stage-item.stage-active .stage-status {
  color: var(--brand-primary);
}

.stage-item.stage-completed .stage-status {
  color: var(--success-base);
}

.stage-progress {
  --el-progress-stroke-width: 6;
}

/* =============================================
   日志卡片
   ============================================= */
.log-card :deep(.el-card__body) {
  padding: 0;
}

.log-container {
  max-height: 400px;
  overflow-y: auto;
  background: var(--slate-900);
  border-radius: 0 0 var(--radius-2xl) var(--radius-2xl);
  padding: var(--space-4);
}

.log-content {
  display: flex;
  flex-direction: column;
}

.log-item {
  display: flex;
  gap: var(--space-3);
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--slate-800);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
}

.log-item:last-child {
  border-bottom: none;
}

.log-time {
  color: var(--slate-500);
  white-space: nowrap;
  flex-shrink: 0;
}

.log-message {
  flex: 1;
  word-break: break-all;
  color: var(--slate-300);
}

.log-item.log-success .log-message { color: var(--success-base); }
.log-item.log-error .log-message { color: var(--danger-base); }
.log-item.log-warning .log-message { color: var(--warning-base); }

.log-empty {
  padding: var(--space-8);
  text-align: center;
}

/* =============================================
   进度卡片
   ============================================= */
.progress-circle-wrapper {
  display: flex;
  justify-content: center;
  padding: var(--space-4) 0;
}

.progress-status-text {
  text-align: center;
  margin-top: var(--space-3);
}

/* =============================================
   论文卡片
   ============================================= */
.count-badge {
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  color: var(--text-secondary);
  background: var(--bg-tertiary);
  padding: 2px 8px;
  border-radius: var(--radius-full);
  margin-left: var(--space-2);
}

.papers-scroll :deep(.el-scrollbar__body) {
  padding: var(--space-2);
}

.papers-empty {
  padding: var(--space-6);
  text-align: center;
}

.papers-list {
  display: flex;
  flex-direction: column;
}

.paper-item {
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--border-secondary);
}

.paper-item:last-child {
  border-bottom: none;
}

.paper-title {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-primary);
  margin-bottom: var(--space-2);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: var(--leading-relaxed);
}

.paper-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.paper-year {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}

/* =============================================
   操作卡片
   ============================================= */
.actions-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.action-btn {
  height: 40px;
  border-radius: var(--radius-lg);
  font-weight: var(--font-medium);
  transition: var(--transition-base);
}

.action-btn:hover {
  transform: translateY(-1px);
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
@media (max-width: 992px) {
  .content-grid {
    flex-direction: column;
  }
}
</style>
