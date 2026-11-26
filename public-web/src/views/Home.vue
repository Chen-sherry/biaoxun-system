<template>
  <div class="home-page">
    <!-- Hero 区：大搜索框 + 高级筛选 -->
    <section class="hero">
      <div class="hero-grid" aria-hidden="true"></div>
      <div class="hero-glow" aria-hidden="true"></div>
      <img class="hero-art" :src="heroArt" alt="" aria-hidden="true" />
      <div class="hero-inner">
        <div class="hero-copy">
          <span class="hero-kicker"><el-icon><DataLine /></el-icon> BID INTELLIGENCE PLATFORM</span>
          <h1 class="hero-title">全国标讯 · 智能搜索</h1>
          <p class="hero-sub">聚合公共资源交易平台、政府采购网、招投标公告，AI 语义匹配 + 多条件精准筛选</p>

          <!-- AI 搜索框常驻 -->
          <div class="ai-search-box">
            <el-input
              v-model="aiKeyword"
              size="large"
              placeholder="试试：帮我找培训场地相关的招标公告"
              @keyup.enter="onAiSearch"
              clearable
            >
              <template #prefix><el-icon><MagicStick /></el-icon></template>
              <template #append>
                <el-button :icon="MagicStick" type="primary" @click="onAiSearch">智能检索</el-button>
              </template>
            </el-input>
          </div>

          <!-- 折叠式高级筛选面板 -->
          <el-collapse v-model="filterOpen" class="filter-panel" :expand-icon-position="'start'">
            <el-collapse-item name="open">
              <template #title>
                <span class="filter-title"><el-icon><Operation /></el-icon> 高级筛选（点击展开 / 收起）</span>
              </template>
              <el-row :gutter="16">
                <el-col :xs="24" :sm="12" :span="8">
                  <el-form-item label="公告类型">
                    <el-select v-model="filter.notice_type_id" clearable placeholder="全部" style="width:100%">
                      <el-option v-for="t in noticeTypes" :key="t.id" :label="t.name" :value="t.id" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12" :span="8">
                  <el-form-item label="地区代码">
                    <el-input v-model="filter.region_code" placeholder="如 110000" clearable />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12" :span="8">
                  <el-form-item label="客群">
                    <el-select v-model="filter.customer_group" clearable placeholder="全部" style="width:100%">
                      <el-option label="政务" value="政务" />
                      <el-option label="国企" value="国企" />
                      <el-option label="民企" value="民企" />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="16">
                <el-col :xs="24" :sm="12" :span="12">
                  <el-form-item label="发布时间范围">
                    <el-date-picker v-model="filter.date_range" type="daterange" start-placeholder="开始" end-placeholder="结束" value-format="YYYY-MM-DD" style="width:100%" />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12" :span="12">
                  <el-form-item label="中标时间范围">
                    <el-date-picker v-model="filter.winner_date_range" type="daterange" start-placeholder="开始" end-placeholder="结束" value-format="YYYY-MM-DD" style="width:100%" />
                  </el-form-item>
                </el-col>
              </el-row>
              <div style="text-align:right; display:flex; gap:12px; justify-content:flex-end">
                <el-button @click="resetFilter">重置</el-button>
                <el-button type="primary" @click="onTraditionalSearch">应用筛选 <el-icon><Right /></el-icon></el-button>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>
      </div>
      <!-- 底部渐变过渡 -->
      <div class="hero-fade" aria-hidden="true"></div>
    </section>

    <!-- 门户统计 -->
    <section class="stats-bar">
      <div class="stat-item" v-for="(stat, idx) in statCards" :key="stat.label">
        <span class="stat-icon" :style="{ '--i-color': stat.color }"><el-icon><component :is="stat.icon" /></el-icon></span>
        <div class="stat-text">
          <div class="stat-num">{{ stat.value }}</div>
          <div class="stat-label">{{ stat.label }}</div>
        </div>
        <span class="stat-index">0{{ idx + 1 }}</span>
      </div>
    </section>

    <!-- 热门标讯列表 -->
    <section class="content-section">
      <div class="section-header">
        <div>
          <span class="section-kicker">LATEST BIDS</span>
          <h2><el-icon><TrendCharts /></el-icon> 最新标讯</h2>
        </div>
        <el-button text type="primary" @click="$router.push('/search')">查看全部 <el-icon><Right /></el-icon></el-button>
      </div>
      <el-row :gutter="16">
        <el-col v-for="b in hotBids" :key="b.id" :xs="24" :sm="12" :span="12" style="margin-bottom:14px">
          <div class="bid-card" @click="$router.push(`/bid/${b.id}`)">
            <div class="bid-card-top">
              <span class="bid-idx">#{{ String(b.id).slice(-4) }}</span>
              <span class="bid-arrow"><el-icon><Right /></el-icon></span>
            </div>
            <div class="bid-title">{{ b.title }}</div>
            <div class="bid-meta">
              <el-tag v-if="b.notice_type" size="small" type="primary" effect="dark">{{ b.notice_type }}</el-tag>
              <span><el-icon><Calendar /></el-icon> {{ formatTime(b.publish_time) }}</span>
              <span v-if="b.region_name"><el-icon><Location /></el-icon> {{ b.region_name }}</span>
            </div>
            <div class="bid-sub" v-if="b.tenderee"><el-icon><OfficeBuilding /></el-icon> 采购人：{{ b.tenderee }}</div>
          </div>
        </el-col>
      </el-row>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, reactive, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { MagicStick, Operation, Right, DataLine, TrendCharts, Calendar, Location, OfficeBuilding, Tickets, Refresh, Connection, Clock } from '@element-plus/icons-vue'
