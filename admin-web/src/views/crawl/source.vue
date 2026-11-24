<template>
  <div class="page-container">
    <div class="page-card">
      <div style="display: flex; justify-content: space-between; align-items: center">
        <h3 class="card-title">采集源配置</h3>
        <el-button type="warning" :loading="runningAll" @click="runAll">立即触发所有采集源</el-button>
      </div>
      <el-table :data="list" v-loading="loading" stripe style="margin-top: 12px">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="code" label="编码" width="140" />
        <el-table-column prop="source_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ {1:'爬虫',2:'开放接口',3:'手动',4:'Excel'}[row.source_type] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="interval_minutes" label="间隔(分)" width="100" />
        <el-table-column prop="last_crawl_at" label="上次采集" width="180">
          <template #default="{ row }">{{ formatTime(row.last_crawl_at) || '—' }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status ? 'success' : 'info'" size="small">{{ row.status ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" :loading="runningId === row.id" @click="runOnce(row)">立即采集</el-button>
            <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="editing?.id ? '编辑采集源' : '新增采集源'" width="640px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="编码"><el-input v-model="form.code" /></el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.source_type">
            <el-option label="爬虫" :value="1" />
            <el-option label="开放接口" :value="2" />
            <el-option label="手动" :value="3" />
            <el-option label="Excel" :value="4" />
          </el-select>
        </el-form-item>
        <el-form-item label="根地址"><el-input v-model="form.base_url" /></el-form-item>
        <el-form-item label="列表间隔(分)"><el-input-number v-model="form.interval_minutes" :min="5" /></el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" />
        </el-form-item>
        <el-form-item label="说明"><el-input v-model="form.description" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchSourceList, createSource, updateSource, runCrawlSource, runCrawlAll } from '@/api'

const loading = ref(false)
const list = ref<any[]>([])
const dialogVisible = ref(false)
const editing = ref<any>(null)
const runningId = ref<number | null>(null)
const runningAll = ref(false)
const form = reactive({
  name: '', code: '', source_type: 1, base_url: '', interval_minutes: 60, status: 1, description: '',
})

function formatTime(t: any) {
  if (!t) return ''
  // 后端返回 ISO 字符串
  if (typeof t === 'string') return t.replace('T', ' ').slice(0, 19)
  return new Date(t).toLocaleString()
}

async function loadData() {
  loading.value = true
  try { list.value = await fetchSourceList() } finally { loading.value = false }
}

function openDialog(row?: any) {
  editing.value = row || null
  Object.assign(form, row || { name: '', code: '', source_type: 1, base_url: '', interval_minutes: 60, status: 1, description: '' })
  dialogVisible.value = true
}

async function save() {
  if (editing.value?.id) {
    await updateSource(editing.value.id, form)
  } else {
    await createSource(form)
  }
  ElMessage.success('保存成功')
  dialogVisible.value = false
  loadData()
}

async function runOnce(row: any) {
  runningId.value = row.id
  try {
    const result = await runCrawlSource(row.id)
    ElMessage.success(`${row.name}：${result.msg || '已触发'}`)
    loadData()  // 刷新看 last_crawl_at
  } catch (e: any) {
    ElMessage.error(e?.message || '触发失败')
  } finally {
    runningId.value = null
  }
}

async function runAll() {
  runningAll.value = true
  try {
    const result = await runCrawlAll()
    ElMessage.success(result.msg || '全部触发完成')
    loadData()
  } catch (e: any) {
    ElMessage.error(e?.message || '触发失败')
  } finally {
    runningAll.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.card-title { margin: 0; font-size: 16px; }
</style>
