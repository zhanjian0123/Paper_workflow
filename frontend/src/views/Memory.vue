<template>
  <Layout>
    <ContentContainer size="2xl">
      <PageContent spacing="loose" class="memory-page">
        <PageHeader
          title="长期记忆"
          subtitle="管理系统的长期记忆和知识库"
        >
          <template #actions>
            <el-button class="page-nav-button" @click="$router.push('/dashboard')">返回仪表盘</el-button>
            <el-button type="primary" @click="showCreateDialog = true">
              <el-icon><Plus /></el-icon>
              新建记忆
            </el-button>
          </template>
        </PageHeader>

        <!-- 统计卡片 -->
        <el-row :gutter="16" class="stats-row">
      <el-col :xs="12" :sm="6">
        <div class="stat-card stat-card--user">
          <div class="stat-card-icon">
            <el-icon :size="24"><User /></el-icon>
          </div>
          <div class="stat-card-content">
            <span class="stat-card-label">用户记忆</span>
            <div class="stat-card-value">{{ byType.user || 0 }}</div>
            <span class="stat-card-unit">条</span>
          </div>
        </div>
      </el-col>

      <el-col :xs="12" :sm="6">
        <div class="stat-card stat-card--feedback">
          <div class="stat-card-icon">
            <el-icon :size="24"><ChatDotRound /></el-icon>
          </div>
          <div class="stat-card-content">
            <span class="stat-card-label">反馈记忆</span>
            <div class="stat-card-value">{{ byType.feedback || 0 }}</div>
            <span class="stat-card-unit">条</span>
          </div>
        </div>
      </el-col>

      <el-col :xs="12" :sm="6">
        <div class="stat-card stat-card--project">
          <div class="stat-card-icon">
            <el-icon :size="24"><Folder /></el-icon>
          </div>
          <div class="stat-card-content">
            <span class="stat-card-label">项目记忆</span>
            <div class="stat-card-value">{{ byType.project || 0 }}</div>
            <span class="stat-card-unit">条</span>
          </div>
        </div>
      </el-col>

      <el-col :xs="12" :sm="6">
        <div class="stat-card stat-card--reference">
          <div class="stat-card-icon">
            <el-icon :size="24"><Link /></el-icon>
          </div>
          <div class="stat-card-content">
            <span class="stat-card-label">参考记忆</span>
            <div class="stat-card-value">{{ byType.reference || 0 }}</div>
            <span class="stat-card-unit">条</span>
          </div>
        </div>
      </el-col>
        </el-row>

        <!-- 操作栏 -->
        <el-card class="action-card feature-panel feature-panel--amber">
      <div class="action-content">
        <div class="action-text">
          <el-icon class="action-icon"><Delete /></el-icon>
          <span>清理过期和过时的记忆，释放存储空间</span>
        </div>
        <el-button type="warning" @click="cleanup">
          <el-icon><Delete /></el-icon>
          清理记忆
        </el-button>
      </div>
        </el-card>

        <!-- 类型标签 -->
        <el-tabs v-model="activeType" @tab-change="loadMemories" class="memory-tabs">
      <el-tab-pane label="全部" name="" />
      <el-tab-pane label="用户记忆" name="user" />
      <el-tab-pane label="反馈记忆" name="feedback" />
      <el-tab-pane label="项目记忆" name="project" />
      <el-tab-pane label="参考记忆" name="reference" />
        </el-tabs>

        <!-- 记忆列表 -->
        <el-card class="table-card feature-panel feature-panel--violet">
      <div class="table-shell table-shell--wide">
      <el-table
        :data="memories"
        v-loading="loading"
        style="width: 100%"
        class="memory-table"
      >
        <el-table-column prop="memory_type" label="类型" width="120">
          <template #default="{ row }">
            <span :class="['type-badge', `type-${row.memory_type}`]">
              {{ getTypeLabel(row.memory_type) }}
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="name" label="名称" min-width="200">
          <template #default="{ row }">
            <span class="memory-name">{{ row.name }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="description" label="描述" min-width="350">
          <template #default="{ row }">
            <div class="description-text">{{ row.description }}</div>
          </template>
        </el-table-column>

        <el-table-column label="状态" width="130">
          <template #default="{ row }">
            <status-tag
              v-if="row.is_expired"
              status="failed"
              text="已过期"
              size="small"
            />
            <status-tag
              v-else-if="row.is_stale"
              status="warning"
              :text="`过时 (${row.stale_days}天)`"
              size="small"
            />
            <status-tag v-else status="success" text="正常" size="small" show-dot />
          </template>
        </el-table-column>

        <el-table-column prop="updated_at" label="更新时间" width="170">
          <template #default="{ row }">
            <span class="time-text">{{ formatDate(row.updated_at) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              type="danger"
              link
              @click="deleteMemory(row.id)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      </div>
        </el-card>

        <!-- 创建对话框 -->
        <el-dialog
      v-model="showCreateDialog"
      title="创建记忆"
      width="600px"
      class="memory-dialog"
      destroy-on-close
    >
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="类型" required>
          <el-select v-model="createForm.memory_type" class="select-full">
            <el-option label="用户记忆" value="user" />
            <el-option label="反馈记忆" value="feedback" />
            <el-option label="项目记忆" value="project" />
            <el-option label="参考记忆" value="reference" />
          </el-select>
        </el-form-item>

        <el-form-item label="名称" required>
          <el-input
            v-model="createForm.name"
            placeholder="简短标题，例如：testing-preference"
            class="input-lg"
          />
        </el-form-item>

        <el-form-item label="描述" required>
          <el-input
            v-model="createForm.description"
            type="textarea"
            :rows="4"
            placeholder="详细描述记忆内容（至少 50 字符）"
            class="textarea-lg"
          />
        </el-form-item>

        <el-form-item label="标签">
          <el-input
            v-model="tagsInput"
            placeholder="逗号分隔，例如：testing, preference"
            class="input-lg"
          />
        </el-form-item>

        <el-form-item label="过期天数">
          <el-input-number
            v-model="createForm.expires_days"
            :min="1"
            :max="365"
            :disabled="createForm.memory_type !== 'project'"
          />
          <span class="hint">仅项目记忆可设置过期时间</span>
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="showCreateDialog = false">取消</el-button>
          <el-button type="primary" @click="createMemory" :loading="creating">
            创建
          </el-button>
        </div>
      </template>
        </el-dialog>
      </PageContent>
    </ContentContainer>
  </Layout>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, User, ChatDotRound, Folder, Link, Delete } from '@element-plus/icons-vue'
import { useMemoryStore } from '@/stores'
import StatusTag from '@/components/StatusTag.vue'
import { Layout, ContentContainer, PageContent, PageHeader } from '@/components/layout'

const memoryStore = useMemoryStore()

const memories = ref([])
const loading = ref(false)
const byType = ref({})
const activeType = ref('')
const showCreateDialog = ref(false)
const creating = ref(false)
const tagsInput = ref('')

const createForm = reactive({
  memory_type: 'user',
  name: '',
  description: '',
  expires_days: null,
})

const typeLabels = {
  user: '用户',
  feedback: '反馈',
  project: '项目',
  reference: '参考',
}

const getTypeLabel = (type) => typeLabels[type] || type

const getTypeBadgeType = (type) => {
  const types = {
    user: 'type-user',
    feedback: 'type-feedback',
    project: 'type-project',
    reference: 'type-reference',
  }
  return types[type] || ''
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

const loadMemories = async () => {
  loading.value = true
  try {
    await memoryStore.fetchMemories({ type_filter: activeType.value || undefined })
    memories.value = memoryStore.memories
    byType.value = memoryStore.byType
  } finally {
    loading.value = false
  }
}

const deleteMemory = async (id) => {
  if (!confirm('确定要删除此记忆吗？')) return
  try {
    await memoryStore.deleteMemory(id)
    await loadMemories()
    ElMessage.success('删除成功')
  } catch (err) {
    ElMessage.error('删除失败：' + err.message)
  }
}

const createMemory = async () => {
  if (!createForm.name || !createForm.description) {
    ElMessage.warning('请填写名称和描述')
    return
  }
  if (createForm.description.length < 50) {
    ElMessage.warning('描述至少需要 50 字符')
    return
  }

  creating.value = true
  try {
    const data = {
      ...createForm,
      tags: tagsInput.value ? tagsInput.value.split(',').map((t) => t.trim()) : undefined,
    }
    await memoryStore.createMemory(data)
    showCreateDialog.value = false
    ElMessage.success('创建成功')
    // 重置表单
    createForm.memory_type = 'user'
    createForm.name = ''
    createForm.description = ''
    createForm.expires_days = null
    tagsInput.value = ''
    await loadMemories()
  } catch (err) {
    ElMessage.error('创建失败：' + err.message)
  } finally {
    creating.value = false
  }
}

const cleanup = async () => {
  if (!confirm('确定要清理过期和过时的记忆吗？此操作不可恢复。')) return
  try {
    const result = await memoryStore.cleanup()
    ElMessage.success(`清理完成：过期 ${result.expired} 条，过时 ${result.stale} 条`)
    await loadMemories()
  } catch (err) {
    ElMessage.error('清理失败：' + err.message)
  }
}

onMounted(() => {
  loadMemories()
})
</script>

<style scoped>
@import '@/styles/variables.css';

.memory-page {
  animation: fadeInUp 0.5s var(--ease-out);
}

/* =============================================
   统计卡片行
   ============================================= */
.stat-card {
  background: var(--bg-primary);
  border-radius: var(--radius-xl);
  padding: var(--space-4);
  display: flex;
  align-items: center;
  gap: var(--space-3);
  border: 1px solid var(--border-primary);
  box-shadow: var(--shadow-sm);
  transition: var(--transition-base);
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

.stat-card--user::before { background: linear-gradient(90deg, #3b82f6, #2563eb); }
.stat-card--feedback::before { background: linear-gradient(90deg, #10b981, #059669); }
.stat-card--project::before { background: linear-gradient(90deg, #f59e0b, #d97706); }
.stat-card--reference::before { background: linear-gradient(90deg, #8b5cf6, #7c3aed); }

.stat-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
  border-color: transparent;
}

.stat-card:hover::before {
  opacity: 1;
}

.stat-card-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: var(--transition-base);
}

.stat-card--user .stat-card-icon { background: var(--info-light); color: var(--info-dark); }
.stat-card--feedback .stat-card-icon { background: var(--success-light); color: var(--success-dark); }
.stat-card--project .stat-card-icon { background: var(--warning-light); color: var(--warning-dark); }
.stat-card--reference .stat-card-icon { background: var(--slate-100); color: var(--slate-600); }

.stat-card:hover .stat-card-icon {
  transform: scale(1.1) rotate(5deg);
}

.stat-card-content {
  flex: 1;
  display: flex;
  align-items: baseline;
  gap: var(--space-1);
}

.stat-card-label {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  font-weight: var(--font-medium);
}

.stat-card-value {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
}

.stat-card-unit {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
}

/* =============================================
   操作卡片
   ============================================= */
.action-card {
  background: var(--bg-primary);
  border-radius: var(--radius-xl);
  border: 1px solid var(--border-primary);
  box-shadow: var(--shadow-sm);
}

.action-card :deep(.el-card__body) {
  padding: var(--space-4) var(--space-5);
}

.action-card :deep(.el-card__header) {
  background: var(--brand-header-bg);
  border-bottom: 1px solid var(--brand-header-border);
}

.action-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.action-text {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.action-icon {
  color: var(--warning-base);
  font-size: 20px;
}

/* =============================================
   标签页
   ============================================= */
.memory-tabs {
  margin-bottom: var(--space-4);
  background: var(--bg-primary);
  padding: var(--space-1);
  border-radius: var(--radius-full);
  display: inline-flex;
}

.memory-tabs :deep(.el-tabs__item) {
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-full);
  transition: var(--transition-base);
}

.memory-tabs :deep(.el-tabs__item.is-active) {
  background: var(--brand-primary);
  color: white;
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

.table-card :deep(.el-card__header) {
  background: var(--brand-header-bg);
  border-bottom: 1px solid var(--brand-header-border);
}

.table-card :deep(.el-card__body) {
  padding: var(--space-5);
}

.memory-table {
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.memory-table :deep(.el-table__header th) {
  background-color: var(--brand-table-header);
  color: var(--slate-700);
  font-weight: var(--font-semibold);
  font-size: var(--text-sm);
  padding: 12px 16px;
  border-bottom: 1px solid var(--brand-header-border);
}

.memory-table :deep(.el-table__body td) {
  padding: 16px;
  border-bottom-color: var(--border-secondary);
}

.memory-table :deep(.el-table__row:hover) {
  background-color: var(--brand-table-row-hover);
}

/* 类型徽章 */
.type-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
}

.type-user {
  background: var(--info-light);
  color: var(--info-dark);
}

.type-feedback {
  background: var(--success-light);
  color: var(--success-dark);
}

.type-project {
  background: var(--warning-light);
  color: var(--warning-dark);
}

.type-reference {
  background: var(--slate-100);
  color: var(--slate-600);
}

/* 记忆名称 */
.memory-name {
  font-weight: var(--font-medium);
  color: var(--text-primary);
  font-size: var(--text-sm);
}

/* 描述文本 */
.description-text {
  color: var(--text-secondary);
  font-size: var(--text-sm);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: var(--leading-relaxed);
}

/* 时间文本 */
.time-text {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
}

/* =============================================
   对话框
   ============================================= */
.memory-dialog :deep(.el-dialog) {
  border-radius: var(--radius-2xl);
}

.memory-dialog :deep(.el-dialog__header) {
  padding: var(--space-5) var(--space-6);
  border-bottom: 1px solid var(--border-secondary);
}

.memory-dialog :deep(.el-dialog__title) {
  font-weight: var(--font-semibold);
  font-size: var(--text-xl);
}

.memory-dialog :deep(.el-dialog__body) {
  padding: var(--space-6);
}

.select-full,
.input-lg,
.textarea-lg {
  width: 100%;
}

.input-lg :deep(.el-input__wrapper) {
  border-radius: var(--radius-lg);
}

.textarea-lg :deep(.el-textarea__inner) {
  border-radius: var(--radius-lg);
}

.hint {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  margin-left: var(--space-2);
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
}

/* 输入框样式 */
.input-lg :deep(.el-input__wrapper) {
  height: 40px;
  border-radius: var(--radius-lg);
}

.textarea-lg :deep(.el-textarea__inner) {
  border-radius: var(--radius-lg);
  resize: vertical;
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
</style>
