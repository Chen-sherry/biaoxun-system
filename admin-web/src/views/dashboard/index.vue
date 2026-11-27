<template>
  <div class="page-container dashboard">
    <div class="dash-head">
      <div>
        <span class="section-kicker">OVERVIEW</span>
        <h1>数据总览</h1>
        <p>标讯平台核心指标实时监控</p>
      </div>
      <div class="dash-time"><span class="status-dot"></span> 实时数据 · {{ today }}</div>
    </div>

    <div class="stat-grid">
      <div class="stat-card" v-for="card in cards" :key="card.title" :style="{ '--c': card.color }">
        <div class="stat-top">
          <span class="stat-icon"><el-icon><component :is="card.icon" /></el-icon></span>
          <el-icon class="stat-trend"><Top /></el-icon>
        </div>
        <div class="value">{{ card.value }}</div>
        <div class="label">{{ card.title }}</div>
        <div class="sub">{{ card.sub }}</div>
        <div class="stat-line"></div>
      </div>
    </div>

    <el-row :gutter="16" style="margin-top: 18px">
      <el-col :xs="24" :span="16">
        <div class="panel-card">
          <div class="panel-head">
            <div><el-icon><TrendCharts /></el-icon><h3>近 7 天标讯新增趋势</h3></div>
            <span class="panel-tag">TREND · 7D</span>
          </div>
          <div ref="chartRef" class="chart"></div>
        </div>
      </el-col>
      <el-col :xs="24" :span="8">
        <div class="panel-card">
          <div class="panel-head">
            <div><el-icon><Clock /></el-icon><h3>最新待审核</h3></div>
            <span class="panel-tag warn">{{ latestPending.length }} 条</span>
          </div>
          <el-table :data="latestPending" size="small" v-loading="loading">
            <el-table-column prop="title" label="标题" show-overflow-tooltip />
            <el-table-column label="操作" width="70">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="$router.push(`/bid/edit/${row.id}`)">处理</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!loading && latestPending.length === 0" description="暂无待审核" :image-size="60" />
        </div>
      </el-col>
    </el-row>

    <!-- AI 用量与成本 -->
    <el-row :gutter="16" style="margin-top: 18px">
      <el-col :span="24">
        <div class="panel-card">
          <div class="panel-head">
            <div><el-icon><Coin /></el-icon><h3>AI 用量与成本</h3></div>
            <span class="panel-tag">TOKENS · 30D</span>
          </div>

          <div class="usage-stats">
            <div class="usage-item" v-for="p in usagePeriods" :key="p.key" :style="{ '--c': p.color }">
              <div class="usage-label">{{ p.label }}</div>
              <div class="usage-value">{{ fmtNum(p.tokens) }}<small> tokens</small></div>
              <div class="usage-sub">{{ p.calls }} 次调用 · 约 ¥{{ p.cost.toFixed(2) }}</div>
              <div class="usage-line"></div>
            </div>
          </div>

          <div class="usage-body">
            <div ref="usageChartRef" class="usage-chart"></div>
            <div class="usage-tags">
              <div class="tags-title">本月按功能<span class="tags-scope">（按 token 排序）</span></div>
              <div class="tag-row" v-for="t in usageTags" :key="t.tag">
                <span class="tag-name">{{ tagLabel(t.tag) }}</span>
                <div class="tag-bar"><i :style="{ width: t.pct + '%' }"></i></div>
                <span class="tag-num">{{ fmtNum(t.total_tokens) }}</span>
                <span class="tag-cost">¥{{ t.est_cost.toFixed(2) }}</span>
              </div>
              <el-empty v-if="!usageTags.length" description="本月还没有 AI 调用" :image-size="50" />
            </div>
          </div>

          <div class="usage-foot">
            估算值（按 Qwen 价目）：输入 ¥{{ pricing.input_per_m }}/M · 输出 ¥{{ pricing.output_per_m }}/M，仅统计接通统一 LLM 层的调用
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { Tickets, TrendCharts, Warning, Connection, Top, Clock, Coin } from '@element-plus/icons-vue'
import { fetchStatsOverview, fetchAIUsage } from '@/api'

