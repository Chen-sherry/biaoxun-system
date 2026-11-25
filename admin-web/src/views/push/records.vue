<template>
  <div class="push-records">
    <el-card>
      <template #header>
        <div class="card-header">
          <span class="title">推送记录</span>
          <span class="desc">审计日志 · 只读不可删</span>
        </div>
      </template>

      <el-form :inline="true" class="filter-bar">
        <el-form-item label="类型">
          <el-select v-model="q.push_type" placeholder="全部" clearable style="width: 130px">
            <el-option value="scheduled" label="定时" />
            <el-option value="manual" label="临时" />
            <el-option value="test" label="测试" />
            <el-option value="subscribe" label="订阅" />
            <el-option value="ai" label="AI 生成" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="q.status" placeholder="全部" clearable style="width: 110px">
            <el-option :value="0" label="成功" />
            <el-option :value="1" label="失败" />
          </el-select>
        </el-form-item>
        <el-form-item label="预览记录">
          <el-switch v-model="q.include_preview" active-text="显示" inactive-text="隐藏" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="load">查询</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="items" v-loading="loading" stripe border>
        <el-table-column prop="push_time" label="时间" width="155">
          <template #default="{ row }">{{ (row.push_time || '').replace('T', ' ').slice(0, 19) }}</template>
        </el-table-column>
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="typeTag(row.push_type)">{{ typeName(row.push_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="模板" width="120">
          <template #default="{ row }">
            <span v-if="row.template_code">{{ row.template_code }}</span>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作人" width="100">
          <template #default="{ row }">{{ row.operator_name || '定时任务' }}</template>
        </el-table-column>
        <el-table-column prop="subject" label="内容摘要" min-width="200" :show-overflow-tooltip="true" />
        <el-table-column prop="channel" label="通道" width="80" />
        <el-table-column label="标讯数" width="70">
          <template #default="{ row }">{{ row.bid_ids?.length || 0 }}</template>
        </el-table-column>
        <el-table-column label="结果" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.preview" size="small" type="info">预览</el-tag>
            <el-tag v-else-if="row.status === 0" size="small" type="success">成功</el-tag>
            <el-tag v-else size="small" type="danger">失败</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="error_msg" label="失败原因" min-width="160" :show-overflow-tooltip="true">
          <template #default="{ row }">
            <span :class="{ err: row.error_msg }">{{ row.error_msg || '-' }}</span>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="q.page" v-model:page-size="q.page_size" :total="total"
        :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next"
        @size-change="load" @current-change="load" class="pag"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { fetchPushRecords } from '@/api'

const q = reactive({
  push_type: undefined as string | undefined,
  status: undefined as number | undefined,
  include_preview: false,
  page: 1, page_size: 20,
})
const items = ref<any[]>([])
const total = ref(0)
const loading = ref(false)

const TYPE_NAME: Record<string, string> = {
  scheduled: '定时', manual: '临时', test: '测试', subscribe: '订阅', ai: 'AI 生成',
}
const TYPE_TAG: Record<string, any> = {
  scheduled: '', manual: 'primary', test: 'warning', subscribe: 'success', ai: 'danger',
}
function typeName(t: string) { return TYPE_NAME[t] || t }
function typeTag(t: string) { return TYPE_TAG[t] || 'info' }

async function load() {
  loading.value = true
  try {
    const params: any = {
      page: q.page, page_size: q.page_size, include_preview: q.include_preview,
    }
    if (q.push_type) params.push_type = q.push_type
    if (q.status !== null && q.status !== undefined) params.status = q.status
    const d = await fetchPushRecords(params)
    items.value = d.items || []
    total.value = d.total || 0
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.card-header { display: flex; align-items: baseline; gap: 10px; }
.title { font-size: 16px; font-weight: 600; }
.desc { color: #909399; font-size: 12px; }
.filter-bar { margin-bottom: 10px; }
.pag { margin-top: 16px; justify-content: flex-end; display: flex; }
.muted { color: #c0c4cc; }
.err { color: #f56c6c; }
</style>
