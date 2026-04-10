import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 论文上传相关 API
export const uploadApi = {
  // 上传单篇论文
  uploadPaper(file, title) {
    const formData = new FormData()
    formData.append('file', file)
    if (title) formData.append('title', title)
    return api.post('/upload/papers', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // 批量上传
  uploadPapersBatch(files) {
    const formData = new FormData()
    files.forEach(file => formData.append('files', file))
    return api.post('/upload/papers/batch', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // 解析论文
  parsePaper(paperId) {
    return api.post(`/upload/papers/${paperId}/parse`)
  },

  // 完整解析论文
  parsePaperFull(paperId) {
    return api.post(`/upload/papers/${paperId}/full-parse`)
  },

  // 获取论文列表
  getPapers(params) {
    return api.get('/papers', { params })
  },

  // 获取论文详情
  getPaper(paperId) {
    return api.get(`/papers/${paperId}`)
  },

  // 从本地论文创建工作流
  createWorkflowFromPapers(paperIds, query) {
    const formData = new FormData()
    paperIds.forEach(id => formData.append('paper_ids', id))
    formData.append('query', query)
    formData.append('skip_search', 'true')
    return api.post('/workflows/from-local-papers', formData)
  },

  // 获取工作流详情
  getWorkflow(workflowId) {
    return api.get(`/workflows/${workflowId}`)
  },

  // 获取工作流列表
  getWorkflows(params) {
    return api.get('/workflows', { params })
  },

  // 取消工作流
  cancelWorkflow(workflowId, reason) {
    return api.post(`/workflows/${workflowId}/cancel`, { reason })
  },
}

export default api
