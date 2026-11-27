<template>
  <div class="page-container">
    <div class="page-card">
      <h3 class="card-title">会员订单管理</h3>

      <!-- 筛选栏 -->
      <div class="filter-bar">
        <el-select v-model="query.status" placeholder="全部状态" clearable style="width: 130px">
          <el-option label="待支付" :value="0" />
          <el-option label="已支付" :value="1" />
          <el-option label="已取消" :value="2" />
          <el-option label="已退款" :value="3" />
        </el-select>
        <el-input v-model="query.keyword" placeholder="搜索订单号" clearable style="width: 200px" />
        <el-date-picker
          v-model="query.dateRange"
          type="daterange"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          style="width: 260px"
        />
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </div>

      <!-- 表格 -->
      <el-table :data="list" v-loading="loading" stripe style="margin-top: 12px">
        <el-table-column prop="order_no" label="订单号" min-width="200" show-overflow-tooltip />
        <el-table-column label="用户" width="120">
          <template #default="{ row }">{{ row.nickname || row.username || '-' }}</template>
        </el-table-column>
        <el-table-column prop="package_name" label="套餐" width="120" show-overflow-tooltip />
        <el-table-column prop="amount" label="金额" width="90">
          <template #default="{ row }">{{ row.amount.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="pay_type" label="支付方式" width="90">
          <template #default="{ row }">{{ { wechat: '微信', alipay: '支付宝', manual: '手动' }[row.pay_type] || row.pay_type || '-' }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="会员起始" width="160">
          <template #default="{ row }">{{ formatTime(row.start_date) || '-' }}</template>
        </el-table-column>
        <el-table-column label="到期时间" width="160">
          <template #default="{ row }">{{ formatTime(row.end_date) || '-' }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="160">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="showDetail(row)">详情</el-button>
            <el-popconfirm v-if="row.status === 1" title="确定退款？退款后会员权益将失效。" @confirm="refund(row)">
              <template #reference>
                <el-button link type="danger">退款</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="total > pageSize"
        style="margin-top: 12px; justify-content: flex-end"
        background
        layout="total, prev, pager, next"
        :total="total"
        :page-size="pageSize"
        v-model:current-page="page"
        @current-change="loadData"
      />
    </div>

    <!-- 订单详情弹窗 -->
    <el-dialog v-model="detailVisible" title="订单详情" width="520px">
      <el-descriptions :column="1" border v-if="detail">
        <el-descriptions-item label="订单号">{{ detail.order_no }}</el-descriptions-item>
        <el-descriptions-item label="用户">{{ detail.nickname || detail.username }} (ID: {{ detail.user_id }})</el-descriptions-item>
        <el-descriptions-item label="手机号">{{ detail.phone || '-' }}</el-descriptions-item>
        <el-descriptions-item label="套餐">{{ detail.package_name }}</el-descriptions-item>
        <el-descriptions-item label="金额">{{ detail.amount?.toFixed(2) }} 元</el-descriptions-item>
        <el-descriptions-item label="支付方式">{{ { wechat: '微信', alipay: '支付宝', manual: '手动' }[detail.pay_type] || detail.pay_type || '-' }}</el-descriptions-item>
        <el-descriptions-item label="支付时间">{{ formatTime(detail.pay_time) || '-' }}</el-descriptions-item>
        <el-descriptions-item label="会员起始">{{ formatTime(detail.start_date) || '-' }}</el-descriptions-item>
        <el-descriptions-item label="到期时间">{{ formatTime(detail.end_date) || '-' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusType(detail.status)" size="small">{{ statusText(detail.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="交易流水号">{{ detail.trade_no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="备注">{{ detail.remark || '-' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatTime(detail.created_at) }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchAdminOrderList, fetchAdminOrderDetail, refundOrder } from '@/api'

const loading = ref(false)
const list = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const detailVisible = ref(false)
const detail = ref<any>(null)

const query = reactive({
  status: undefined as number | undefined,
  keyword: '',
  dateRange: null as string[] | null,
})

function statusText(s: number) {
  return { 0: '待支付', 1: '已支付', 2: '已取消', 3: '已退款' }[s] || '未知'
}
function statusType(s: number) {
  return { 0: 'warning', 1: 'success', 2: 'info', 3: 'danger' }[s] as any || 'info'
}
function formatTime(t: any) {
  if (!t) return ''
  if (typeof t === 'string') return t.replace('T', ' ').slice(0, 19)
  return new Date(t).toLocaleString()
}

async function loadData() {
  loading.value = true
  try {
    const params: Record<string, any> = { page: page.value, page_size: pageSize }
    if (query.status !== undefined) params.status = query.status
    if (query.keyword) params.keyword = query.keyword
    if (query.dateRange?.length === 2) {
      params.date_from = query.dateRange[0]
      params.date_to = query.dateRange[1]
    }
    const res = await fetchAdminOrderList(params)
    list.value = res.items || []
    total.value = res.total || 0
  } finally { loading.value = false }
}

function search() {
  page.value = 1
  loadData()
}

function reset() {
  query.status = undefined
  query.keyword = ''
  query.dateRange = null
  search()
}

async function showDetail(row: any) {
  try {
    detail.value = await fetchAdminOrderDetail(row.order_no)
    detailVisible.value = true
  } catch (e: any) {
    ElMessage.error('获取详情失败')
  }
}

async function refund(row: any) {
  try {
    await refundOrder(row.order_no)
    ElMessage.success('退款成功')
    loadData()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '退款失败')
  }
}

onMounted(loadData)
</script>

<style scoped>
.card-title { margin: 0 0 12px; font-size: 16px; }
.filter-bar { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
</style>