import axios from 'axios'
import heroArt from '@/assets/brand/hero-illustration.svg'
import { fetchPublicHot, fetchPortalStats, fetchPublicNoticeTypes } from '@/api'

const router = useRouter()
const aiKeyword = ref('')
const filterOpen = ref<string[]>([])  // 默认收起，点击展开
const noticeTypes = ref<any[]>([])
const hotBids = ref<any[]>([])
const stats = reactive({ total_bids: 0, today_new: 0, sources_enabled: 0 })

// ===== 服务器时钟：取服务器 Date 头做基准，本地每秒自增，每 3 分钟重新同步 =====
const clockText = ref('--:--:--')
let clockOffset = 0            // 服务器时间 - 本地时间（毫秒）
let tickTimer: number | null = null
let syncTimer: number | null = null

const pad2 = (n: number) => String(n).padStart(2, '0')
function renderClock() {
  const d = new Date(Date.now() + clockOffset)
  clockText.value = `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`
}
async function syncServerClock() {
  try {
    const resp = await axios.head(import.meta.env.BASE_URL, { timeout: 8000 })
    const raw = (resp.headers as any)?.date ?? (resp.headers as any)?.Date
    const serverMs = raw ? Date.parse(raw) : NaN
    if (!isNaN(serverMs)) clockOffset = serverMs - Date.now()
  } catch { /* 同步失败则沿用上次偏移，本地继续走时 */ }
  renderClock()
}

const statCards = computed(() => [
  { label: '累计标讯', value: stats.total_bids.toLocaleString(), icon: Tickets, color: '#38bdf8' },
  { label: '今日新增', value: stats.today_new.toLocaleString(), icon: TrendCharts, color: '#22d3ee' },
  { label: '实时更新中', value: clockText.value, icon: Clock, color: '#10b981' },
  { label: '启用采集源', value: stats.sources_enabled, icon: Connection, color: '#818cf8' },
])

const filter = reactive({
  notice_type_id: null as number | null,
  region_code: '',
  customer_group: '',
  date_range: null as any,
  winner_date_range: null as any,
})

function onAiSearch() {
  if (!aiKeyword.value.trim()) { router.push('/ai-match'); return }
  // 整句传给 AI 检索页，由后端转译（不再本地拆词）
  router.push({ path: '/ai-match', query: { q: aiKeyword.value.trim() } })
}
function onTraditionalSearch() {
  const q: any = {}
  if (aiKeyword.value.trim()) q.kw = aiKeyword.value.trim()
  if (filter.notice_type_id) q.notice_type_id = filter.notice_type_id
  if (filter.region_code) q.region_code = filter.region_code
  if (filter.customer_group) q.customer_group = filter.customer_group
  if (filter.date_range) { q.date_from = filter.date_range[0]; q.date_to = filter.date_range[1] }
  if (filter.winner_date_range) { q.winner_date_from = filter.winner_date_range[0]; q.winner_date_to = filter.winner_date_range[1] }
  router.push({ name: 'search', query: q })
}
function resetFilter() {
  filter.notice_type_id = null; filter.region_code = ''
  filter.customer_group = ''; filter.date_range = null; filter.winner_date_range = null
}
function formatTime(t: any) {
  if (!t) return ''
  return String(t).replace('T', ' ').slice(0, 10)
}

