<template>
  <div class="page-container">
    <div class="page-card">
      <h3 class="card-title">待审核标讯</h3>
      <el-table :data="list" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="标题" min-width="360" show-overflow-tooltip />
        <el-table-column prop="tenderee" label="采购人" width="180" show-overflow-tooltip />
        <el-table-column prop="publish_time" label="录入时间" width="160" />
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="goEdit(row.id)">编辑</el-button>
            <el-button link type="success" @click="onAudit(row.id)">审核通过</el-button>
            <el-button link type="danger" @click="onReject(row.id)">驳回</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchBidList, auditBid } from '@/api'

const router = useRouter()
const loading = ref(false)
const list = ref<any[]>([])

async function loadData() {
  loading.value = true
  try {
    const data = await fetchBidList({ status: 0, page: 1, page_size: 50 })
    list.value = data.items
  } finally {
    loading.value = false
  }
}
function goEdit(id: number) { router.push(`/bid/edit/${id}`) }

async function onAudit(id: number) {
  await ElMessageBox.confirm('确认审核通过？通过后标讯将对前台可见', '审核', { type: 'warning' })
  await auditBid(id)
  ElMessage.success('已通过')
  loadData()
}
async function onReject(id: number) {
  await ElMessageBox.confirm('确认驳回？', '驳回', { type: 'warning' })
  ElMessage.success('已驳回')
  loadData()
}

onMounted(loadData)
</script>

<style scoped>
.card-title { margin: 0 0 12px; font-size: 16px; }
</style>
