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
  notice_type?: string
  snippet?: string
}
const items = ref<AIItem[]>([])   // 全量打分结果（降序，后端一次返回）
const totalHits = ref<number | null>(null)   // 关键词全量命中数（后端 total_hits，真实总数）
const fallbackUsed = ref(false)   // 最高分 <60，兜底展示

// 转译结果 / 检索诊断（chips、放宽提示、空结果诊断态）
const translated = ref<any>(null)
const diagnostics = ref<any>(null)
const dateRelaxed = ref(false)

// ===== 分档渐进展示：默认 75+，每点一次加载更多降一档（60→40→20→0） =====
const BANDS = [75, 60, 40, 20, 0]
const minScore = ref(75)

const visibleItems = computed(() => items.value.filter(i => i.score >= minScore.value))
const hiddenCount = computed(() => items.value.length - visibleItems.value.length)
const allShown = computed(() => hiddenCount.value === 0)

// 下一档阈值（跳过没有新增条目的空档）
const nextBand = computed(() => {
  const cur = minScore.value
  for (const b of BANDS) {
    if (b < cur && items.value.some(i => i.score >= b && i.score < cur)) return b
  }
  return -1   // 没有更低档可加载
})

function loadMore() {
  const nb = nextBand.value
  if (nb >= 0) minScore.value = nb
}

// 初始档位：没有 75+ 时从 60 起步；连 60 都没有（兜底）则直接全量显示
function initBand() {
  if (items.value.some(i => i.score >= 75)) minScore.value = 75
  else if (items.value.some(i => i.score >= 60)) minScore.value = 60
  else minScore.value = 0
}

// 真实总数：全量命中数 > 打分池时顶部显示「共 N 条 · 精排 M」，
// 否则维持原显示（totalHits 为空/命中数不超打分池时不加噪音）
const totalCount = computed(() =>
  totalHits.value && totalHits.value > items.value.length ? totalHits.value : items.value.length)
const rankedCount = computed(() =>
  totalHits.value && totalHits.value > items.value.length ? items.value.length : 0)

// 分档分隔线：可见列表中跨过档位边界时插入说明
function bandDivider(index: number): string | null {
  const list = visibleItems.value
  const cur = list[index]
  const prev = index > 0 ? list[index - 1] : null
  if (!prev || !cur) return null
  if (prev.score >= 75 && cur.score < 75) return '以下为辅助推荐（60~74 分，可能不完全匹配）'
  if (prev.score >= 60 && cur.score < 60) return '以下为一般相关（40~59 分，仅供参考）'
  if (prev.score >= 40 && cur.score < 40) return '以下为弱相关（20~39 分，谨慎参考）'
  if (prev.score >= 20 && cur.score < 20) return '以下为低相关（低于 20 分，兜底参考）'
  return null
}

const conditionChips = computed(() => {
  const t = translated.value
  if (!t) return []
  const chips: string[] = []
  if (t.keywords?.length) chips.push(...t.keywords)
  if (t.region_name) chips.push(t.region_name)
  if (t.date_from || t.date_to) {
    chips.push(`${t.date_from || '不限'} ~ ${t.date_to || '不限'}`)
  }
  if (t.notice_type) chips.push(t.notice_type)
  if (t.procure_type) chips.push(t.procure_type)
  if (t.budget_max != null) chips.push(`预算 ≤ ${t.budget_max} 万`)
  if (t.budget_min != null) chips.push(`预算 ≥ ${t.budget_min} 万`)
  return chips
})

const emptyDesc = computed(() => {
  const d = diagnostics.value
  if (!d) return '没有找到相关标讯，换个说法试试'
  const range = d.library_date_range ? `（库内标讯时间范围：${d.library_date_range}）` : ''
  if (d.candidate_count === 0) {
    return `知识库未检索到相关候选${range}，试试更宽泛的说法或去掉时间/地区限制`
  }
  return `检索到 ${d.candidate_count} 条候选，但最高只有 ${d.top_score} 分，未达展示线${range}。换个说法试试`
})

const diagModeText = computed(() => {
  const m = diagnostics.value?.match_mode as string
  const map: Record<string, string> = {
    ft_and: '全文检索（全词）',
    ft_or: '全文检索',
    ft_or_exp: '全文检索（同义词）',
    like_and: '关键词匹配',
    like_or: '关键词匹配（兜底）',
    latest: '最新发布',
  }
  return (m && map[m]) || m || '-'
})