const chartRef = ref<HTMLElement | null>(null)
const usageChartRef = ref<HTMLElement | null>(null)
const loading = ref(false)
const overview = ref<any>(null)
const usage = ref<any>(null)
const today = new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })

const cards = computed(() => {
  const c = overview.value?.cards || {}
  return [
    { title: '标讯总量', value: (c.total_bids ?? 0).toLocaleString(), sub: `已发布 ${c.published ?? 0}`, color: '#0ea5e9', icon: Tickets },
    { title: '今日新增', value: c.today_new ?? 0, sub: '今日录入', color: '#10b981', icon: TrendCharts },
    { title: '待审核', value: c.pending ?? 0, sub: '请尽快处理', color: '#f59e0b', icon: Warning },
    { title: '启用采集源', value: `${c.sources_enabled ?? 0}/${c.sources_total ?? 0}`, sub: '定时抓取', color: '#818cf8', icon: Connection },
  ]
})

const latestPending = computed(() => overview.value?.latest_pending || [])

// ---------- AI 用量 ----------
const TAG_LABELS: Record<string, string> = {
  chat: '悬浮球对话',
  stream: '悬浮球对话(流式)',
  translate: '检索·转译',
  score: '检索·打分',
  push: '推送文案',
  extract: '字段补提取',
  match: '智能匹配(已停用)',
  admin_prompt_try: '后台试运行',
}

const pricing = computed(() => usage.value?.pricing || { input_per_m: 0.3, output_per_m: 0.6 })

const usagePeriods = computed(() => {
  const s = usage.value?.summary || {}
  return [
    { key: 'today', label: '今日', color: '#0ea5e9', ...pick(s.today) },
    { key: 'week', label: '本周（周一起）', color: '#10b981', ...pick(s.week) },
    { key: 'month', label: '本月', color: '#818cf8', ...pick(s.month) },
  ]
})

function pick(p: any) {
  return { tokens: p?.total_tokens ?? 0, calls: p?.calls ?? 0, cost: p?.est_cost ?? 0 }
}

const usageTags = computed(() => {
  const list = usage.value?.by_tag || []
  const max = list.length ? (list[0].total_tokens || 1) : 1
  const top = list.slice(0, 6)
  return top.map((t: any) => ({ ...t, pct: Math.max(2, Math.round(t.total_tokens / max * 100)) }))
})

const tagLabel = (t: string) => TAG_LABELS[t] || t

function fmtNum(n: number) {
  if (n == null) return '0'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}

function renderUsageChart(series: any[]) {
  if (!usageChartRef.value || !series?.length) return
  const chart = echarts.init(usageChartRef.value)
  chart.setOption({
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#0d1e38',
      borderColor: 'rgba(56,189,248,0.35)',
      textStyle: { color: '#e8f2ff' },
      formatter: (ps: any[]) => {
        const p = ps[0]
        const row = series[p.dataIndex] || {}
        return `${p.axisValue}<br/>tokens：<b>${(row.total_tokens || 0).toLocaleString()}</b><br/>调用：${row.calls || 0} 次`
      },
    },
    grid: { left: 12, right: 16, top: 20, bottom: 8, containLabel: true },
    xAxis: {
      type: 'category', data: series.map((t: any) => t.date),
      axisLine: { lineStyle: { color: '#dbe6f2' } },
      axisTick: { show: false },
      axisLabel: { color: '#64748b', fontSize: 11, interval: 4 },
    },
    yAxis: {
      type: 'value', minInterval: 1,
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: '#64748b', fontSize: 11 },
      splitLine: { lineStyle: { color: '#eef4fb' } },
    },
    series: [{
      name: 'tokens', type: 'line', smooth: true, symbolSize: 5,
      lineStyle: { width: 2, color: '#38bdf8' },
      itemStyle: { color: '#0ea5e9' },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(56,189,248,0.28)' },
          { offset: 1, color: 'rgba(56,189,248,0.02)' },
        ]),
      },
      data: series.map((t: any) => t.total_tokens),
    }],
  })
}

