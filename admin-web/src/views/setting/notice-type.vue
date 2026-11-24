<template>
  <div class="page-container">
    <div class="page-card">
      <h3 class="card-title">公告类型字典</h3>
      <el-alert type="info" :closable="false" title="公告类型字典 — 查看列表可用。增 / 删 / 改 功能开发中，敬请期待。" />
      <el-table :data="list" v-loading="loading" stripe style="margin-top: 16px">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="名称" min-width="180" />
        <el-table-column prop="code" label="编码" width="140" />
        <el-table-column prop="category" label="分类" width="160" />
        <el-table-column prop="sort" label="排序" width="90" />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status ? 'success' : 'info'">{{ row.status ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { fetchNoticeTypes } from '@/api'

const loading = ref(false)
const list = ref<any[]>([])

async function loadData() {
  loading.value = true
  try { list.value = await fetchNoticeTypes() } finally { loading.value = false }
}

onMounted(loadData)
</script>

<style scoped>
.card-title { margin: 0 0 12px; font-size: 16px; }
</style>