onMounted(async () => {
  // 服务器时钟：先同步一次基准，之后本地每秒自增、每 3 分钟重新对时
  syncServerClock()
  renderClock()
  tickTimer = window.setInterval(renderClock, 1000)
  syncTimer = window.setInterval(syncServerClock, 3 * 60 * 1000)

  try {
    const [hot, s, nts] = await Promise.all([
      fetchPublicHot(16), fetchPortalStats(), fetchPublicNoticeTypes(),
    ])
    hotBids.value = hot
    Object.assign(stats, s)
    noticeTypes.value = nts || []
  } catch (e) { console.error(e) }
})

onUnmounted(() => {
  if (tickTimer) clearInterval(tickTimer)
  if (syncTimer) clearInterval(syncTimer)
})
</script>

<style scoped>
.hero {
  position: relative;
  overflow: hidden;
  background: linear-gradient(118deg, var(--brand-950) 0%, var(--brand-850) 48%, #0c2647 100%);
  padding: 56px 24px 64px;
  color: var(--on-dark);
}
.hero-grid {
  position: absolute; inset: 0; pointer-events: none; opacity: 0.85;
  background-image: url('@/assets/brand/bg-grid.svg');
  background-size: 48px 48px;
  mask-image: radial-gradient(ellipse at 60% 40%, #000 30%, transparent 85%);
}
.hero-glow {
  position: absolute; top: -180px; left: -120px; width: 720px; height: 620px; pointer-events: none;
  background-image: url('@/assets/brand/bg-glow.svg');
  background-size: cover; opacity: 0.9; animation: pulse-glow 8s ease-in-out infinite;
}
.hero-art {
  position: absolute; right: -40px; top: 50%; transform: translateY(-52%);
  width: 520px; max-width: 46vw; height: auto; pointer-events: none;
  opacity: 0.95; filter: drop-shadow(0 0 40px rgba(14, 165, 233, 0.18));
  animation: float-slow 9s ease-in-out infinite;
}
.hero-inner { position: relative; z-index: 2; max-width: 920px; margin: 0 auto; }
.hero-copy { max-width: 720px; }
.hero-kicker {
  display: inline-flex; align-items: center; gap: 8px;
  font-size: 12px; font-weight: 700; letter-spacing: 2px; color: var(--accent);
  padding: 5px 12px; border-radius: 999px;
  border: 1px solid rgba(56, 189, 248, 0.3); background: rgba(56, 189, 248, 0.08);
}
.hero-title {
  font-size: 40px; font-weight: 800; letter-spacing: 1px;
  margin: 18px 0 12px; line-height: 1.2; color: #fff;
  text-shadow: 0 4px 24px rgba(0, 0, 0, 0.25);
  animation: fade-up 0.6s var(--ease) both;
}
.hero-sub {
  color: var(--on-dark-soft); margin-bottom: 30px; font-size: 16px; line-height: 1.6;
  animation: fade-up 0.6s 0.08s var(--ease) both;
}
.ai-search-box { max-width: 700px; animation: fade-up 0.6s 0.16s var(--ease) both; }
.ai-search-box :deep(.el-input-group) { align-items: stretch; gap: 10px; }
.ai-search-box :deep(.el-input__wrapper) {
  height: 54px; background: rgba(255, 255, 255, 0.97);
  box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.4) inset, 0 12px 32px rgba(0, 0, 0, 0.2) !important;
  border-radius: 12px !important;
}
.ai-search-box :deep(.el-input-group__append) {
  background: linear-gradient(135deg, var(--accent-strong), var(--accent-deep)) !important;
  border: none !important; border-radius: 12px !important;
  padding: 0 !important; display: flex; overflow: hidden;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.2);
}
.ai-search-box :deep(.el-input-group__append .el-button) {
  color: #fff !important; font-weight: 600; font-size: 15px;
  height: auto; align-self: stretch; margin: 0; padding: 0 26px;
  background: transparent; border: none; border-radius: 12px;
}
.filter-panel {
  max-width: 720px; margin: 20px auto 0 0; background: rgba(255, 255, 255, 0.96);
  border-radius: var(--r-md); padding: 4px 18px; border: 1px solid rgba(255, 255, 255, 0.5);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.18);
}
.filter-title { font-size: 14px; font-weight: 600; color: var(--accent-deep); display: inline-flex; align-items: center; gap: 7px; }
.hero-fade {
  position: absolute; left: 0; right: 0; bottom: -1px; height: 60px; pointer-events: none;
  background: linear-gradient(180deg, transparent, var(--surface-soft));
}

