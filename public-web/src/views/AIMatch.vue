<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChatLineRound, MagicStick, Clock, Search, ArrowRight } from '@element-plus/icons-vue'
import axios from 'axios'

const router = useRouter()
const route = useRoute()

const query = ref('')
const loading = ref(false)
const hasSearched = ref(false)

interface AIItem {
  id: number
  title: string
  score: number
  reason: string
  publish_time?: string
  tenderee?: string
  budget?: string
  region_name?: string
}
const items = ref<AIItem[]>([])

// ===== AI 检索（付费会员专属：未登录 401 / 非付费 403 → 提示开通会员） =====
async function doAiSearch() {
  const q = query.value.trim()
  if (!q) { ElMessage.warning('请输入检索内容'); return }
  loading.value = true
  hasSearched.value = false
  items.value = []
  try {
    const token = localStorage.getItem('token')
    const res = await axios.post(`${import.meta.env.VITE_API_BASE || ''}/api/v1/ai/search`,
      { query: q, limit: 20 },
      {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        timeout: 120000,
      })
    hasSearched.value = true
    if (res.data.code === 0) {
      items.value = res.data.data.items || []
      if (items.value.length === 0) {
        ElMessage.info('没有找到评分高于 75 分的相关标讯，换个说法试试')
      }
    } else {
      ElMessage.error(res.data.message || '检索失败')
    }
  } catch (e: any) {
    const status = e?.response?.status
    if (status === 401 || status === 403) {
      try {
        await ElMessageBox.alert(
          'AI 检索是付费会员专属功能，开通会员后即可使用。\n（当前为演示环境，会员开通功能即将上线）',
          '会员专享',
          { type: 'warning', confirmButtonText: '查看会员套餐', center: true },
        )
        router.push('/member')
      } catch { /* 用户取消 */ }
    } else if (status === 400) {
      ElMessage.error('检索内容不能为空')
    } else {
      ElMessage.error('AI 检索服务暂时不可用，请稍后再试')
    }
  } finally {
    loading.value = false
  }
}

// 首页 AI 搜索框跳转过来时带 q 参数，自动检索
onMounted(() => {
  const q = route.query.q
  if (typeof q === 'string' && q.trim()) {
    query.value = q.trim()
    doAiSearch()
  }
})

function viewDetail(id: number) {
  router.push(`/bid/${id}`)
}
function goSearch() {
  router.push('/search')
}

// ===== 最近浏览（与 AI 检索无关的辅助功能，保留） =====
const recent = ref<any[]>([])
onMounted(async () => {
  try {
    const res = await axios.get(`${import.meta.env.VITE_API_BASE || ''}/api/v1/bids/recently-viewed`)
    if (res.data.code === 0) recent.value = res.data.data.items || []
  } catch { /* 忽略 */ }
})
</script>

