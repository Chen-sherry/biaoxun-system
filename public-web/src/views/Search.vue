<template>
  <div class="search-page">
    <div class="page-head">
      <span class="section-kicker">ADVANCED SEARCH</span>
      <h1>高级检索</h1>
      <p>多条件精确筛选，快速定位目标标讯</p>
    </div>

    <div class="search-bar tech-card">
      <el-input v-model="keyword" size="large" placeholder="输入关键词..." @keyup.enter="loadData" clearable>
        <template #append><el-button :icon="Search" type="primary" @click="loadData">搜索</el-button></template>
      </el-input>
    </div>

    <div class="filter-row tech-card">
      <el-form :inline="true" :model="filter">
        <el-form-item label="公告类型">
          <el-select v-model="filter.notice_type_id" clearable placeholder="全部" style="width:140px">
            <el-option v-for="t in noticeTypes" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="地区代码">
          <el-input v-model="filter.region_code" placeholder="如 110000" clearable style="width:120px" />
        </el-form-item>
        <el-form-item label="客群">
          <el-select v-model="filter.customer_group" clearable placeholder="全部" style="width:110px">
            <el-option label="政务" value="政务" />
            <el-option label="国企" value="国企" />
            <el-option label="民企" value="民企" />
          </el-select>
        </el-form-item>
        <el-form-item label="发布日期">
          <el-date-picker v-model="filter.date_range" type="daterange" start-placeholder="开始" end-placeholder="结束" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="中标日期">
          <el-date-picker v-model="filter.winner_date_range" type="daterange" start-placeholder="开始" end-placeholder="结束" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="loadData">查询</el-button>
          <el-button @click="reset">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="result-bar">
      <el-icon><DataLine /></el-icon> 共 <b>{{ total }}</b> 条标讯
    </div>

    <div v-loading="loading" class="result-list">
      <div v-for="b in list" :key="b.id" class="result-item tech-card" @click="$router.push(`/bid/${b.id}`)">
        <div class="result-accent"></div>
        <div class="result-main">
          <h3 class="result-title">{{ b.title }}</h3>
          <div class="result-meta">
            <el-tag v-if="b.notice_type" size="small" type="primary" effect="dark">{{ b.notice_type }}</el-tag>
            <span><el-icon><Calendar /></el-icon> {{ formatTime(b.publish_time) }}</span>
            <span v-if="b.region_name"><el-icon><Location /></el-icon> {{ b.region_name }}</span>
            <span><el-icon><View /></el-icon> {{ b.view_count }}</span>
          </div>
          <div v-if="b.tenderee" class="result-sub">
            <el-icon><OfficeBuilding /></el-icon> 采购人：{{ b.tenderee }}
            <template v-if="b.winner_unit"> · 中标单位：{{ b.winner_unit }}</template>
            <template v-if="b.win_amount"> · 中标金额：<b class="amount">¥{{ b.win_amount?.toLocaleString() }}</b></template>
          </div>
        </div>
        <el-icon class="result-arrow"><Right /></el-icon>
      </div>
      <el-empty v-if="!loading && list.length === 0" description="暂无匹配的标讯" :image="emptyArt" :image-size="180" />
    </div>

    <div class="pagination-wrap">
      <el-pagination v-if="total > 0" v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[10,20,30,50]" layout="total, sizes, prev, pager, next" @size-change="loadData" @current-change="loadData" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search, DataLine, Calendar, Location, View, OfficeBuilding, Right } from '@element-plus/icons-vue'
import emptyArt from '@/assets/brand/empty-state.svg'
import { fetchPublicBids, fetchPublicNoticeTypes } from '@/api'

const route = useRoute()
const router = useRouter()
const keyword = ref((route.query.kw as string) || '')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const list = ref<any[]>([])
const loading = ref(false)
const noticeTypes = ref<any[]>([])
const filter = reactive({
  notice_type_id: (route.query.notice_type_id ? Number(route.query.notice_type_id) : null) as number | null,
  customer_group: (route.query.customer_group as string) || '',
  date_range: null as any,
  winner_date_range: null as any,
  region_code: (route.query.region_code as string) || '',
})

// 从 route.query 读取日期区间，兼容 Home 页推过来的 date_from/date_to
function hydrateFilterFromQuery() {
  const q = route.query
  if (q.date_from && q.date_to) {
    filter.date_range = [q.date_from, q.date_to]
  }
  if (q.winner_date_from && q.winner_date_to) {
    filter.winner_date_range = [q.winner_date_from, q.winner_date_to]
  }
  if (q.notice_type_id) filter.notice_type_id = Number(q.notice_type_id)
  if (q.customer_group) filter.customer_group = q.customer_group as string
  if (q.region_code) filter.region_code = q.region_code as string
  if (q.kw) keyword.value = q.kw as string
}
hydrateFilterFromQuery()

