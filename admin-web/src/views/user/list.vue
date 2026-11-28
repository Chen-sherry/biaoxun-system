<template>
  <div class="page-container">
    <div class="page-card">
      <h3 class="card-title">用户管理</h3>
      <el-alert type="info" :closable="false" title="用户管理 — 查看列表可用。权限分配 / 状态切换 功能开发中，敬请期待。" />
      <el-table :data="list" v-loading="loading" stripe style="margin-top: 16px">
        <el-table-column prop="id" label="ID" min-width="80" />
        <el-table-column prop="username" label="用户名" min-width="140" />
        <el-table-column prop="nickname" label="昵称" min-width="140" />
        <el-table-column prop="roles" label="角色" min-width="200">
          <template #default="{ row }">
            <el-tag v-for="r in row.roles" :key="r.code" size="small" style="margin-right: 4px">{{ r.name }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" min-width="90">
          <template #default="{ row }">
            <el-tag :type="row.status ? 'success' : 'info'">{{ row.status ? '正常' : '禁用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="160">
          <template #default="{ row }">
            <el-button link type="primary" @click="toggleStatus(row)">{{ row.status ? '禁用' : '启用' }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchAdminUserList } from '@/api'

const loading = ref(false)
const list = ref<any[]>([])

async function loadData() {
  loading.value = true
  try {
    const d = await fetchAdminUserList({ page: 1, page_size: 50 })
    // 后端返回 { total, page, page_size, items }，d 本身就是这个对象（axios 拦截器已解包 data.data）
    list.value = d.items || d || []
  } finally {
    loading.value = false
  }
}
async function toggleStatus(row: any) {
  ElMessage.info('用户状态切换 — 功能开发中，敬请期待')
}

onMounted(loadData)
</script>

<style scoped>
.card-title { margin: 0 0 12px; font-size: 16px; }
</style>
