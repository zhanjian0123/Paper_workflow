/**
 * API 客户端封装
 */
import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

// 创建 axios 实例
const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    // 添加请求头（如需要认证 token）
    // const token = localStorage.getItem('token')
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`
    // }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => {
    return response
  },
  (error) => {
    // 统一错误处理
    if (error.response) {
      const { status, data } = error.response

      switch (status) {
        case 400:
          console.error('请求参数错误')
          break
        case 401:
          console.error('未授权，请重新登录')
          // TODO: 跳转到登录页
          break
        case 403:
          console.error('权限不足')
          break
        case 404:
          console.error('资源不存在')
          break
        case 500:
          console.error('服务器内部错误')
          break
        default:
          console.error(`请求失败：${status}`)
      }

      // 抛出详细错误信息
      throw new Error(data?.message || error.message)
    }

    if (error.code === 'ECONNABORTED') {
      console.error('请求超时')
      throw new Error('请求超时')
    }

    if (error.code === 'ERR_NETWORK') {
      console.error('网络错误')
      throw new Error('网络错误，请检查网络连接')
    }

    throw error
  }
)

export default apiClient