async function loadUsage() {
  try {
    usage.value = await fetchAIUsage()
    renderUsageChart(usage.value?.series_30d || [])
  } catch { /* 统计失败不影响总览 */ }
}

function renderChart(trend: any[]) {
  if (!chartRef.value || !trend?.length) return
  const chart = echarts.init(chartRef.value)
  chart.setOption({
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#0d1e38',
      borderColor: 'rgba(56,189,248,0.35)',
      textStyle: { color: '#e8f2ff' },
      axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(56,189,248,0.08)' } },
    },
    grid: { left: 12, right: 16, top: 28, bottom: 8, containLabel: true },
    xAxis: {
      type: 'category', data: trend.map((t: any) => t.date),
      axisLine: { lineStyle: { color: '#dbe6f2' } },
      axisTick: { show: false },
      axisLabel: { color: '#64748b', fontSize: 12 },
    },
    yAxis: {
      type: 'value', minInterval: 1,
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: '#64748b', fontSize: 12 },
      splitLine: { lineStyle: { color: '#eef4fb' } },
    },
    series: [{
      name: '新增数量', type: 'bar', barWidth: '46%',
      itemStyle: {
        borderRadius: [5, 5, 0, 0],
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#38bdf8' },
          { offset: 1, color: '#0284c7' },
        ]),
        shadowColor: 'rgba(14,165,233,0.25)', shadowBlur: 12, shadowOffsetY: 4,
      },
      emphasis: { itemStyle: { color: '#22d3ee' } },
      data: trend.map((t: any) => t.count),
    }],
  })
}

async function loadStats() {
  loading.value = true
  try {
    overview.value = await fetchStatsOverview()
    renderChart(overview.value?.trend_7d || [])
  } finally { loading.value = false }
}

onMounted(() => {
  loadStats()
  loadUsage()
})
</script>

<style scoped>
.dashboard { padding: 22px 20px; }
.dash-head { display: flex; align-items: flex-end; justify-content: space-between; margin-bottom: 22px; }
.dash-head h1 { font-size: 26px; font-weight: 800; color: var(--ink-900); margin: 8px 0 4px; }
.dash-head p { color: var(--ink-500); font-size: 14px; margin: 0; }
.dash-time {
  display: inline-flex; align-items: center; gap: 8px; font-size: 12px; color: var(--ink-500);
  padding: 7px 14px; border-radius: 999px; background: var(--surface); border: 1px solid var(--line);
}
.status-dot { width: 7px; height: 7px; border-radius: 50%; background: #34d399; box-shadow: 0 0 8px rgba(52,211,153,0.7); }

.stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.stat-card {
  position: relative; overflow: hidden;
  background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--r-md); padding: 18px 20px 16px;
  box-shadow: var(--shadow-card); transition: transform 0.35s var(--ease), box-shadow 0.35s var(--ease);
}
.stat-card:hover { transform: translateY(-3px); box-shadow: var(--shadow-hover); }
.stat-top { display: flex; align-items: flex-start; justify-content: space-between; }
.stat-icon {
  width: 42px; height: 42px; border-radius: 11px; display: grid; place-items: center; font-size: 19px;
  color: var(--c); background: color-mix(in srgb, var(--c) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--c) 26%, transparent);
}
.stat-trend { color: var(--c); font-size: 15px; opacity: 0.6; }
.value { font-size: 30px; font-weight: 800; color: var(--ink-900); margin-top: 14px; line-height: 1; font-variant-numeric: tabular-nums; }
.label { font-size: 14px; color: var(--ink-700); font-weight: 600; margin-top: 8px; }
.sub { font-size: 12px; color: var(--ink-400); margin-top: 2px; }
.stat-line { position: absolute; left: 0; bottom: 0; height: 3px; width: 100%; background: linear-gradient(90deg, var(--c), transparent); opacity: 0.75; }

