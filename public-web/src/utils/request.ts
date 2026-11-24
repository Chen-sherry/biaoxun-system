import axios from 'axios'
import { ElMessage } from 'element-plus'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '',
  timeout: 30000,
})

// 请求拦截器：带 token
request.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：解包 ApiResponse
request.interceptors.response.use(
  (resp) => {
    const data = resp.data
    // 登录例外：直接返回
    if (resp.config.url?.includes('/auth/login')) {
      return data
    }
    // ApiResponse 包裹
    if (data && typeof data === 'object' && 'code' in data) {
      if (data.code !== 0) {
        ElMessage.error(data.msg || '请求失败')
        if (data.code === 401) {
          localStorage.removeItem('token')
          window.location.href = `${import.meta.env.BASE_URL}login`
        }
        return Promise.reject(new Error(data.msg || 'error'))
      }
      return data.data
    }
    return data
  },
  (err) => {
    ElMessage.error(err.message || '网络异常')
    return Promise.reject(err)
  },
)

export default request
