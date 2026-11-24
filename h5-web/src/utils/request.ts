import axios from 'axios'
import { showToast } from 'vant'

const TOKEN_KEY = 'BID_H5_TOKEN'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '',
  timeout: 15000,
})

request.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

request.interceptors.response.use(
  (res) => {
    const data = res.data
    if (data && typeof data === 'object' && 'code' in data) {
      if (data.code === 0) return data.data
      if (data.code === 401) {
        localStorage.removeItem(TOKEN_KEY)
        window.location.hash = '#/login'
        return Promise.reject(new Error(data.msg))
      }
      showToast(data.msg || '请求失败')
      return Promise.reject(new Error(data.msg))
    }
    return data
  },
  (err) => {
    showToast(err.message || '网络异常')
    return Promise.reject(err)
  }
)

export { request, TOKEN_KEY }
export default request