<template>
  <div class="ai-match-page">
    <div class="page-container">

      <el-card shadow="never" class="main-card">
        <template #header>
          <div class="card-header">
            <el-icon><ChatLineRound /></el-icon>
            <span>AI 检索（大白话搜索）</span>
            <span class="sub-title">大白话描述需求 → AI 转译检索 → 相关性评分，只展示 75 分以上的结果</span>
          </div>
        </template>

        <!-- 搜索框 -->
        <div class="search-area">
          <el-input
            v-model="query"
            size="large"
            placeholder="大白话描述你要找的标讯，例如：合肥的学校招标，预算100万以内，最近一个月"
            clearable
            @keyup.enter="doAiSearch"
          >
            <template #prefix><el-icon><MagicStick /></el-icon></template>
            <template #append>
              <el-button type="primary" :loading="loading" @click="doAiSearch">
                <el-icon><Search /></el-icon> AI 检索
              </el-button>
            </template>
          </el-input>
          <div class="hint">会员专享 · 检索结果按相关性评分，75 分以下不展示</div>
        </div>

        <!-- 加载中 -->
        <div v-if="loading" class="loading-area">
          <el-icon class="is-loading" :size="28"><MagicStick /></el-icon>
          <p>AI 正在理解你的需求并检索知识库…</p>
          <p class="loading-sub">转译 → 候选检索 → 语义打分，约 5~30 秒</p>
        </div>

        <!-- 结果列表 -->
        <div v-else-if="items.length > 0" class="results">
          <div class="result-meta">共 {{ items.length }} 条评分 75+ 的相关标讯</div>
          <div
            v-for="item in items"
            :key="item.id"
            class="result-card"
            @click="viewDetail(item.id)"
          >
            <div class="result-main">
              <div class="result-title">{{ item.title }}</div>
              <div class="result-reason">
                <el-tag size="small" type="success">AI 评分 {{ item.score }}</el-tag>
                <span class="reason-text">{{ item.reason }}</span>
              </div>
              <div class="result-meta-line">
                <span v-if="item.tenderee">招标人：{{ item.tenderee }}</span>
                <span v-if="item.region_name">地区：{{ item.region_name }}</span>
                <span v-if="item.budget">预算：{{ item.budget }}</span>
                <span v-if="item.publish_time">发布：{{ item.publish_time.slice(0, 10) }}</span>
              </div>
            </div>
            <el-icon class="result-arrow"><ArrowRight /></el-icon>
          </div>
        </div>

        <!-- 空状态 -->
        <el-empty
          v-else-if="hasSearched"
          description="没有找到评分高于 75 分的相关标讯，换个说法试试"
        />
      </el-card>

      <!-- 最近浏览 -->
      <el-card shadow="never" class="recent-card" v-if="recent.length > 0">
        <template #header>
          <div class="card-header">
            <el-icon><Clock /></el-icon>
            <span>最近浏览</span>
          </div>
        </template>
        <div class="recent-list">
          <div v-for="item in recent" :key="item.id" class="recent-item" @click="viewDetail(item.id)">
            <span class="recent-title">{{ item.title }}</span>
            <span class="recent-time">{{ (item.viewed_at || '').slice(0, 10) }}</span>
          </div>
        </div>
      </el-card>

      <div class="other-search">
        <el-button @click="goSearch">
          <el-icon><ArrowRight /></el-icon> 使用高级检索（多条件筛选）
        </el-button>
      </div>

    </div>
  </div>
</template>

<style scoped>
.ai-match-page { min-height: 100vh; background: #f5f7fa; }
.page-container { max-width: 960px; margin: 0 auto; padding: 24px 16px; }

.main-card { border-radius: 8px; }
.card-header { display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 16px; }
.card-header .sub-title { font-weight: 400; font-size: 13px; color: #909399; margin-left: 8px; }

.search-area { margin-bottom: 20px; }
.search-area :deep(.el-input-group__append) { padding: 0 20px; }
.hint { font-size: 12px; color: #909399; margin-top: 8px; text-align: center; }

.loading-area { text-align: center; padding: 48px 0; color: #667eea; }
.loading-area p { margin: 12px 0 0; font-size: 14px; }
.loading-sub { color: #c0c4cc; font-size: 12px !important; }

.result-meta { font-size: 13px; color: #909399; margin-bottom: 12px; }
.results { display: flex; flex-direction: column; gap: 12px; }
.result-card {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px; background: #fff; border: 1px solid #e4e7ed;
  border-radius: 8px; cursor: pointer; transition: all 0.2s;
}
.result-card:hover { border-color: #667eea; box-shadow: 0 2px 8px rgba(102, 126, 234, 0.15); transform: translateY(-1px); }
.result-main { flex: 1; min-width: 0; }
.result-title { font-size: 15px; font-weight: 600; color: #303133; margin-bottom: 8px; line-height: 1.4; }
.result-reason { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.reason-text { font-size: 13px; color: #909399; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.result-meta-line { font-size: 12px; color: #909399; display: flex; gap: 16px; flex-wrap: wrap; }
.result-arrow { color: #c0c4cc; font-size: 18px; }

.recent-card { margin-top: 20px; border-radius: 8px; }
.recent-list { display: flex; flex-direction: column; }
.recent-item { display: flex; justify-content: space-between; padding: 10px 4px; border-bottom: 1px solid #f0f2f5; cursor: pointer; }
.recent-item:last-child { border-bottom: none; }
.recent-item:hover .recent-title { color: #667eea; }
.recent-title { font-size: 14px; color: #303133; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; margin-right: 12px; }
.recent-time { font-size: 13px; color: #909399; }

.other-search { text-align: center; margin-top: 24px; }

/* ===== 移动端（≤768px）===== */
@media (max-width: 768px) {
  .page-container { padding: 14px 10px; }
  .card-header { flex-wrap: wrap; font-size: 15px; }
  .card-header .sub-title { display: none; }
  .search-area :deep(.el-input-group__append) { padding: 0 10px; }
  .result-card { padding: 12px; }
  .result-meta-line { gap: 8px 12px; }
  .reason-text { white-space: normal; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
}
</style>
