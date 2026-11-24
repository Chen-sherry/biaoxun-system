<template>
  <div class="subscribe-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span class="title">订阅管理</span>
          <span class="desc">所有用户订阅关键词 / 推送频率 / 启用状态</span>
        </div>
      </template>

      <!-- 筛选 -->
      <el-form :inline="true" class="filter-bar">
        <el-form-item label="关键词">
          <el-input v-model="q.keyword" placeholder="订阅关键词" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="q.status" placeholder="全部" clearable>
            <el-option :value="1" label="启用" />
            <el-option :value="0" label="停用" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="load">查询</el-button>
          <el-button @click="reset">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 表格 -->
      <el-table :data="items" v-loading="loading" stripe border>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="username" label="用户" width="130" />
        <el-table-column prop="keyword" label="订阅关键词" min-width="220" :show-overflow-tooltip="true" />
        <el-table-column label="频率" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.frequency === 'daily'" type="success">每日</el-tag>
            <el-tag v-else-if="row.frequency === 'weekly'" type="warning">每周</el-tag>
            <el-tag v-else>{{ row.frequency }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="渠道" width="140">
          <template #default="{ row }">
            <el-icon v-if="row.push_email" class="channel"><Message /></el-icon>
            <el-icon v-if="row.push_wechat" class="channel"><ChatDotRound /></el-icon>
            <span v-if="!row.push_email && !row.push_wechat">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status ? 'success' : 'info'">{{ row.status ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_push_at" label="上次推送" width="180" />
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link size="small" @click="toggleStatus(row)">
              {{ row.status ? '停用' : '启用' }}
            </el-button>
            <el-button link size="small" type="danger" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="q.page"
        v-model:page-size="q.page_size"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @size-change="load"
        @current-change="load"
        class="pag"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Message, ChatDotRound } from '@element-plus/icons-vue'
import { fetchSubscribeList, toggleSubscribe, deleteSubscribe } from '@/api'

const q = reactive({ keyword: '', status: undefined as number | undefined, page: 1, page_size: 20 })
const items = ref<any[]>([])
const total = ref(0)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const d = await fetchSubscribeList({ ...q })
    items.value = d.items || []
    total.value = d.total || 0
  } finally {
    loading.value = false
  }
}
function reset() { q.keyword = ''; q.status = undefined; q.page = 1; load() }

async function toggleStatus(row: any) {
  await toggleSubscribe(row.id)
  ElMessage.success('已更新')
  load()
}
async function onDelete(row: any) {
  await ElMessageBox.confirm(`删除订阅 #${row.id}？`, '提示', { type: 'warning' })
  await deleteSubscribe(row.id)
  ElMessage.success('删除成功')
  load()
}

onMounted(load)
</script>

<style scoped>
.card-header { display: flex; align-items: baseline; gap: 10px; }
.title { font-size: 16px; font-weight: 600; }
.desc { color: #909399; font-size: 12px; }
.filter-bar { margin-bottom: 10px; }
.pag { margin-top: 16px; justify-content: flex-end; display: flex; }
.channel { margin-right: 4px; color: #409eff; }
</style>
