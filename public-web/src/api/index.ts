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
export function fetchStatsOverview() {
  return request.get('/api/v1/stats/overview')
}
export function fetchHotSearches(limit = 12) {
  return request.get('/api/v1/ai/hot-searches', { params: { limit } })
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

// ============ 会员 ============
export function fetchMemberPackages() {
  return request.get('/api/v1/member-packages')
}
export function fetchMyMemberStatus() {
  return request.get('/api/v1/member-orders/my-status')
}
export function fetchMyOrders(params?: Record<string, any>) {
  return request.get('/api/v1/member-orders', { params })
}
export function createOrder(data: { package_id: number }) {
  return request.post('/api/v1/member-orders', data)
}
export function payOrder(orderNo: string, payType = 'manual') {
  return request.post(`/api/v1/member-orders/${orderNo}/pay`, null, { params: { pay_type: payType } })
}
