import request from '@/utils/request'

// 标讯列表（后台全量，含待审核）
export function fetchBidList(params: Record<string, any>) {
  return request.get('/api/v1/bids', { params })
}

export function fetchBidDetail(id: number) {
  return request.get(`/api/v1/bids/${id}`)
}

export function createBid(data: Record<string, any>) {
  return request.post('/api/v1/bids', data)
}

export function updateBid(data: Record<string, any>) {
  return request.put('/api/v1/bids', data)
}

export function auditBid(id: number) {
  return request.post(`/api/v1/bids/${id}/audit`)
}

export function offlineBid(id: number) {
  return request.post(`/api/v1/bids/${id}/offline`)
}

export function toggleBidTop(id: number, top?: boolean) {
  return request.post(`/api/v1/bids/${id}/top`, undefined, { params: { top } })
}

// 采集源
export function fetchSourceList() {
  return request.get('/api/v1/sources')
}
export function createSource(data: Record<string, any>) {
  return request.post('/api/v1/sources', data)
}
export function updateSource(id: number, data: Record<string, any>) {
  return request.put(`/api/v1/sources/${id}`, data)
}
export function deleteSource(id: number) {
  return request.delete(`/api/v1/sources/${id}`)
}
// 爬虫全量约 3~4 分钟（12 个 ccgp 分类 + ggzy 详情），单独加大超时
export function runCrawlAll() {
  return request.post('/api/v1/crawl/run-all', null, { timeout: 300000 })
}
export function runCrawlSource(sourceId: number) {
  return request.post(`/api/v1/crawl/run/${sourceId}`, null, { timeout: 300000 })
}

// 会员套餐
export function fetchPackageList() {
  return request.get('/api/v1/member-packages')
}

export function fetchOrderList(params?: Record<string, any>) {
  return request.get('/api/v1/member-orders', { params })
}

// 管理后台用户
export function fetchAdminUserList(params: Record<string, any>) {
  return request.get('/api/v1/admin/users', { params })
}

export function fetchRoleList() {
  return request.get('/api/v1/admin/users/roles')
}

// 字典
export function fetchNoticeTypes(category?: string) {
  return request.get('/api/v1/dicts/notice-types', { params: { category } })
}

export function fetchIndustries(parentId = 0) {
  return request.get('/api/v1/dicts/industries', { params: { parent_id: parentId } })
}

export function fetchRegions(parentId = 0) {
  return request.get('/api/v1/dicts/regions', { params: { parent_id: parentId } })
}

// 统计
export function fetchStatsOverview() {
  return request.get('/api/v1/stats/overview')
}

// 订阅管理
export function fetchSubscribeList(params?: Record<string, any>) {
  return request.get('/api/v1/subscribes', { params })
}
export function toggleSubscribe(id: number) {
  return request.put(`/api/v1/subscribes/${id}/toggle`)
}
export function deleteSubscribe(id: number) {
  return request.delete(`/api/v1/subscribes/${id}`)
}

// 数据清洗
export function runDataClean(payload?: Record<string, any>) {
  return request.post('/api/v1/admin/data-clean/run', payload || {})
}
export function fetchDataCleanStatus() {
  return request.get('/api/v1/admin/data-clean/status')
}

// ===== 推送管理 =====
// 模板（定时推送页）
export function fetchPushTemplates() {
  return request.get('/api/v1/admin/push/templates')
}
export function savePushTemplate(code: string, data: Record<string, any>) {
  return request.put(`/api/v1/admin/push/templates/${code}`, data)
}
export function createPushTemplate(data: Record<string, any>) {
  return request.post('/api/v1/admin/push/templates', data)
}
export function deletePushTemplate(code: string) {
  return request.delete(`/api/v1/admin/push/templates/${code}`)
}
export function previewPushTemplate(code: string, data?: Record<string, any>) {
  return request.post(`/api/v1/admin/push/templates/${code}/preview`, data || {})
}
export function testPushTemplate(code: string, data?: Record<string, any>) {
  return request.post(`/api/v1/admin/push/templates/${code}/test`, data || {}, { timeout: 20000 })
}
// 可用变量清单（变量管理界面）
export function fetchPushVariables() {
  return request.get('/api/v1/admin/push/variables')
}
// 临时推送
export function previewManualPush(payload: Record<string, any>) {
  return request.post('/api/v1/admin/push/manual/preview', payload)
}
export function sendManualBids(payload: Record<string, any>) {
  return request.post('/api/v1/admin/push/manual/bids', payload, { timeout: 20000 })
}
export function sendManualText(payload: Record<string, any>) {
  return request.post('/api/v1/admin/push/manual/text', payload, { timeout: 20000 })
}
// AI 生成
export function aiGeneratePush(messages: Record<string, any>[]) {
  return request.post('/api/v1/admin/push/ai/generate', { messages }, { timeout: 120000 })
}
export function aiSendPush(payload: Record<string, any>) {
  return request.post('/api/v1/admin/push/ai/send', payload, { timeout: 20000 })
}
// 推送记录 / 通道
export function fetchPushRecords(params?: Record<string, any>) {
  return request.get('/api/v1/admin/push/records', { params })
}
export function fetchPushChannels() {
  return request.get('/api/v1/admin/push/channels')
}
// 订阅用户（推送模块）
export function previewSubscribe(id: number, days = 7) {
  return request.get(`/api/v1/subscribes/${id}/preview`, { params: { days } })
}
export function pushSubscribeNow(id: number) {
  return request.post(`/api/v1/subscribes/${id}/push`)
}
export function pushAllSubscribes() {
  return request.post('/api/v1/subscribes/batch-push')
}
export function adminUpdateSubscribe(id: number, data: Record<string, any>) {
  return request.put(`/api/v1/subscribes/${id}/admin`, data)
}

// ===== AI 设置板块（后台 admin/ops） =====
export function fetchAISettings() {
  return request.get('/api/v1/admin/ai/settings')
}
export function saveAISetting(key: string, data: { value?: string; remark?: string }) {
  return request.put(`/api/v1/admin/ai/settings/${encodeURIComponent(key)}`, data)
}
export function fetchAISnapshots(key: string) {
  return request.get(`/api/v1/admin/ai/settings/${encodeURIComponent(key)}/snapshots`)
}
export function rollbackAISetting(key: string, snapshotId: number) {
  return request.post(`/api/v1/admin/ai/settings/${encodeURIComponent(key)}/rollback`,
                     { snapshot_id: snapshotId })
}
export function testAIConnection(payload: {
  provider?: string; base_url: string; api_key: string; model: string;
  temperature?: number; timeout?: number;
}) {
  return request.post('/api/v1/admin/ai/settings/test-connection', payload,
    { timeout: 30000 })
}
export function tryAIPrompt(payload: { setting_key: string; input_text: string }) {
  return request.post('/api/v1/admin/ai/settings/prompt/try', payload,
    { timeout: 60000 })
}
// AI 用量统计（日/周/月 + 30 天趋势 + 按功能拆分）
export function fetchAIUsage() {
  return request.get('/api/v1/admin/ai/usage')
}
