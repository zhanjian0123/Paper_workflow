import { defineStore } from 'pinia'
import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

const getWebSocketBase = () => {
  if (import.meta.env.VITE_API_BASE_URL) {
    const httpUrl = new URL(import.meta.env.VITE_API_BASE_URL, window.location.origin)
    httpUrl.protocol = httpUrl.protocol === 'https:' ? 'wss:' : 'ws:'
    httpUrl.pathname = ''
    return httpUrl.toString().replace(/\/$/, '')
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}`
}

// 创建 axios 实例
const api = axios.create({
  baseURL: API_BASE,
  timeout: 60000,
})

// 工作流 Store
export const useWorkflowStore = defineStore('workflow', {
  state: () => ({
    workflows: [],
    currentWorkflow: null,
    loading: false,
    error: null,
    total: 0,
    page: 1,
    pageSize: 20,
  }),

  getters: {
    workflowById: (state) => (id) => {
      return state.workflows.find((w) => w.id === id) || state.currentWorkflow
    },
  },

  actions: {
    async fetchWorkflows(params = {}) {
      this.loading = true
      this.error = null
      try {
        this.page = params.page ?? this.page
        this.pageSize = params.page_size ?? this.pageSize
        const res = await api.get('/workflows', {
          params: { ...params, page: this.page, page_size: this.pageSize },
        })
        this.workflows = res.data.items
        this.total = res.data.total
      } catch (err) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },

    async fetchWorkflow(id) {
      this.loading = true
      try {
        const res = await api.get(`/workflows/${id}`)
        this.currentWorkflow = res.data
        return res.data
      } catch (err) {
        this.error = err.message
        throw err
      } finally {
        this.loading = false
      }
    },

    async createWorkflow(data) {
      const payload = {
        ...data,
        year_range: data?.year_range?.trim() ? data.year_range.trim() : null,
      }
      const res = await api.post('/workflows', payload)
      return res.data
    },

    async cancelWorkflow(id, reason) {
      const res = await api.post(`/workflows/${id}/cancel`, { reason })
      return res.data
    },

    async batchDeleteWorkflows(workflowIds) {
      const res = await api.post('/workflows/batch-delete', {
        workflow_ids: workflowIds,
      })
      return res.data
    },

    subscribeWorkflow(id, onEvent) {
      const ws = new WebSocket(`${getWebSocketBase()}/ws/workflows/${id}`)

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data)
        onEvent(data)
      }

      ws.onerror = (err) => {
        console.error('WebSocket error:', err)
      }

      return ws
    },
  },
})

// 论文 Store
export const usePaperStore = defineStore('paper', {
  state: () => ({
    papers: [],
    total: 0,
    page: 1,
    pageSize: 20,
    loading: false,
  }),

  actions: {
    async fetchPapers(params = {}) {
      this.loading = true
      try {
        this.page = params.page ?? this.page
        this.pageSize = params.page_size ?? this.pageSize
        const res = await api.get('/papers', {
          params: { ...params, page: this.page, page_size: this.pageSize },
        })
        this.papers = res.data.items
        this.total = res.data.total
      } finally {
        this.loading = false
      }
    },

    async downloadPdf(paperId) {
      const res = await api.get(`/papers/${paperId}/pdf`, {
        responseType: 'blob',
      })
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const link = document.createElement('a')
      link.href = url
      link.download = `${paperId}.pdf`
      link.click()
      window.URL.revokeObjectURL(url)
    },

    async batchDownload(paperIds) {
      const res = await api.post(
        '/papers/batch-download',
        { paper_ids: paperIds },
        { responseType: 'blob' }
      )
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const link = document.createElement('a')
      link.href = url
      link.download = 'papers_bundle.zip'
      link.click()
      window.URL.revokeObjectURL(url)
    },

    async batchDelete(paperIds) {
      const res = await api.post('/papers/batch-delete', { paper_ids: paperIds })
      return res.data
    },
  },
})

// 报告 Store
export const useReportStore = defineStore('report', {
  state: () => ({
    reports: [],
    currentReport: null,
    loading: false,
    total: 0,
    page: 1,
    pageSize: 20,
  }),

  actions: {
    async fetchReports(params = {}) {
      this.loading = true
      try {
        this.page = params.page ?? this.page
        this.pageSize = params.page_size ?? this.pageSize
        const res = await api.get('/reports', {
          params: { ...params, page: this.page, page_size: this.pageSize },
        })
        this.reports = res.data.items
        this.total = res.data.total
      } finally {
        this.loading = false
      }
    },

    async fetchReport(id) {
      this.loading = true
      try {
        const res = await api.get(`/reports/${id}`)
        this.currentReport = res.data
        return res.data
      } finally {
        this.loading = false
      }
    },

    async downloadReport(id, format = 'markdown') {
      const res = await api.get(`/reports/${id}/download?format=${format}`, {
        responseType: 'blob',
      })
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const link = document.createElement('a')
      link.href = url
      link.download = `report_${id}.${format === 'markdown' ? 'md' : 'pdf'}`
      link.click()
      window.URL.revokeObjectURL(url)
    },

    async batchDownload(reportIds) {
      const res = await api.post(
        '/reports/batch-download',
        { report_ids: reportIds },
        { responseType: 'blob' }
      )
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const link = document.createElement('a')
      link.href = url
      link.download = 'reports_bundle.zip'
      link.click()
      window.URL.revokeObjectURL(url)
    },

    async batchDelete(reportIds) {
      const res = await api.post('/reports/batch-delete', { report_ids: reportIds })
      return res.data
    },
  },
})

// 记忆 Store
export const useMemoryStore = defineStore('memory', {
  state: () => ({
    memories: [],
    total: 0,
    byType: {},
    loading: false,
  }),

  actions: {
    async fetchMemories(params = {}) {
      this.loading = true
      try {
        const res = await api.get('/memory', { params })
        this.memories = res.data.items
        this.total = res.data.total
        this.byType = res.data.by_type
      } finally {
        this.loading = false
      }
    },

    async createMemory(data) {
      const res = await api.post('/memory', data)
      return res.data
    },

    async deleteMemory(id) {
      await api.delete(`/memory/${id}`)
    },

    async cleanup() {
      const res = await api.post('/memory/cleanup')
      return res.data
    },
  },
})
