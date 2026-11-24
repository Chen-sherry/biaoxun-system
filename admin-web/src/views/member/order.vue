<template>
  <div class="page-container">
    <div class="page-card">
      <h3 class="card-title">会员订单</h3>
      <el-alert type="info" :closable="false" title="会员订单 — 查看列表可用。订单筛选 / 退款 / 导出 功能开发中，敬请期待。" />
      <el-table :data="list" v-loading="loading" stripe style="margin-top: 16px">
        <el-table-column prop="order_no" label="订单号" width="220" />
        <el-table-column prop="user_id" label="用户ID" width="90" />
        <el-table-column prop="package_id" label="套餐ID" width="90" />
        <el-table-column prop="amount" label="金额(元)" width="110" />
        <el-table-column prop="pay_type" label="支付方式" width="110" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            {{ {0:'待支付',1:'已支付',2:'已取消',3:'已退款'}[row.status] }}
          </template>
        </el-table-column>
        <el-table-column prop="start_date" label="会员起始" width="160" />
        <el-table-column prop="end_date" label="到期时间" width="160" />
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { fetchOrderList } from '@/api'

const loading = ref(false)
const list = ref<any[]>([])

async function loadData() {
  loading.value = true
  try { list.value = await fetchOrderList({ page: 1, page_size: 50 }) } finally { loading.value = false }
}

onMounted(loadData)
</script>

<style scoped>
.card-title { margin: 0 0 12px; font-size: 16px; }
</style>
