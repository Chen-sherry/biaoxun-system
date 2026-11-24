<template>
  <div class="page-container">
    <div class="page-card">
      <el-row :gutter="16">
        <el-col :span="6" v-for="card in cards" :key="card.title">
          <div class="stat-card" :style="{ borderTop: `4px solid ${card.color}` }">
            <div class="label">{{ card.title }}</div>
            <div class="value">{{ card.value }}</div>
            <div class="sub">{{ card.sub }}</div>
          </div>
        </el-col>
      </el-row>
    </div>

    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="16">
        <div class="page-card">
          <h3 class="card-title">近 7 天标讯新增趋势</h3>
          <div ref="chartRef" style="height: 300px"></div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="page-card">
          <h3 class="card-title">最新待审核</h3>
          <el-table :data="latestPending" size="small" stripe v-loading="loading">
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
import { fetchStatsOverview } from '@/api'

const chartRef = ref<HTMLElement | null>(null)
const loading = ref(false)
const overview = ref<any>(null)

const cards = computed(() => {
  const c = overview.value?.cards || {}
  return [
    { title: '标讯总量', value: c.total_bids ?? 0, sub: `已发布 ${c.published ?? 0}`, color: '#409eff' },
    { title: '今日新增', value: c.today_new ?? 0, sub: '今日录入', color: '#67c23a' },
    { title: '待审核',   value: c.pending ?? 0, sub: '请尽快处理', color: '#e6a23c' },
    { title: '启用采集源', value: `${c.sources_enabled ?? 0}/${c.sources_total ?? 0}`, sub: '定时抓取', color: '#909399' },
  ]
})

const latestPending = computed(() => overview.value?.latest_pending || [])

function renderChart(trend: any[]) {
  if (!chartRef.value || !trend?.length) return
  const chart = echarts.init(chartRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: trend.map((t: any) => t.date) },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{
      name: '新增数量',
      type: 'bar',
      smooth: true,
      barWidth: 20,
      itemStyle: { borderRadius: [4, 4, 0, 0], color: '#409eff' },
      data: trend.map((t: any) => t.count),
    }],
  })
}

async function loadStats() {
  loading.value = true
  try {
    overview.value = await fetchStatsOverview()
    renderChart(overview.value?.trend_7d || [])
  } finally {
    loading.value = false
  }
}

onMounted(loadStats)
</script>

<style scoped>
.stat-card {
  background: #fff;
  border-radius: 6px;
  padding: 20px 24px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}
.label { color: #909399; font-size: 14px; }
.value { font-size: 32px; font-weight: 700; color: #303133; margin-top: 4px; }
.sub { color: #c0c4cc; font-size: 12px; margin-top: 4px; }
.card-title { margin: 0 0 16px; font-size: 16px; color: #303133; }
</style>
