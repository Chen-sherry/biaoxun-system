<template>
  <div class="search-page">
    <div class="search-bar">
      <el-input v-model="keyword" size="large" placeholder="输入关键词..." @keyup.enter="loadData" clearable>
        <template #append><el-button :icon="Search" type="primary" @click="loadData">搜索</el-button></template>
      </el-input>
    </div>

    <div class="filter-row">
      <el-form :inline="true" :model="filter">
        <el-form-item label="公告类型">
          <el-select v-model="filter.notice_type_id" clearable placeholder="全部" style="width:140px">
            <el-option v-for="t in noticeTypes" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="招采类型">
          <el-input v-model="filter.procure_type" placeholder="如 公开招标" clearable style="width:140px" />
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
      共 <b>{{ total }}</b> 条标讯
    </div>

    <div v-loading="loading" class="result-list">
      <div v-for="b in list" :key="b.id" class="result-item" @click="$router.push(`/bid/${b.id}`)">
        <h3 class="result-title">{{ b.title }}</h3>
        <div class="result-meta">
          <el-tag v-if="b.procure_type" size="small">{{ b.procure_type }}</el-tag>
          <el-tag v-if="b.notice_type" size="small" type="success">{{ b.notice_type }}</el-tag>
          <span>{{ formatTime(b.publish_time) }}</span>
          <span v-if="b.region_name">· {{ b.region_name }}</span>
          <span>· 👁 {{ b.view_count }}</span>
        </div>
        <div v-if="b.tenderee" class="result-sub">采购人：{{ b.tenderee }} <span v-if="b.winner_unit">| 中标单位：{{ b.winner_unit }}</span> <span v-if="b.win_amount">| 中标金额：¥{{ b.win_amount?.toLocaleString() }}</span></div>
      </div>
      <el-empty v-if="!loading && list.length === 0" description="暂无匹配的标讯" />
    </div>

    <div class="pagination-wrap">
      <el-pagination v-if="total > 0" v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[10,20,30,50]" layout="total, sizes, prev, pager, next" @size-change="loadData" @current-change="loadData" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
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
  procure_type: (route.query.procure_type as string) || '',
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
  if (q.procure_type) filter.procure_type = q.procure_type as string
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
    if (filter.procure_type) q.procure_type = filter.procure_type
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
  keyword.value = ''; filter.notice_type_id = null; filter.procure_type = ''
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
.search-page { max-width: 1200px; margin: 24px auto; padding: 0 24px; }
.search-bar { max-width: 700px; margin: 0 auto 16px; }
.filter-row { background: #fff; border-radius: 8px; padding: 16px; margin-bottom: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.04); }
.result-bar { color: #909399; font-size: 13px; margin-bottom: 12px; }
.result-item { background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 12px; cursor: pointer; transition: all .2s; box-shadow: 0 1px 4px rgba(0,0,0,0.04); }
.result-item:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.08); transform: translateY(-1px); }
.result-title { margin: 0 0 10px; font-size: 16px; color: #303133; line-height: 1.5; }
.result-meta { display: flex; gap: 8px; align-items: center; color: #909399; font-size: 13px; flex-wrap: wrap; }
.result-sub { margin-top: 6px; color: #606266; font-size: 13px; }
.pagination-wrap { display: flex; justify-content: center; margin-top: 24px; }
</style>