.panel-card {
  background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--r-md); padding: 18px 20px; box-shadow: var(--shadow-card);
}
.panel-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.panel-head > div { display: flex; align-items: center; gap: 9px; }
.panel-head :deep(.el-icon) { color: var(--accent-strong); font-size: 18px; }
.panel-head h3 { margin: 0; font-size: 16px; font-weight: 700; color: var(--ink-900); }
.panel-tag {
  font-size: 11px; font-weight: 700; letter-spacing: 1px; color: var(--accent-deep);
  padding: 4px 10px; border-radius: 999px; background: var(--accent-soft); border: 1px solid var(--accent-line);
}
.panel-tag.warn { color: #d97706; background: rgba(245, 158, 11, 0.1); border-color: rgba(245, 158, 11, 0.25); }
.chart { height: 300px; width: 100%; }

/* ===== AI 用量卡片 ===== */
.usage-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 18px; }
.usage-item {
  position: relative; overflow: hidden;
  border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px 12px;
  background: color-mix(in srgb, var(--c) 4%, var(--surface));
}
.usage-label { font-size: 12.5px; color: var(--ink-500); font-weight: 600; }
.usage-value { font-size: 24px; font-weight: 800; color: var(--ink-900); margin-top: 6px; font-variant-numeric: tabular-nums; }
.usage-value small { font-size: 12px; font-weight: 600; color: var(--ink-400); }
.usage-sub { font-size: 12px; color: var(--ink-400); margin-top: 4px; }
.usage-line { position: absolute; left: 0; bottom: 0; height: 3px; width: 100%; background: linear-gradient(90deg, var(--c), transparent); opacity: .7; }

.usage-body { display: grid; grid-template-columns: 1fr 340px; gap: 22px; align-items: stretch; }
.usage-chart { height: 220px; width: 100%; }
.usage-tags { border-left: 1px dashed var(--line); padding-left: 18px; }
.tags-title { font-size: 13px; font-weight: 700; color: var(--ink-700); margin-bottom: 12px; }
.tags-scope { font-weight: 400; font-size: 11.5px; color: var(--ink-400); }
.tag-row { display: flex; align-items: center; gap: 8px; margin-bottom: 9px; font-size: 12.5px; }
.tag-name { width: 96px; flex-shrink: 0; color: var(--ink-700); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tag-bar { flex: 1; height: 7px; border-radius: 999px; background: #eef4fb; overflow: hidden; }
.tag-bar i { display: block; height: 100%; border-radius: 999px; background: linear-gradient(90deg, #38bdf8, #6366f1); }
.tag-num { width: 58px; text-align: right; color: var(--ink-700); font-variant-numeric: tabular-nums; }
.tag-cost { width: 52px; text-align: right; color: var(--ink-400); font-variant-numeric: tabular-nums; }
.usage-foot { margin-top: 14px; padding-top: 12px; border-top: 1px dashed var(--line); font-size: 11.5px; color: var(--ink-400); }

@media (max-width: 1200px) { .stat-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 900px) {
  .usage-body { grid-template-columns: 1fr; }
  .usage-tags { border-left: none; padding-left: 0; border-top: 1px dashed var(--line); padding-top: 14px; }
}
@media (max-width: 768px) {
  .dashboard { padding: 14px 12px; }
  .dash-head h1 { font-size: 21px; }
  .dash-time { display: none; }
  .stat-grid { grid-template-columns: repeat(2, 1fr); gap: 12px; }
  .value { font-size: 24px; }
  .chart { height: 260px; }
  .usage-stats { grid-template-columns: 1fr; }
  .usage-chart { height: 180px; }
}
</style>
