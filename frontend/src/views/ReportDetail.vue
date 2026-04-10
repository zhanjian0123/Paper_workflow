<template>
  <Layout>
    <ContentContainer size="xl">
      <div class="report-detail-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <el-page-header @back="$router.push('/reports')">
        <template #content>
          <div class="page-header-content">
            <div class="header-main">
              <h1 class="report-title">{{ report?.title || '加载中...' }}</h1>
              <div class="report-meta" v-if="report">
                <span class="meta-item">
                  <el-icon><Document /></el-icon>
                  {{ formatNumber(report.word_count) }} 字
                </span>
                <span class="meta-item">
                  <el-icon><Collection /></el-icon>
                  {{ report.paper_count }} 篇论文
                </span>
                <span class="meta-item">
                  <el-icon><Calendar /></el-icon>
                  {{ formatDate(report.created_at) }}
                </span>
              </div>
            </div>
            <el-button class="page-nav-button" @click="$router.push('/dashboard')">返回仪表盘</el-button>
          </div>
        </template>
      </el-page-header>
    </div>

    <!-- 报告内容卡片 -->
    <el-card class="report-card feature-panel feature-panel--blue">
      <template #header>
        <div class="card-header">
          <div class="card-title-section">
            <el-icon class="header-icon"><Reading /></el-icon>
            <span class="card-title">报告内容</span>
          </div>
          <div class="card-actions">
            <el-button @click="downloadReport('markdown')" class="action-btn">
              <el-icon><Download /></el-icon>
              下载 Markdown
            </el-button>
            <el-button disabled class="action-btn" title="即将推出">
              <el-icon><Document /></el-icon>
              导出 PDF
              <el-tag size="small" type="info" effect="plain" style="margin-left: 6px">
                即将推出
              </el-tag>
            </el-button>
          </div>
        </div>
      </template>

      <!-- 加载状态 -->
      <div v-if="loading" class="loading-container">
        <el-skeleton :rows="15" animated />
      </div>

      <!-- 错误状态 -->
      <div v-else-if="error" class="error-container">
        <el-result icon="error" :title="error" subtitle="请刷新页面重试">
          <template #extra>
            <el-button type="primary" @click="loadReport">刷新页面</el-button>
          </template>
        </el-result>
      </div>

      <!-- 报告内容 -->
      <div v-else class="markdown-body" v-html="renderedMarkdown"></div>
    </el-card>
      </div>
    </ContentContainer>
  </Layout>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useReportStore } from '@/stores'
import MarkdownIt from 'markdown-it'
import { Layout, ContentContainer } from '@/components/layout'
import {
  Document,
  Collection,
  Calendar,
  Reading,
  Download,
} from '@element-plus/icons-vue'

const route = useRoute()
const reportStore = useReportStore()

const report = ref(null)
const loading = ref(false)
const error = ref(null)

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
  breaks: true,
})

// 自定义渲染规则 - 美化输出
md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  tokens[idx].attrPush(['target', '_blank'])
  tokens[idx].attrPush(['rel', 'noopener noreferrer'])
  tokens[idx].attrPush(['class', 'markdown-link'])
  return self.renderToken(tokens, idx, options)
}

md.renderer.rules.heading_open = (tokens, idx, options, env, self) => {
  const level = parseInt(tokens[idx].tag.slice(1))
  tokens[idx].attrPush(['class', `markdown-heading heading-${level}`])
  return self.renderToken(tokens, idx, options)
}

md.renderer.rules.code_inline = (tokens, idx, options, env, self) => {
  const token = tokens[idx]
  return `<code class="markdown-code-inline">${token.content}</code>`
}

md.renderer.rules.fence = (tokens, idx, options, env, self) => {
  const token = tokens[idx]
  const info = token.info ? token.info.trim() : ''
  const langClass = info ? `language-${info}` : ''
  return `<pre class="markdown-code-block"><code class="${langClass}">${md.utils.escapeHtml(token.content)}</code></pre>`
}