// ===== AI 检索（付费会员专属：未登录 401 / 非付费 403 → 提示开通会员） =====
async function doAiSearch() {
  const q = query.value.trim()
  if (!q) { ElMessage.warning('请输入检索内容'); return }
  loading.value = true
  hasSearched.value = false
  items.value = []
  totalHits.value = null
  translated.value = null
  diagnostics.value = null
  dateRelaxed.value = false
  fallbackUsed.value = false
  minScore.value = 75
  try {
    const token = localStorage.getItem('token')
    const res = await axios.post(`${import.meta.env.VITE_API_BASE || ''}/api/v1/ai/search`,
      { query: q, limit: 120 },
      {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        timeout: 120000,
      })
    hasSearched.value = true
    if (res.data.code === 0) {
      const data = res.data.data || {}
      items.value = data.items || []
      totalHits.value = typeof data.total_hits === 'number' ? data.total_hits : null
      translated.value = data.translated || null
      diagnostics.value = data.diagnostics || null
      dateRelaxed.value = !!data.date_relaxed
      fallbackUsed.value = !!data.fallback_used
      initBand()   // 按结果分布定初始档位
      if (items.value.length === 0) {
        ElMessage.info('没有找到达到展示分数的相关标讯，换个说法试试')
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
          {
            type: 'warning',
            confirmButtonText: '查看会员套餐',
            cancelButtonText: '登录',
            showCancelButton: true,
            distinguishCancelAndClose: true,
            center: true,
          },
        )
        router.push('/member')
      } catch (action) {
        // 「登录」按钮 = cancel；右上角 X = close（不跳转）
        if (action === 'cancel') router.push('/login')
      }
    } else if (status === 400) {
      ElMessage.error('检索内容不能为空')
    } else {
      ElMessage.error('AI 检索服务暂时不可用，请稍后再试')
    }
  } finally {
    loading.value = false
  }
}