function formatTime(t: any) { return t ? String(t).replace('T',' ').slice(0,10) : '' }

async function loadData() {
  loading.value = true
  try {
    const q: any = { page: page.value, page_size: pageSize.value, keyword: keyword.value || undefined }
    if (filter.notice_type_id) q.notice_type_id = filter.notice_type_id
    if (filter.customer_group) q.customer_group = filter.customer_group
    if (filter.region_code) q.region_code = filter.region_code
    if (filter.date_range) { q.date_from = filter.date_range[0]; q.date_to = filter.date_range[1] }
    if (filter.winner_date_range) { q.winner_date_from = filter.winner_date_range[0]; q.winner_date_to = filter.winner_date_range[1] }
    const data = await fetchPublicBids(q)
    list.value = data.items || []
    total.value = data.total || 0
  } finally { loading.value = false }
}
function reset() {
  keyword.value = ''; filter.notice_type_id = null
  filter.customer_group = ''; filter.date_range = null; filter.winner_date_range = null
  filter.region_code = ''; page.value = 1; loadData()
}

// 路由 query 变化 → 重新灌入筛选条件 + 刷新
watch(() => route.fullPath, () => {
  hydrateFilterFromQuery()
  page.value = 1
  loadData()
})

onMounted(async () => {
  try { noticeTypes.value = await fetchPublicNoticeTypes() } catch {}
  loadData()
})
</script>

<style scoped>
.search-page { max-width: 1200px; margin: 28px auto; padding: 0 24px 20px; }
.page-head { margin-bottom: 22px; }
.page-head h1 { font-size: 28px; font-weight: 800; color: var(--ink-900); margin: 8px 0 4px; }
.page-head p { color: var(--ink-500); font-size: 14px; }
.search-bar { max-width: 720px; margin: 0 auto 16px; padding: 8px; }
.filter-row { padding: 16px; margin-bottom: 16px; }
.result-bar {
  color: var(--ink-500); font-size: 13px; margin-bottom: 14px;
  display: flex; align-items: center; gap: 7px;
}
.result-bar :deep(.el-icon) { color: var(--accent-strong); }
.result-bar b { color: var(--accent-deep); font-size: 16px; }
.result-list { display: flex; flex-direction: column; gap: 12px; }
.result-item {
  position: relative; padding: 18px 22px; cursor: pointer;
  display: flex; align-items: center; gap: 16px; overflow: hidden;
}
.result-accent {
  position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
  background: linear-gradient(var(--accent), var(--accent-cyan));
  transform: scaleY(0); transition: transform 0.35s var(--ease);
}
.result-item:hover .result-accent { transform: scaleY(1); }
.result-item:hover { border-color: var(--accent-line); }
.result-main { flex: 1; min-width: 0; }
.result-title {
  margin: 0 0 10px; font-size: 16px; font-weight: 600; color: var(--ink-900); line-height: 1.5;
  transition: color 0.25s;
}
.result-item:hover .result-title { color: var(--accent-deep); }
.result-meta { display: flex; gap: 14px; align-items: center; color: var(--ink-500); font-size: 13px; flex-wrap: wrap; }
.result-meta span { display: inline-flex; align-items: center; gap: 4px; }
.result-sub { margin-top: 8px; color: var(--ink-700); font-size: 13px; display: flex; align-items: center; flex-wrap: wrap; gap: 2px; }
.result-sub .amount { color: var(--danger); font-weight: 700; }
.result-arrow { color: var(--line-strong); font-size: 18px; flex: none; transition: all 0.3s var(--ease); }
.result-item:hover .result-arrow { color: var(--accent); transform: translateX(3px); }
.pagination-wrap { display: flex; justify-content: center; margin-top: 26px; }

/* ===== 移动端（≤768px）：筛选表单竖排，保留原逻辑 ===== */
@media (max-width: 768px) {
  .search-page { margin: 16px auto; padding: 0 12px 16px; }
  .page-head h1 { font-size: 22px; }
  .filter-row { padding: 12px; }
  .filter-row :deep(.el-form--inline) { display: flex; flex-direction: column; }
  .filter-row :deep(.el-form--inline .el-form-item) { display: flex; width: 100%; margin: 0 0 10px; }
  .filter-row :deep(.el-form--inline .el-form-item__label) { width: auto; padding-right: 8px; }
  .filter-row :deep(.el-form-item__content) { flex: 1; min-width: 0; }
  .filter-row :deep(.el-input),
  .filter-row :deep(.el-select),
  .filter-row :deep(.el-date-editor) { width: 100% !important; }
  .result-item { padding: 14px; }
  .result-title { font-size: 15px; }
  .result-arrow { display: none; }
  .pagination-wrap :deep(.el-pagination) { flex-wrap: wrap; justify-content: center; row-gap: 8px; }
}
</style>