md.renderer.rules.blockquote_open = (tokens, idx, options, env, self) => {
  tokens[idx].attrPush(['class', 'markdown-blockquote'])
  return self.renderToken(tokens, idx, options)
}

md.renderer.rules.table_open = (tokens, idx, options, env, self) => {
  tokens[idx].attrPush(['class', 'markdown-table'])
  return self.renderToken(tokens, idx, options)
}

const renderedMarkdown = computed(() => {
  if (!report.value?.content_markdown) return ''
  return md.render(report.value.content_markdown)
})

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
  const days = Math.floor(diff / 86400000)

  if (days < 1) return '今天'
  if (days < 7) return `${days} 天前`
  return date.toLocaleDateString('zh-CN')
}

const downloadReport = async (format) => {
  try {
    const reportId = report.value?.report_id
    if (!reportId) {
      throw new Error('报告尚未加载完成')
    }
    await reportStore.downloadReport(reportId, format)
    ElMessage.success('下载已开始')
  } catch (err) {
    ElMessage.error('下载失败：' + err.message)
  }
}

const loadReport = async () => {
  loading.value = true
  error.value = null
  try {
    const workflowId = route.params.id
    const res = await fetch(`/api/workflows/${workflowId}/report`)
    if (res.ok) {
      report.value = await res.json()
    } else {
      error.value = '报告不存在或尚未生成'
    }
  } catch (err) {
    error.value = '加载报告失败：' + err.message
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadReport()
})
</script>

<style scoped>
@import '@/styles/variables.css';

.report-detail-page {
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
  flex-direction: column;
  gap: var(--space-2);
}

.report-title {
  font-size: var(--text-xl);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin: 0;
  line-height: var(--leading-tight);
}

.report-meta {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-sm);
  color: var(--text-secondary);
  background: var(--bg-tertiary);
  padding: 4px 10px;
  border-radius: var(--radius-full);
  font-weight: var(--font-medium);
}

.meta-item .el-icon {
  color: var(--brand-primary);
}

/* =============================================
   报告内容卡片
   ============================================= */
.report-card {
  border-radius: var(--radius-2xl);
  border: 1px solid var(--border-primary);
  box-shadow: var(--shadow-sm);
}