.stats-bar {
  position: relative; z-index: 3;
  max-width: 1200px; margin: -32px auto 30px; padding: 8px 12px;
  background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--r-lg); box-shadow: var(--shadow-hover);
  display: grid; grid-template-columns: repeat(4, 1fr);
}
.stat-item {
  position: relative; display: flex; align-items: center; gap: 14px;
  padding: 16px 20px; border-radius: var(--r-md); transition: background 0.25s;
}
.stat-item:not(:last-child)::after {
  content: ''; position: absolute; right: 0; top: 20%; height: 60%; width: 1px;
  background: linear-gradient(transparent, var(--line-strong), transparent);
}
.stat-item:hover { background: var(--surface-soft); }
.stat-icon {
  flex: none; width: 46px; height: 46px; border-radius: 12px;
  display: grid; place-items: center; font-size: 21px;
  color: var(--i-color);
  background: color-mix(in srgb, var(--i-color) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--i-color) 26%, transparent);
  box-shadow: 0 4px 14px color-mix(in srgb, var(--i-color) 20%, transparent);
}
.stat-num { font-size: 27px; font-weight: 800; color: var(--ink-900); line-height: 1.1; }
.stat-label { font-size: 13px; color: var(--ink-500); margin-top: 3px; }
.stat-index {
  position: absolute; top: 10px; right: 14px; font-size: 11px; font-weight: 700;
  color: var(--line-strong); font-variant-numeric: tabular-nums;
}

.content-section { max-width: 1200px; margin: 0 auto; padding: 0 24px 8px; }
.section-header { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 18px; }
.section-header h2 {
  margin: 6px 0 0; font-size: 22px; font-weight: 700; color: var(--ink-900);
  display: flex; align-items: center; gap: 9px;
}
.section-header h2 :deep(.el-icon) { color: var(--accent-strong); }
.section-header :deep(.el-button) { font-weight: 600; }

.bid-card {
  position: relative; height: 100%; cursor: pointer;
  background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--r-md); padding: 18px 18px 16px;
  box-shadow: var(--shadow-card);
  transition: transform 0.35s var(--ease), box-shadow 0.35s var(--ease), border-color 0.35s var(--ease);
  overflow: hidden;
}
.bid-card::before {
  content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
  background: linear-gradient(var(--accent), var(--accent-cyan));
  transform: scaleY(0); transform-origin: center; transition: transform 0.35s var(--ease);
}
.bid-card:hover { transform: translateY(-4px); border-color: var(--accent-line); box-shadow: var(--shadow-hover); }
.bid-card:hover::before { transform: scaleY(1); }
.bid-card-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.bid-idx { font-size: 11px; font-weight: 700; letter-spacing: 1px; color: var(--accent-deep); font-variant-numeric: tabular-nums; }
.bid-arrow {
  width: 24px; height: 24px; border-radius: 50%; display: grid; place-items: center;
  color: var(--ink-400); background: var(--surface-soft); transition: all 0.3s var(--ease);
}
.bid-card:hover .bid-arrow { background: var(--accent); color: #fff; transform: translateX(2px); box-shadow: 0 0 12px var(--accent-glow); }
.bid-title {
  font-size: 15px; font-weight: 600; color: var(--ink-900); line-height: 1.5; margin-bottom: 12px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.bid-meta { font-size: 12px; color: var(--ink-500); display: flex; gap: 12px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }
.bid-meta span { display: inline-flex; align-items: center; gap: 3px; }
.bid-sub { font-size: 12px; color: var(--ink-700); display: flex; align-items: center; gap: 5px; }

/* ===== 移动端（≤768px）保留原有响应式断点 ===== */
@media (max-width: 1024px) {
  .hero-art { opacity: 0.35; right: -80px; }
  .hero-title { font-size: 32px; }
}
@media (max-width: 768px) {
  .hero { padding: 36px 14px 48px; }
  .hero-art { display: none; }
  .hero-kicker { font-size: 10px; letter-spacing: 1px; }
  .hero-title { font-size: 25px; margin: 14px 0 10px; }
  .hero-sub { font-size: 14px; margin-bottom: 22px; }
  .ai-search-box :deep(.el-input__wrapper) { height: 48px; }
  .ai-search-box :deep(.el-input-group__append .el-button) { height: 48px; font-size: 13px; }
  .filter-panel { max-width: 100%; padding: 4px 10px; }
  .stats-bar { grid-template-columns: repeat(2, 1fr); gap: 4px; margin-top: -22px; padding: 6px; }
  .stat-item { padding: 12px; gap: 10px; }
  .stat-icon { width: 38px; height: 38px; font-size: 17px; }
  .stat-num { font-size: 21px; }
  .stat-index { display: none; }
  .content-section { padding: 0 14px 8px; }
  .section-header h2 { font-size: 18px; }
}
</style>
