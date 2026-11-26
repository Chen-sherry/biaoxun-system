<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChatLineRound, MagicStick, Clock, Search, ArrowRight, DataAnalysis } from '@element-plus/icons-vue'
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
    <div class="ai-glow" aria-hidden="true"></div>
    <div class="page-container">

      <div class="page-head">
        <span class="section-kicker">AI SEMANTIC SEARCH</span>
        <h1>智能检索</h1>
        <p>描述需求 → AI 转译检索 → 相关性评分，只展示 75 分以上的结果</p>
      </div>

      <el-card shadow="never" class="main-card tech-card">
        <!-- 搜索框 -->
        <div class="search-area">
          <el-input
            v-model="query"
            size="large"
            placeholder="描述你要找的标讯，例如：合肥的学校招标，预算100万以内，最近一个月"
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
          <div class="hint"><el-icon><DataAnalysis /></el-icon> 会员专享 · 检索结果按相关性评分，75 分以下不展示</div>
        </div>

        <!-- 加载中 -->
        <div v-if="loading" class="loading-area">
          <div class="ai-loader"><span></span><span></span><span></span></div>
          <p>AI 正在理解你的需求并检索知识库…</p>
          <p class="loading-sub">转译 → 候选检索 → 语义打分，约 5~30 秒</p>
        </div>

        <!-- 结果列表 -->
        <div v-else-if="items.length > 0" class="results">
          <div class="result-meta"><el-icon><DataLine /></el-icon> 共 {{ items.length }} 条评分 75+ 的相关标讯</div>
          <div
            v-for="item in items"
            :key="item.id"
            class="result-card"
            @click="viewDetail(item.id)"
          >
            <div class="score-badge">
              <div class="score-num">{{ item.score }}</div>
              <div class="score-label">AI 评分</div>
            </div>
            <div class="result-main">
              <div class="result-title">{{ item.title }}</div>
              <div class="result-reason">
                <el-tag size="small" type="success" effect="dark">高相关</el-tag>
                <span class="reason-text">{{ item.reason }}</span>
              </div>
              <div class="result-meta-line">
                <span v-if="item.tenderee"><el-icon><OfficeBuilding /></el-icon> {{ item.tenderee }}</span>
                <span v-if="item.region_name"><el-icon><Location /></el-icon> {{ item.region_name }}</span>
                <span v-if="item.budget"><el-icon><Wallet /></el-icon> {{ item.budget }}</span>
                <span v-if="item.publish_time"><el-icon><Calendar /></el-icon> {{ item.publish_time.slice(0, 10) }}</span>
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
      <el-card shadow="never" class="recent-card tech-card" v-if="recent.length > 0">
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
.ai-match-page { position: relative; min-height: calc(100vh - 64px); overflow: hidden; }
.ai-glow {
  position: absolute; top: -120px; left: 50%; transform: translateX(-50%);
  width: 900px; height: 500px; pointer-events: none;
  background-image: url('@/assets/brand/bg-glow.svg');
  background-size: cover; opacity: 0.5;
}
.page-container { position: relative; z-index: 1; max-width: 960px; margin: 0 auto; padding: 28px 16px; }
.page-head { margin-bottom: 24px; }
.page-head h1 { font-size: 28px; font-weight: 800; color: var(--ink-900); margin: 8px 0 5px; }
.page-head p { color: var(--ink-500); font-size: 14px; }

.main-card { padding: 24px; border-radius: var(--r-md) !important; }
.card-header { display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 16px; }

.search-area { margin-bottom: 20px; }
.search-area :deep(.el-input__wrapper) { height: 50px; }
.search-area :deep(.el-input-group__append .el-button) { height: 50px; font-weight: 600; }
.hint { font-size: 12px; color: var(--ink-500); margin-top: 10px; text-align: center; display: flex; align-items: center; justify-content: center; gap: 5px; }
.hint :deep(.el-icon) { color: var(--accent-strong); }

/* AI 加载动画 */
.loading-area { text-align: center; padding: 56px 0 40px; }
.ai-loader { display: flex; justify-content: center; gap: 8px; margin-bottom: 20px; }
.ai-loader span {
  width: 12px; height: 12px; border-radius: 50%;
  background: linear-gradient(135deg, var(--accent), var(--accent-cyan));
  animation: pulse-glow 1.2s ease-in-out infinite;
}
.ai-loader span:nth-child(2) { animation-delay: 0.2s; }
.ai-loader span:nth-child(3) { animation-delay: 0.4s; }
.loading-area p { margin: 8px 0 0; font-size: 14px; color: var(--ink-700); font-weight: 500; }
.loading-sub { color: var(--ink-400) !important; font-size: 12px !important; font-weight: 400 !important; }

.result-meta { font-size: 13px; color: var(--ink-500); margin-bottom: 14px; display: flex; align-items: center; gap: 6px; }
.result-meta :deep(.el-icon) { color: var(--accent-strong); }
.results { display: flex; flex-direction: column; gap: 12px; }
.result-card {
  display: flex; align-items: flex-start; gap: 16px;
  padding: 18px; background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--r-md); cursor: pointer; transition: all 0.3s var(--ease);
}
.result-card:hover { border-color: var(--accent-line); box-shadow: var(--shadow-hover); transform: translateY(-2px); }
.score-badge {
  flex: none; width: 58px; text-align: center; padding: 10px 4px; border-radius: 10px;
  background: linear-gradient(150deg, rgba(56, 189, 248, 0.14), rgba(129, 140, 248, 0.10));
  border: 1px solid rgba(56, 189, 248, 0.3);
}
.score-num { font-size: 22px; font-weight: 800; color: var(--accent-deep); line-height: 1; font-variant-numeric: tabular-nums; }
.score-label { font-size: 10px; color: var(--ink-500); margin-top: 4px; }
.result-main { flex: 1; min-width: 0; }
.result-title { font-size: 15px; font-weight: 600; color: var(--ink-900); margin-bottom: 10px; line-height: 1.5; }
.result-card:hover .result-title { color: var(--accent-deep); }
.result-reason { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.reason-text { font-size: 13px; color: var(--ink-700); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.result-meta-line { font-size: 12px; color: var(--ink-500); display: flex; gap: 16px; flex-wrap: wrap; }
.result-meta-line span { display: inline-flex; align-items: center; gap: 4px; }
.result-arrow { color: var(--line-strong); font-size: 18px; flex: none; margin-top: 20px; transition: all 0.3s var(--ease); }
.result-card:hover .result-arrow { color: var(--accent); transform: translateX(3px); }

.recent-card { margin-top: 20px; }
.recent-list { display: flex; flex-direction: column; }
.recent-item { display: flex; justify-content: space-between; padding: 11px 4px; border-bottom: 1px solid var(--line); cursor: pointer; }
.recent-item:last-child { border-bottom: none; }
.recent-item:hover .recent-title { color: var(--accent-deep); }
.recent-title { font-size: 14px; color: var(--ink-800); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; margin-right: 12px; }
.recent-time { font-size: 13px; color: var(--ink-400); flex: none; }
.other-search { text-align: center; margin-top: 26px; }

/* ===== 移动端（≤768px）===== */
@media (max-width: 768px) {
  .page-container { padding: 18px 12px; }
  .page-head h1 { font-size: 22px; }
  .main-card { padding: 16px; }
  .card-header .sub-title { display: none; }
  .result-card { padding: 13px; gap: 12px; }
  .score-badge { width: 50px; }
  .score-num { font-size: 19px; }
  .result-meta-line { gap: 8px 12px; }
  .reason-text { white-space: normal; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
  .result-arrow { display: none; }
}
</style>
