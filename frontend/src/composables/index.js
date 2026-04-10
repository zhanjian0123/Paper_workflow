/**
 *  composables - Vue 3 组合式函数
 */

import { ref, computed, onMounted, onUnmounted } from 'vue'

/**
 * 轮询数据
 */
export function usePolling(fn, interval = 5000, immediate = true) {
  const loading = ref(false)
  const error = ref(null)
  const data = ref(null)
  let timer = null

  const execute = async () => {
    loading.value = true
    error.value = null
    try {
      data.value = await fn()
    } catch (err) {
      error.value = err
    } finally {
      loading.value = false
    }
  }

  const start = () => {
    if (immediate) {
      execute()
    }
    timer = setInterval(execute, interval)
  }

  const stop = () => {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  onMounted(() => {
    start()
  })

  onUnmounted(() => {
    stop()
  })

  return {
    loading,
    error,
    data,
    refresh: execute,
    start,
    stop,
  }
}

/**
 * WebSocket 连接
 */
export function useWebSocket(url, options = {}) {
  const {
    onOpen,
    onMessage,
    onError,
    onClose,
    autoConnect = true,
    reconnectInterval = 3000,
    maxReconnects = 5,
  } = options

  const ws = ref(null)
  const isConnected = ref(false)
  const reconnectCount = ref(0)

  const connect = () => {
    ws.value = new WebSocket(url)

    ws.value.onopen = () => {
      isConnected.value = true
      reconnectCount.value = 0
      onOpen?.()
    }

    ws.value.onmessage = (event) => {
      const data = JSON.parse(event.data)
      onMessage?.(data)
    }

    ws.value.onerror = (error) => {
      isConnected.value = false
      onError?.(error)
    }

    ws.value.onclose = () => {
      isConnected.value = false
      onClose?.()

      // 自动重连
      if (reconnectCount.value < maxReconnects) {
        reconnectCount.value++
        setTimeout(connect, reconnectInterval)
      }
    }
  }

  const disconnect = () => {
    if (ws.value) {
      ws.value.close()
      ws.value = null
    }
  }

  const send = (data) => {
    if (ws.value && isConnected.value) {
      ws.value.send(JSON.stringify(data))
    }
  }

  if (autoConnect) {
    onMounted(() => {
      connect()
    })

    onUnmounted(() => {
      disconnect()
    })
  }

  return {
    ws,
    isConnected,
    connect,
    disconnect,
    send,
  }
}

/**
 * 本地存储
 */
export function useStorage(key, defaultValue = null) {
  const getItem = () => {
    try {
      const item = localStorage.getItem(key)
      return item ? JSON.parse(item) : defaultValue
    } catch {
      return defaultValue
    }
  }

  const setItem = (value) => {
    try {
      localStorage.setItem(key, JSON.stringify(value))
    } catch (err) {
      console.error('Failed to save to localStorage:', err)
    }
  }

  const removeItem = () => {
    try {
      localStorage.removeItem(key)
    } catch (err) {
      console.error('Failed to remove from localStorage:', err)
    }
  }

  const value = ref(getItem())

  const setValue = (newValue) => {
    value.value = newValue
    setItem(newValue)
  }

  return {
    value,
    setValue,
    remove: removeItem,
  }
}

/**
 * 分页
 */
export function usePagination(initialPage = 1, initialPageSize = 20) {
  const page = ref(initialPage)
  const pageSize = ref(initialPageSize)
  const total = ref(0)

  const totalPages = computed(() => Math.ceil(total.value / pageSize.value))
  const hasPrev = computed(() => page.value > 1)
  const hasNext = computed(() => page.value < totalPages.value)

  const nextPage = () => {
    if (hasNext.value) {
      page.value++
    }
  }

  const prevPage = () => {
    if (hasPrev.value) {
      page.value--
    }
  }

  const goToPage = (p) => {
    if (p >= 1 && p <= totalPages.value) {
      page.value = p
    }
  }

  const setPageSize = (size) => {
    pageSize.value = size
    page.value = 1
  }

  const reset = () => {
    page.value = initialPage
    pageSize.value = initialPageSize
    total.value = 0
  }

  return {
    page,
    pageSize,
    total,
    totalPages,
    hasPrev,
    hasNext,
    nextPage,
    prevPage,
    goToPage,
    setPageSize,
    reset,
  }
}

/**
 * 表单验证
 */
export function useFormValidation(rules) {
  const errors = ref({})

  const validate = (form) => {
    errors.value = {}

    for (const [field, fieldRules] of Object.entries(rules)) {
      const value = form[field]

      for (const rule of fieldRules) {
        if (typeof rule === 'string') {
          if (rule === 'required' && !value) {
            errors.value[field] = `${field} 是必填项`
            break
          }
        } else if (typeof rule === 'function') {
          const result = rule(value)
          if (result !== true) {
            errors.value[field] = result
            break
          }
        }
      }
    }

    return Object.keys(errors.value).length === 0
  }

  const clearError = (field) => {
    delete errors.value[field]
  }

  const clearErrors = () => {
    errors.value = {}
  }

  return {
    errors,
    validate,
    clearError,
    clearErrors,
  }
}