.report-card :deep(.el-card__header) {
  background: var(--brand-header-bg);
  border-bottom: 1px solid var(--brand-header-border);
  padding: var(--space-4) var(--space-5);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.card-title-section {
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

.card-actions {
  display: flex;
  gap: var(--space-2);
}

.action-btn {
  border-radius: var(--radius-lg);
  font-weight: var(--font-medium);
  transition: var(--transition-base);
}

.action-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

/* =============================================
   加载/错误状态
   ============================================= */
.loading-container,
.error-container {
  padding: var(--space-10);
}

/* =============================================
   Markdown 内容样式
   ============================================= */
.markdown-body {
  padding: var(--space-2) var(--space-1);
  line-height: var(--leading-relaxed);
  color: var(--text-primary);
}

/* 标题样式 */
.markdown-heading {
  font-weight: var(--font-semibold);
  letter-spacing: var(--tracking-tight);
  margin: var(--space-8) 0 var(--space-4);
  color: var(--text-primary);
  scroll-margin-top: var(--space-20);
}

.heading-1 {
  font-size: var(--text-3xl);
  padding-bottom: var(--space-3);
  border-bottom: 2px solid var(--border-primary);
}

.heading-2 {
  font-size: var(--text-2xl);
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--border-secondary);
}

.heading-3 {
  font-size: var(--text-xl);
}

.heading-4 {
  font-size: var(--text-lg);
}

.heading-5 {
  font-size: var(--text-base);
}

.heading-6 {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

/* 段落 */
.markdown-body :deep(p) {
  margin: var(--space-4) 0;
  text-align: justify;
}

/* 链接 */
.markdown-link {
  color: var(--brand-primary);
  text-decoration: none;
  border-bottom: 1px solid transparent;
  transition: var(--transition-base);
}

.markdown-link:hover {
  color: var(--brand-primary-hover);
  border-bottom-color: var(--brand-primary);
}

/* 行内代码 */
.markdown-code-inline {
  font-family: var(--font-mono);
  font-size: 0.9em;
  background: var(--bg-tertiary);
  padding: 2px 6px;
  border-radius: var(--radius-md);
  color: var(--danger-base);
  border: 1px solid var(--border-secondary);
}

/* 代码块 */
.markdown-code-block {
  background: var(--slate-900) !important;
  color: var(--slate-100);
  padding: var(--space-5);
  border-radius: var(--radius-xl);
  overflow-x: auto;
  margin: var(--space-5) 0;
  border: 1px solid var(--slate-800);
  box-shadow: var(--shadow-inset);
}

.markdown-code-block code {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  line-height: var(--leading-relaxed);
  background: none;
  padding: 0;
  color: inherit;
}

/* 引用 */
.markdown-blockquote {
  margin: var(--space-5) 0;
  padding: var(--space-4) var(--space-5);
  background: var(--bg-secondary);
  border-left: 4px solid var(--brand-primary);
  border-radius: 0 var(--radius-lg) var(--radius-lg) 0;
  color: var(--text-secondary);
  font-style: italic;
}

.markdown-blockquote p {
  margin: 0;
}

/* 列表 */
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: var(--space-4) 0;
  padding-left: var(--space-6);
}

.markdown-body :deep(li) {
  margin: var(--space-2) 0;
  line-height: var(--leading-relaxed);
}

.markdown-body :deep(ul) {
  list-style-type: disc;
}

.markdown-body :deep(ol) {
  list-style-type: decimal;
}

.markdown-body :deep(li::marker) {
  color: var(--brand-primary);
}

/* 表格 */
.markdown-table {
  width: 100%;
  border-collapse: collapse;
  margin: var(--space-5) 0;
  border-radius: var(--radius-lg);
  overflow: hidden;
  box-shadow: var(--shadow-sm);
}

.markdown-table th {
  background: var(--bg-tertiary);
  font-weight: var(--font-semibold);
  text-align: left;
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--border-secondary);
  color: var(--text-primary);
}

.markdown-table td {
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--border-secondary);
  background: var(--bg-primary);
}

.markdown-table tr:nth-child(even) td {
  background: var(--bg-secondary);
}

.markdown-table tr:hover td {
  background: var(--bg-tertiary);
}

/* 图片 */
.markdown-body :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-md);
  margin: var(--space-5) 0;
}

/* 分隔线 */
.markdown-body :deep(hr) {
  border: none;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    var(--border-primary),
    transparent
  );
  margin: var(--space-8) 0;
}

/* 强调文本 */
.markdown-body :deep(strong) {
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.markdown-body :deep(em) {
  font-style: italic;
  color: var(--text-secondary);
}

/* 高亮文本 */
.markdown-body :deep(mark) {
  background: var(--warning-light);
  color: var(--warning-dark);
  padding: 2px 6px;
  border-radius: var(--radius-md);
}

/* 任务列表 */
.markdown-body :deep(.task-list-item) {
  list-style: none;
  padding-left: 0;
}

/* 脚注 */
.markdown-body :deep(.footnote-ref) {
  color: var(--brand-primary);
  font-size: var(--text-xs);
  vertical-align: super;
}

/* 摘要/目录 */
.markdown-body :deep(.table-of-contents) {
  background: var(--bg-secondary);
  padding: var(--space-5);
  border-radius: var(--radius-xl);
  border: 1px solid var(--border-primary);
  margin: var(--space-6) 0;
}

/* =============================================
   打印样式
   ============================================= */
@media print {
  .report-card {
    box-shadow: none;
    border: none;
  }

  .card-header {
    display: none;
  }

  .markdown-body {
    padding: 0;
  }

  .markdown-code-block {
    background: #f5f5f5 !important;
    color: #333;
    border: 1px solid #ddd;
  }
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
  .card-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .card-actions {
    width: 100%;
    flex-direction: column;
  }

  .action-btn {
    width: 100%;
  }

  .report-meta {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-2);
  }
}
</style>
