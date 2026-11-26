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
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { Tickets, TrendCharts, Warning, Connection, Top, Clock } from '@element-plus/icons-vue'
import { fetchStatsOverview } from '@/api'

const chartRef = ref<HTMLElement | null>(null)
const loading = ref(false)
const overview = ref<any>(null)
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

onMounted(loadStats)
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

@media (max-width: 1200px) { .stat-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 768px) {
  .dashboard { padding: 14px 12px; }
  .dash-head h1 { font-size: 21px; }
  .dash-time { display: none; }
  .stat-grid { grid-template-columns: repeat(2, 1fr); gap: 12px; }
  .value { font-size: 24px; }
  .chart { height: 260px; }
}
</style>
