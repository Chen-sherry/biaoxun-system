<template>
  <div class="push-subscribers">
    <el-card>
      <template #header>
        <div class="card-header">
          <span class="title">订阅用户</span>
          <span class="desc">用户订阅条件管理 · 匹配预览 · 推送（通道待接入）</span>
          <span class="spacer" />
          <el-button type="warning" plain @click="batchPush">批量立即推送全部订阅</el-button>
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
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="username" label="用户" width="110" />
        <el-table-column label="会员" width="140">
          <template #default="{ row }">
            <template v-if="row.package_name">
              <el-tooltip :content="`订阅 ${row.active_subscribe_count}/${row.max_subscribe} 条`" placement="top">
                <el-tag size="small" :type="row.over_limit ? 'danger' : 'info'">
                  {{ row.package_name }}{{ row.over_limit ? '（超限）' : '' }}
                </el-tag>
              </el-tooltip>
            </template>
            <span v-else class="muted">无套餐</span>
          </template>
        </el-table-column>
        <el-table-column prop="keyword" label="订阅关键词" min-width="180" :show-overflow-tooltip="true" />
        <el-table-column label="地区" width="90">
          <template #default="{ row }">{{ dictName(regions, row.region_code, 'code') || '-' }}</template>
        </el-table-column>
        <el-table-column label="行业" width="100">
          <template #default="{ row }">{{ dictName(industries, row.industry_id) || '-' }}</template>
        </el-table-column>
        <el-table-column label="公告类型" width="100">
          <template #default="{ row }">{{ dictName(noticeTypes, row.notice_type_id) || '-' }}</template>
        </el-table-column>
        <el-table-column label="频率" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.frequency === 'daily'" type="success" size="small">每日</el-tag>
            <el-tag v-else-if="row.frequency === 'realtime'" type="primary" size="small">实时</el-tag>
            <el-tag v-else type="info" size="small">{{ row.frequency }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="渠道" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.push_wechat" size="small" type="success">企微</el-tag>
            <el-tag v-else-if="row.push_email" size="small">邮件</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="70">
          <template #default="{ row }">
            <el-tag :type="row.status ? 'success' : 'info'" size="small">{{ row.status ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_push_at" label="上次推送" width="150">
          <template #default="{ row }">{{ (row.last_push_at || '').replace('T', ' ').slice(0, 16) || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button link size="small" @click="openPreview(row)">匹配预览</el-button>
            <el-button link size="small" type="primary" @click="openEdit(row)">条件编辑</el-button>
            <el-button link size="small" type="warning" @click="pushOne(row)">立即推送</el-button>
            <el-button link size="small" @click="toggleStatus(row)">{{ row.status ? '停用' : '启用' }}</el-button>
            <el-button link size="small" type="danger" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="q.page" v-model:page-size="q.page_size" :total="total"
        :page-sizes="[10, 20, 50]" layout="total, sizes, prev, pager, next"
        @size-change="load" @current-change="load" class="pag"
      />
    </el-card>

    <!-- 匹配预览抽屉（U2） -->
    <el-drawer v-model="pvDrawer" :title="`匹配预览：${pvSub?.username || ''} 的订阅`" size="640px">
      <template v-if="pvSub">
        <el-form label-width="90px" size="small" class="pv-cond">
          <el-form-item label="关键词">{{ pvSub.keyword || '（无）' }}</el-form-item>
          <el-form-item label="限制条件">
            {{ condText(pvSub) }}
          </el-form-item>
          <el-form-item label="近 N 天">
            <el-input-number v-model="pvDays" :min="1" :max="90" @change="loadPreview" />
          </el-form-item>
        </el-form>
        <div class="pv-stat">
          命中 <b>{{ pvItems.length }}</b> 条 —— 即该用户会收到的标讯范围
        </div>
        <el-table :data="pvItems" v-loading="pvLoading" size="small" stripe max-height="460">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="title" label="标题" min-width="260" :show-overflow-tooltip="true" />
          <el-table-column label="发布时间" width="100">
            <template #default="{ row }">{{ (row.publish_time || '').slice(0, 10) }}</template>
          </el-table-column>
        </el-table>
      </template>
    </el-drawer>

    <!-- 条件编辑抽屉（U5） -->
    <el-drawer v-model="editDrawer" title="编辑订阅条件" size="480px">
      <template v-if="editForm">
        <el-form label-position="top">
          <el-form-item label="关键词（空格/逗号分隔多词，OR 匹配）">
            <el-input v-model="editForm.keyword" placeholder="如：医疗器械 中标" />
          </el-form-item>
          <el-form-item label="限定省份">
            <el-select v-model="editForm.region_code" clearable placeholder="不限" style="width: 100%">
              <el-option v-for="r in regions" :key="r.code" :value="r.code" :label="r.name" />
            </el-select>
          </el-form-item>
          <el-form-item label="限定行业">
            <el-select v-model="editForm.industry_id" clearable placeholder="不限" style="width: 100%">
              <el-option v-for="i in industries" :key="i.id" :value="i.id" :label="i.name" />
            </el-select>
          </el-form-item>
          <el-form-item label="限定公告类型">
            <el-select v-model="editForm.notice_type_id" clearable placeholder="不限" style="width: 100%">
              <el-option v-for="t in noticeTypes" :key="t.id" :value="t.id" :label="t.name" />
            </el-select>
          </el-form-item>
          <el-form-item label="推送频率">
            <el-select v-model="editForm.frequency" style="width: 100%">
              <el-option value="daily" label="每日汇总" />
              <el-option value="realtime" label="实时" />
              <el-option value="hourly" label="每小时（本期未启用）" disabled />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-switch v-model="editForm.status" :active-value="1" :inactive-value="0" active-text="启用" inactive-text="停用" />
          </el-form-item>
          <el-button type="primary" style="width: 100%" @click="saveEdit" :loading="saving">保存</el-button>
        </el-form>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  fetchSubscribeList, toggleSubscribe, deleteSubscribe,
  previewSubscribe, pushSubscribeNow, pushAllSubscribes, adminUpdateSubscribe,
  fetchNoticeTypes, fetchIndustries, fetchRegions,
} from '@/api'

const q = reactive({ keyword: '', status: undefined as number | undefined, page: 1, page_size: 20 })
const items = ref<any[]>([])
const total = ref(0)
const loading = ref(false)

const noticeTypes = ref<any[]>([])
const industries = ref<any[]>([])
const regions = ref<any[]>([])

const pvDrawer = ref(false)
const pvSub = ref<any>(null)
const pvItems = ref<any[]>([])
const pvLoading = ref(false)
const pvDays = ref(7)

const editDrawer = ref(false)
const editForm = ref<any>(null)
const saving = ref(false)

function dictName(list: any[], val: any, key = 'id') {
  if (val === null || val === undefined) return ''
  const hit = list.find(i => i[key] === val)
  return hit?.name || ''
}

function condText(s: any) {
  const parts = []
  if (s.region_code) parts.push(`地区=${dictName(regions, s.region_code, 'code')}`)
  if (s.industry_id) parts.push(`行业=${dictName(industries, s.industry_id)}`)
  if (s.notice_type_id) parts.push(`类型=${dictName(noticeTypes, s.notice_type_id)}`)
  return parts.length ? parts.join(' · ') + '（其余维度不约束）' : '无附加限制（全匹配）'
}

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

// U2 匹配预览
async function openPreview(row: any) {
  pvSub.value = row
  pvDays.value = 7
  pvDrawer.value = true
  await loadPreview()
}
async function loadPreview() {
  if (!pvSub.value) return
  pvLoading.value = true
  try {
    const d = await previewSubscribe(pvSub.value.id, pvDays.value)
    pvItems.value = d.items || []
  } finally {
    pvLoading.value = false
  }
}

// U3 立即推送（Q2=C：生成记录，通道待接入）
async function pushOne(row: any) {
  const r = await ElMessageBox.confirm(
    `按「${row.keyword || '该订阅'}」的条件实时匹配标讯并生成推送记录？\n（当前通道待接入，不会实际发送）`,
    '立即推送', { type: 'warning', confirmButtonText: '生成推送记录' },
  ).catch(() => null)
  if (!r) return
  const d: any = await pushSubscribeNow(row.id)
  ElMessage.success(d?.msg || '已生成推送记录')
}

// U4 批量推送（需输入确认词防误触）
async function batchPush() {
  let input = ''
  try {
    await ElMessageBox.prompt(
      '将为所有启用中的订阅生成推送记录（通道待接入，不会实际发送）。\n请输入「确认」二字继续：',
      '批量立即推送', { confirmButtonText: '继续', cancelButtonText: '取消' },
    ).then(v => { input = v.value })
  } catch { return }
  if (input.trim() !== '确认') { ElMessage.warning('确认词不正确，已取消'); return }
  const d: any = await pushAllSubscribes()
  ElMessage.success(d?.msg || '批量推送记录已生成')
}

// U5 条件编辑
const editId = ref(0)
function openEdit(row: any) {
  editId.value = row.id
  editForm.value = {
    keyword: row.keyword, region_code: row.region_code,
    industry_id: row.industry_id, notice_type_id: row.notice_type_id,
    frequency: row.frequency, status: row.status,
  }
  editDrawer.value = true
}
async function saveEdit() {
  saving.value = true
  try {
    await adminUpdateSubscribe(editId.value, editForm.value)
    ElMessage.success('订阅条件已更新')
    editDrawer.value = false
    load()
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  load()
  const [nt, ind, reg] = await Promise.all([
    fetchNoticeTypes().catch(() => []),
    fetchIndustries(0).catch(() => []),
    fetchRegions(0).catch(() => []),
  ])
  noticeTypes.value = nt || []
  industries.value = ind || []
  regions.value = reg || []
})
</script>

<style scoped>
.card-header { display: flex; align-items: center; gap: 10px; }
.title { font-size: 16px; font-weight: 600; }
.desc { color: #909399; font-size: 12px; }
.spacer { flex: 1; }
.filter-bar { margin-bottom: 10px; }
.pag { margin-top: 16px; justify-content: flex-end; display: flex; }
.muted { color: #c0c4cc; font-size: 12px; }
.pv-cond { margin-bottom: 4px; }
.pv-stat { font-size: 13px; color: #606266; margin-bottom: 10px; }
.pv-stat b { color: #409eff; font-size: 16px; }
</style>
