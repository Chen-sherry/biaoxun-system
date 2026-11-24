<template>
  <div class="page-container">
    <div class="page-card">
      <el-form :inline="true" :model="query" class="query-form">
        <el-form-item label="关键词">
          <el-input v-model="query.keyword" placeholder="标题/正文模糊匹配" clearable style="width: 240px" />
        </el-form-item>
        <el-form-item label="公告类型">
          <el-select v-model="query.notice_type_id" placeholder="全部" clearable style="width: 160px">
            <el-option v-for="t in noticeTypes" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="所属行业">
          <el-select v-model="query.industry_id" placeholder="全部" clearable style="width: 160px">
            <el-option v-for="i in industries" :key="i.id" :label="i.name" :value="i.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="审核状态">
          <el-select v-model="query.status" placeholder="全部" clearable style="width: 120px">
            <el-option label="待审核" :value="0" />
            <el-option label="已发布" :value="1" />
            <el-option label="已下架" :value="2" />
            <el-option label="已归档" :value="3" />
          </el-select>
        </el-form-item>
        <el-form-item label="发布日期">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="width: 260px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">查询</el-button>
          <el-button @click="resetQuery">重置</el-button>
          <el-button type="success" :icon="Plus" @click="goCreate">新增标讯</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="page-card" style="margin-top: 16px">
      <el-table :data="list" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="标题" min-width="320" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tag v-if="row.is_top" size="small" type="warning" style="margin-right: 6px">置顶</el-tag>
            {{ row.title }}
          </template>
        </el-table-column>
        <el-table-column prop="notice_type" label="公告类型" width="100" />
        <el-table-column prop="procure_type" label="采购方式" width="120" show-overflow-tooltip />
        <el-table-column prop="region_name" label="地区" width="100" />
        <el-table-column prop="customer_group" label="客户群体" width="100" show-overflow-tooltip />
        <el-table-column prop="winner_unit" label="中标单位" min-width="180" show-overflow-tooltip />
        <el-table-column prop="publish_time" label="发布时间" width="160" />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="goEdit(row.id)">编辑</el-button>
            <el-button link type="success" v-if="row.status === 0" @click="onAudit(row.id)">审核</el-button>
            <el-button link type="warning" v-if="row.status === 1" @click="onOffline(row.id)">下架</el-button>
            <el-button link :type="row.is_top ? 'info' : 'primary'" @click="onToggleTop(row)">
              {{ row.is_top ? '取消置顶' : '置顶' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        style="margin-top: 16px; text-align: right"
        v-model:current-page="query.page"
        v-model:page-size="query.page_size"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadData"
        @current-change="loadData"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { fetchBidList, auditBid, offlineBid, toggleBidTop, fetchNoticeTypes, fetchIndustries } from '@/api'

const router = useRouter()
const loading = ref(false)
const list = ref<any[]>([])
const total = ref(0)
const noticeTypes = ref<any[]>([])
const industries = ref<any[]>([])
const dateRange = ref<[string, string] | null>(null)

const query = reactive({
  keyword: '',
  notice_type_id: undefined as number | undefined,
  industry_id: undefined as number | undefined,
  status: 1 as number | undefined,
  date_from: undefined as string | undefined,
  date_to: undefined as string | undefined,
  page: 1,
  page_size: 20,
})

function statusTag(s: number): 'primary' | 'success' | 'warning' | 'info' | 'danger' {
  return ({ 0: 'info', 1: 'success', 2: 'warning', 3: 'info' } as const)[s] ?? 'info'
}
function statusText(s: number) {
  return { 0: '待审核', 1: '已发布', 2: '已下架', 3: '已归档' }[s] || s
}

async function loadData() {
  loading.value = true
  // 日期范围拆分到 query
  if (dateRange.value && dateRange.value.length === 2) {
    query.date_from = dateRange.value[0]
    query.date_to = dateRange.value[1]
  } else {
    query.date_from = undefined
    query.date_to = undefined
  }
  try {
    const data = await fetchBidList(query)
    list.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}
function resetQuery() {
  query.keyword = ''
  query.notice_type_id = undefined
  query.industry_id = undefined
  query.status = 1
  query.date_from = undefined
  query.date_to = undefined
  dateRange.value = null
  query.page = 1
  loadData()
}
function goCreate() { router.push('/bid/edit') }
function goEdit(id: number) { router.push(`/bid/edit/${id}`) }

async function onAudit(id: number) {
  await ElMessageBox.confirm('确认审核通过该标讯？', '提示', { type: 'warning' })
  await auditBid(id)
  ElMessage.success('审核通过')
  loadData()
}
async function onOffline(id: number) {
  await ElMessageBox.confirm('确认下架该标讯？', '提示', { type: 'warning' })
  await offlineBid(id)
  ElMessage.success('已下架')
  loadData()
}
async function onToggleTop(row: any) {
  const action = row.is_top ? '取消置顶' : '置顶'
  await ElMessageBox.confirm(`确认${action}该标讯？`, '提示', { type: 'warning' })
  await toggleBidTop(row.id, !row.is_top)
  ElMessage.success(`已${action}`)
  loadData()
}

onMounted(async () => {
  noticeTypes.value = await fetchNoticeTypes()
  industries.value = await fetchIndustries()
  loadData()
})
</script>
