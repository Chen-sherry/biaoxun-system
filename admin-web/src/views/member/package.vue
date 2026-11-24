<template>
  <div class="page-container">
    <div class="page-card">
      <h3 class="card-title">会员套餐</h3>
      <el-alert type="info" :closable="false" title="会员套餐 — 查看列表可用。新增 / 编辑 / 上下架 功能开发中，敬请期待。" />
      <el-table :data="list" v-loading="loading" stripe style="margin-top: 16px">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="套餐名称" width="160" />
        <el-table-column prop="level" label="等级" width="80" />
        <el-table-column prop="duration_days" label="有效天数" width="100" />
        <el-table-column prop="price" label="原价(元)" width="110" />
        <el-table-column prop="sale_price" label="售价(元)" width="110" />
        <el-table-column prop="max_subscribe" label="最大订阅数" width="120" />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status ? 'success' : 'info'">{{ row.status ? '上架' : '下架' }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { fetchPackageList } from '@/api'

const loading = ref(false)
const list = ref<any[]>([])

async function loadData() {
  loading.value = true
  try { list.value = await fetchPackageList() } finally { loading.value = false }
}

onMounted(loadData)
</script>

<style scoped>
.card-title { margin: 0 0 12px; font-size: 16px; }
</style>
