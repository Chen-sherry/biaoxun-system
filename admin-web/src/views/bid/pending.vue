<template>
  <div class="page-container">
    <div class="page-card">
      <div class="head-row">
        <h3 class="card-title">待审核标讯</h3>
        <div class="switch-box">
          <span class="switch-label">AI 自动提取</span>
          <el-switch
            v-model="aiEnabled"
            :loading="switchLoading"
            inline-prompt
            active-text="开"
            inactive-text="关"
            @change="onToggleSwitch"
          />
          <el-tooltip placement="bottom" :content="aiEnabled
            ? '提取完整的标讯正常自动通过；缺字段的会先让 AI 补全'
            : '提取完整的标讯照常自动通过；缺字段的转人工审核（不调 AI）'">
            <el-icon class="tip-icon"><QuestionFilled /></el-icon>
          </el-tooltip>
          <span class="switch-hint" :class="{ off: !aiEnabled }">
            {{ aiEnabled ? '缺字段的标讯先由 AI 补全' : '缺字段的转人工，提取完整的正常发布' }}
          </span>
        </div>
      </div>

      <div class="toolbar">
        <span class="total">共 {{ total }} 条待审核</span>
        <el-button size="small" :loading="loading" @click="loadData">刷新</el-button>
      </div>

      <el-table :data="list" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="标题" min-width="340" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.ai_processed" class="ai-pill">AI</span>{{ row.title }}
          </template>
        </el-table-column>
        <el-table-column prop="notice_type" label="类型" width="110" />
        <el-table-column prop="tenderee" label="采购人" width="170" show-overflow-tooltip />
        <el-table-column label="缺失" width="150">
          <template #default="{ row }">
            <template v-if="missingOf(row).length">
              <el-tag v-for="m in missingOf(row)" :key="m" size="small" type="warning"
                      effect="plain" class="miss-tag">{{ m }}</el-tag>
            </template>
            <span v-else class="ok-text">完整</span>
          </template>
        </el-table-column>
        <el-table-column prop="publish_time" label="发布时间" width="160" />
        <el-table-column label="操作" width="290" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="goEdit(row.id)">编辑</el-button>
            <el-button link type="warning" :loading="row._extracting" @click="onReextract(row)">
              重新提取
            </el-button>
            <el-button link type="success" @click="onAudit(row.id)">通过</el-button>
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
import { QuestionFilled } from '@element-plus/icons-vue'
import {
  fetchBidList, auditBid, reextractBid,
  fetchExtractSwitch, updateExtractSwitch,
} from '@/api'

const router = useRouter()
const loading = ref(false)
const switchLoading = ref(false)
const aiEnabled = ref(true)
const list = ref<any[]>([])
const total = ref(0)

const MISS_LABELS: Record<string, string> = {
  tenderee: '采购人', winner_unit: '中标单位', win_amount: '中标金额',
  budget: '预算', deadline: '截止时间', project_code: '项目编号',
}

function missingOf(row: any) {
  const out: string[] = []
  if (!row.tenderee) out.push(MISS_LABELS.tenderee)
  // 仅有中标/成交语义的结果类公告才要求中标字段
  const isResult = /中标|成交|结果|候选人/.test(row.title || '')
  if (isResult && !row.winner_unit) out.push(MISS_LABELS.winner_unit)
  if (isResult && !row.win_amount) out.push(MISS_LABELS.win_amount)
  return out
}

async function loadData() {
  loading.value = true
  try {
    const data = await fetchBidList({ status: 0, page: 1, page_size: 50 })
    list.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function loadSwitch() {
  try {
    const d = await fetchExtractSwitch()
    aiEnabled.value = !!d.enabled
  } catch {
    aiEnabled.value = true
  }
}

async function onToggleSwitch(val: boolean) {
  switchLoading.value = true
  try {
    await updateExtractSwitch(val)
    ElMessage.success(val
      ? '已开启 AI 辅助：缺字段的标讯先由 AI 补全'
      : '已关闭 AI：提取完整的正常发布，缺字段的转人工')
  } catch {
    aiEnabled.value = !val // 失败回滚
  } finally {
    switchLoading.value = false
  }
}

function goEdit(id: number) { router.push(`/bid/edit/${id}`) }

async function onReextract(row: any) {
  row._extracting = true
  try {
    const d = await reextractBid(row.id)
    const n = Object.keys(d.updated || {}).length
    ElMessage.success(n ? `已补全 ${n} 个字段` : '没有可补全的字段，请手工编辑')
    await loadData()
  } finally {
    row._extracting = false
  }
}

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

onMounted(() => { loadData(); loadSwitch() })
</script>

<style scoped>
.head-row { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; margin-bottom: 10px; }
.card-title { margin: 0; font-size: 16px; }
.switch-box { display: flex; align-items: center; gap: 8px; }
.switch-label { font-size: 13px; color: #303133; font-weight: 600; }
.tip-icon { color: #909399; cursor: help; }
.switch-hint { font-size: 12px; color: #67c23a; }
.switch-hint.off { color: #e6a23c; }
.toolbar { display: flex; align-items: center; justify-content: space-between; margin: 6px 0 10px; }
.total { font-size: 12px; color: #909399; }
.miss-tag { margin-right: 4px; }
.ok-text { font-size: 12px; color: #67c23a; }
.ai-pill {
  display: inline-flex; align-items: center; justify-content: center;
  height: 16px; padding: 0 5px; margin-right: 4px; border-radius: 9999px;
  font-size: 10px; font-weight: 700; color: #fff;
  background: linear-gradient(135deg, #6366f1, #8b5cf6 55%, #0ea5e9);
  vertical-align: middle;
}
</style>
