import request from '@/utils/request'

// ============ 门户公开 ============
export function fetchPublicBids(params: any) {
  return request.get('/api/v1/public/bids', { params })
}
export function fetchPublicHot(limit = 20) {
  return request.get('/api/v1/public/bids/hot', { params: { limit } })
}
export function fetchPublicBidDetail(id: number) {
  return request.get(`/api/v1/public/bids/${id}`)
}
export function fetchPortalStats() {
  return request.get('/api/v1/public/stats/portal')
}
export function fetchPublicNoticeTypes() {
  return request.get('/api/v1/public/dicts/notice-types')
}
export function fetchPublicRegions(parentId = 0) {
  return request.get('/api/v1/public/dicts/regions', { params: { parent_id: parentId } })
}

// ============ 认证 ============
export function login(data: { username: string; password: string }) {
  return request.post('/api/v1/auth/login', data)
}
export function register(data: any) {
  return request.post('/api/v1/auth/register', data)
}
export function fetchMe() {
  return request.get('/api/v1/auth/me')
}
