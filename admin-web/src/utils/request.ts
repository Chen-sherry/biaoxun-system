import axios from 'axios'
import { ElMessage } from 'element-plus'

const TOKEN_KEY = 'BID_ADMIN_TOKEN'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '',
  timeout: 30000,
})

// 请求拦截：只加 token，不管 NProgress（NProgress 统一由路由守卫控制）
request.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 统一鉴权失败处理（只清 token，不硬跳转）
function handleUnauthorized(msg?: string) {
  localStorage.removeItem(TOKEN_KEY)
  window.dispatchEvent(new CustomEvent('auth:unauthorized', { detail: { msg } }))
}

// 响应拦截
request.interceptors.response.use(
  (res) => {
    const data = res.data
    // 后端统一响应格式 { code, msg, data }
    if (data && typeof data === 'object' && 'code' in data) {
      if (data.code === 0) {
        return data.data
      }
      if (data.code === 401 || data.msg?.includes('未登录')) {
        handleUnauthorized(data.msg)
        ElMessage.warning(data.msg || '登录已过期，请重新登录')
        return Promise.reject(new Error(data.msg || '未登录'))
      }
      ElMessage.error(data.msg || '请求失败')
      return Promise.reject(new Error(data.msg))
    }
    return data
  },
  (err) => {
    const status = err?.response?.status
    const msg = err?.response?.data?.msg || err.message || '网络异常'
    if (status === 401) {
      handleUnauthorized(msg)
      ElMessage.warning('登录已过期，请重新登录')
    } else {
      ElMessage.error(msg)
    }
    return Promise.reject(err)
  }
)

export { request, TOKEN_KEY }
export default request