// 首页 AI 搜索框跳转带 q 参数、顶栏跳转带 kw 参数，任一存在即自动检索
onMounted(() => {
  const raw = route.query.q ?? route.query.kw
  if (typeof raw === 'string' && raw.trim()) {
    query.value = raw.trim()
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
        <p>描述需求，AI 转译 + 语义评分，默认展示 75+ 高相关</p>
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
          <div class="hint"><el-icon><DataAnalysis /></el-icon> 会员专享 · 默认展示 75+ 高相关</div>
        </div>

        <!-- 加载中 -->
        <div v-if="loading" class="loading-area">
          <div class="ai-loader"><span></span><span></span><span></span></div>
          <p>AI 正在理解你的需求并检索知识库…</p>
          <p class="loading-sub">转译 → 候选召回 → 语义打分，约 5~30 秒</p>
        </div>

        <!-- 结果列表 -->
        <div v-else-if="items.length > 0" class="results">
          <div class="result-meta">
            <el-icon><DataLine /></el-icon>
            共 {{ totalCount }} 条<template v-if="rankedCount > 0"> · 精排 {{ rankedCount }}</template><template v-if="hiddenCount > 0"> · 已显示 {{ visibleItems.length }} 条</template>
          </div>

          <!-- AI 识别出的检索条件 -->
          <div v-if="conditionChips.length" class="condition-chips">
            <span class="chips-label">AI 识别：</span>
            <el-tag v-for="(c, i) in conditionChips" :key="i" size="small" effect="plain">{{ c }}</el-tag>
          </div>
          <el-alert
            v-if="fallbackUsed"
            title="没有达到 60 分的结果，以下为最接近的兜底推荐"
            type="warning" :closable="false" show-icon class="relax-alert"
          />
          <el-alert
            v-if="dateRelaxed"
            title="知识库中该时间段没有命中结果，已自动放宽时间条件，以下结果按相关性排序"
            type="info" :closable="false" show-icon class="relax-alert"
          />
          <div v-if="diagnostics" class="diag-line">{{ diagModeText }} · 候选 {{ diagnostics.candidate_count }} 条</div>

          <template v-for="(item, index) in visibleItems" :key="item.id">
            <!-- 分档分隔线：跨过档位边界时插入 -->
            <div v-if="bandDivider(index)" class="tier-divider">
              <span class="tier-divider-text">{{ bandDivider(index) }}</span>
            </div>
            <div class="result-card" @click="viewDetail(item.id)">
              <div class="score-badge" :class="{ mid: item.score < 75, low: item.score < 60 }">
                <div class="score-num">{{ item.score }}</div>
                <div class="score-label">AI 评分</div>
              </div>
              <div class="result-main">
                <div class="result-title">{{ item.title }}</div>
                <div class="result-reason">
                  <el-tag size="small" :type="item.score >= 75 ? 'success' : item.score >= 60 ? 'info' : 'warning'" effect="dark">
                    {{ item.score >= 75 ? '高相关' : item.score >= 60 ? '辅助推荐' : '兜底参考' }}
                  </el-tag>
                  <span class="reason-text">{{ item.reason }}</span>
                </div>
                <div v-if="item.snippet" class="result-snippet">{{ item.snippet.slice(0, 160) }}</div>
                <div class="result-meta-line">
                  <span v-if="item.notice_type"><el-icon><Tickets /></el-icon> {{ item.notice_type }}</span>
                  <span v-if="item.tenderee"><el-icon><OfficeBuilding /></el-icon> {{ item.tenderee }}</span>
                  <span v-if="item.region_name"><el-icon><Location /></el-icon> {{ item.region_name }}</span>
                  <span v-if="item.budget"><el-icon><Wallet /></el-icon> {{ item.budget }}</span>
                  <span v-if="item.publish_time"><el-icon><Calendar /></el-icon> {{ item.publish_time.slice(0, 10) }}</span>
                </div>
              </div>
              <el-icon class="result-arrow"><ArrowRight /></el-icon>
            </div>
          </template>

          <!-- 加载更多：按 20 分一档逐级放宽；全部显示后提示到底 -->
          <div v-if="!allShown" class="load-more">
            <el-button plain type="primary" @click="loadMore">
              加载更多（还有 {{ hiddenCount }} 条 {{ nextBand >= 0 ? `${nextBand} 分以上` : '' }}的结果）
            </el-button>
          </div>
          <div v-else class="load-end">已经到底了 · 已展示 {{ items.length }} 条精排结果</div>
        </div>

        <!-- 空状态（带诊断信息） -->
        <div v-else-if="hasSearched" class="empty-area">
          <el-empty :description="emptyDesc" />
          <div v-if="diagnostics" class="empty-diag">
            召回方式：{{ diagModeText }} · 候选 {{ diagnostics.candidate_count }} 条 · 最高分 {{ diagnostics.top_score }}
            <template v-if="diagnostics.dropped_short?.length"> · 过短词已跳过：{{ diagnostics.dropped_short.join('、') }}</template>
          </div>
          <el-button type="primary" plain size="small" @click="goSearch" class="empty-cta">去高级检索（多条件筛选）</el-button>
        </div>
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
/* 搜索框与按钮分离：四角统一圆角，避免左直角右圆角 */
.search-area :deep(.el-input-group) { align-items: stretch; gap: 10px; }
.search-area :deep(.el-input__wrapper) {
  height: 52px; border-radius: 12px !important;
}
.search-area :deep(.el-input-group__append) {
  padding: 0 !important; display: flex; overflow: hidden;
  border-radius: 12px !important;
}
.search-area :deep(.el-input-group__append .el-button) {
  height: auto; align-self: stretch; margin: 0; padding: 0 24px;
  border: none; border-radius: 12px; font-weight: 600; font-size: 15px;
  color: #fff !important;   /* 否则被占位灰 #909399 覆盖，蓝底上完全看不清 */
}
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

/* ===== 阶段3：条件 chips / 放宽提示 / 诊断 / 分档 ===== */
.condition-chips { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
.chips-label { font-size: 12px; color: var(--ink-500); flex: none; }
.relax-alert { margin-bottom: 10px; }
.diag-line { font-size: 12px; color: var(--ink-400); margin-bottom: 12px; }
.tier-divider { display: flex; align-items: center; gap: 10px; margin: 6px 0 2px; }
.tier-divider::before, .tier-divider::after { content: ''; flex: 1; height: 1px; background: var(--line); }
.tier-divider-text { font-size: 12px; color: var(--ink-400); flex: none; }
.score-badge.mid {
  background: var(--surface-muted);
  border-color: var(--line);
}
.score-badge.mid .score-num { color: var(--ink-600, var(--ink-500)); }
.score-badge.low {
  background: rgba(234, 179, 8, 0.08);
  border-color: rgba(234, 179, 8, 0.35);
}
.score-badge.low .score-num { color: #b45309; }

/* ===== 分档渐进展示：加载更多 / 到底了 ===== */
.load-more { text-align: center; padding: 10px 0 4px; }
.load-more :deep(.el-button) { min-width: 260px; font-size: 13px; }
.load-end {
  text-align: center; padding: 14px 0 6px;
  font-size: 13px; color: var(--ink-400);
}
.load-end::before, .load-end::after {
  content: ''; display: inline-block; width: 56px; height: 1px;
  background: var(--line); vertical-align: middle; margin: 0 12px;
}
.result-snippet {
  font-size: 12px; color: var(--ink-500); line-height: 1.6; margin-bottom: 10px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.empty-area { text-align: center; padding: 8px 0 4px; }
.empty-diag { font-size: 12px; color: var(--ink-400); margin: -8px 0 14px; }
.empty-cta { margin-bottom: 12px; }

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
