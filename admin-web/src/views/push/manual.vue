<template>
  <div class="push-manual">
    <el-card shadow="never">
      <el-tabs v-model="tab">
        <!-- ============ Tab A：选标讯推送 ============ -->
        <el-tab-pane label="选标讯推送" name="bids">
          <el-form :inline="true" class="filter-bar">
            <el-form-item label="关键词">
              <el-input v-model="q.keyword" placeholder="标题关键词" clearable style="width: 180px" />
            </el-form-item>
            <el-form-item label="公告类型">
              <el-select v-model="q.notice_type_id" placeholder="全部" clearable style="width: 150px">
                <el-option v-for="t in noticeTypes" :key="t.id" :value="t.id" :label="t.name" />
              </el-select>
            </el-form-item>
            <el-form-item label="省份">
              <el-select v-model="q.region_code" placeholder="全部" clearable style="width: 150px">
                <el-option v-for="r in regions" :key="r.code" :value="r.code" :label="r.name" />
              </el-select>
            </el-form-item>
            <el-form-item label="发布时间">
              <el-date-picker v-model="dateRange" type="daterange" value-format="YYYY-MM-DD"
                start-placeholder="开始" end-placeholder="结束" style="width: 240px" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadBids">查询</el-button>
            </el-form-item>
          </el-form>

          <div class="bid-layout">
            <div class="bid-table">
              <el-table
                ref="bidTableRef" :data="bids" v-loading="loading" stripe border
                row-key="id" @selection-change="onSelChange"
              >
                <el-table-column type="selection" width="45" reserve-selection />
                <el-table-column prop="title" label="标题" min-width="280" :show-overflow-tooltip="true" />
                <el-table-column prop="notice_type" label="类型" width="110" />
                <el-table-column prop="region_name" label="地区" width="90" />
                <el-table-column prop="publish_time" label="发布时间" width="105">
                  <template #default="{ row }">{{ (row.publish_time || '').slice(0, 10) }}</template>
                </el-table-column>
              </el-table>
              <el-pagination
                v-model:current-page="q.page" :page-size="q.page_size" :total="total"
                layout="total, prev, pager, next" class="pag" @current-change="loadBids"
              />
            </div>

            <!-- 已选区 -->
            <div class="sel-panel">
              <div class="sel-head">
                已选 <b :class="{ over: selectedIds.length > LIMIT }">{{ selectedIds.length }}</b> / {{ LIMIT }} 条
              </div>
              <div class="sel-list">
                <div v-for="(b, i) in selected" :key="b.id" class="sel-item">
                  <span class="sel-title" :title="b.title">{{ b.title.slice(0, 26) }}</span>
                  <span class="sel-ops">
                    <el-button link size="small" :disabled="i === 0" @click="moveSel(i, -1)">↑</el-button>
                    <el-button link size="small" :disabled="i === selected.length - 1" @click="moveSel(i, 1)">↓</el-button>
                    <el-button link size="small" type="danger" @click="removeSel(b.id)">×</el-button>
                  </span>
                </div>
                <el-empty v-if="!selected.length" description="左侧勾选标讯" :image-size="60" />
              </div>
              <el-input v-model="bidsHeader" placeholder="消息开头文字（可选），如：【今日重点项目】" clearable />
              <el-radio-group v-model="bidsFormat">
                <el-radio value="markdown">Markdown 卡片（带链接）</el-radio>
                <el-radio value="text">纯文本列表</el-radio>
              </el-radio-group>
              <div class="send-ops">
                <el-button @click="previewBids" :loading="previewing">预览</el-button>
                <el-button type="primary" :disabled="!selected.length" @click="sendBids">发送到企微群</el-button>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <!-- ============ Tab B：自由文本通知 ============ -->
        <el-tab-pane label="自由文本通知" name="text">
          <div class="text-layout">
            <div class="text-left">
              <div class="preset-row">
                <span class="lbl">常用文案：</span>
                <el-button v-for="(p, i) in PRESETS" :key="i" size="small" plain @click="applyPreset(p)">
                  {{ p.name }}
                </el-button>
              </div>
              <el-input
                v-model="textContent" type="textarea" :rows="12"
                placeholder="输入要发到企微群的通知内容（支持 Markdown：## 标题、**加粗**、[链接](url)、- 列表）"
              />
              <div class="text-ops">
                <el-radio-group v-model="textFormat">
                  <el-radio value="markdown">Markdown</el-radio>
                  <el-radio value="text">纯文本</el-radio>
                </el-radio-group>
                <span class="len" :class="{ over: textLen > 4096 }">{{ textLen }}/4096 字节</span>
                <el-button @click="previewText" :loading="previewing">预览</el-button>
                <el-button type="primary" :disabled="!textContent.trim()" @click="sendText">发送到企微群</el-button>
              </div>
            </div>
            <div class="text-right" v-html="textPreviewHtml"></div>
          </div>
        </el-tab-pane>

        <!-- ============ Tab C：AI 生成 ============ -->
        <el-tab-pane label="AI 生成" name="ai">
          <el-alert v-if="channels && !channels.ai_enabled" type="warning" :closable="false" class="mb12"
            title="DeepSeek API Key 未配置" description="服务器 backend/.env 配置 DEEPSEEK_API_KEY 并重启 biaoxun-api 后可用。" />
          <el-alert type="info" :closable="false" class="mb12"
            title="用法：直接说需求，AI 会调用标讯数据库检索并生成推送文案；生成后可人工修改，确认无误再发送。" />

          <div class="ai-layout">
            <div class="ai-chat">
              <div class="ai-msgs" ref="msgsRef">
                <div v-for="(m, i) in aiMsgs" :key="i" class="ai-msg" :class="m.role">
                  <div class="ai-role">{{ m.role === 'user' ? '我' : 'AI' }}</div>
                  <div class="ai-body">{{ m.content }}</div>
                </div>
                <div v-if="aiLoading" class="ai-msg assistant">
                  <div class="ai-role">AI</div>
                  <div class="ai-body loading-dot">AI 正在检索标讯并生成…</div>
                </div>
                <div v-if="!aiMsgs.length" class="ai-empty">
                  试试：「找最近 3 天杭州的医疗器械中标公告，整理成推送文案，突出中标金额」
                </div>
              </div>
              <div class="ai-input">
                <el-input
                  v-model="aiInput" type="textarea" :rows="3"
                  placeholder="描述你要推送的内容，回车发送（Shift+回车换行）"
                  @keydown.enter.exact.prevent="sendAi"
                />
                <el-button type="primary" :loading="aiLoading" :disabled="!aiInput.trim()" @click="sendAi">
                  发送
                </el-button>
              </div>
            </div>

            <!-- 生成结果（可编辑 → 预览 → 发送） -->
            <div class="ai-result" v-if="aiDraft !== null">
              <div class="ai-result-head">
                生成结果（可修改）
                <span class="cited" v-if="aiCited.length">引用标讯 {{ aiCited.length }} 条</span>
              </div>
              <el-input v-model="aiDraft" type="textarea" :rows="14" />
              <div class="len-row">
                <span class="len" :class="{ over: aiLen > 4096 }">{{ aiLen }}/4096 字节</span>
                <span class="cited" v-if="aiCited.length">bid_ids: {{ aiCited.slice(0, 8).join(', ') }}{{ aiCited.length > 8 ? '…' : '' }}</span>
              </div>
              <div class="ai-result-ops">
                <el-button @click="previewAi" :loading="previewing">预览</el-button>
                <el-button type="primary" :disabled="!aiDraft.trim()" @click="sendAiResult">发送到企微群</el-button>
              </div>
              <div class="ai-bubble" v-html="aiPreviewHtml"></div>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  fetchBidList, fetchNoticeTypes, fetchRegions,
  previewManualPush, sendManualBids, sendManualText,
  aiGeneratePush, aiSendPush, fetchPushChannels,
} from '@/api'
import { mdLite } from '@/utils/mdLite'

const LIMIT = 20 // Q14：单次上限
const tab = ref('bids')
const channels = ref<any>(null)
const previewing = ref(false)

// ---------- Tab A ----------
const q = reactive({ keyword: '', notice_type_id: undefined as number | undefined,
  region_code: undefined as string | undefined, page: 1, page_size: 20 })
const dateRange = ref<string[] | null>(null)
const bids = ref<any[]>([])
const total = ref(0)
const loading = ref(false)
const selected = ref<any[]>([])
const selectedIds = computed(() => selected.value.map(b => b.id))
const bidsHeader = ref('')
const bidsFormat = ref('markdown')
const noticeTypes = ref<any[]>([])
const regions = ref<any[]>([])
const bidTableRef = ref()

async function loadBids() {
  loading.value = true
  try {
    const params: any = { status: 1, page: q.page, page_size: q.page_size }
    if (q.keyword) params.keyword = q.keyword
    if (q.notice_type_id) params.notice_type_id = q.notice_type_id
    if (q.region_code) params.region_code = q.region_code
    if (dateRange.value?.[0]) params.date_from = dateRange.value[0]
    if (dateRange.value?.[1]) params.date_to = dateRange.value[1] + ' 23:59:59'
    const d = await fetchBidList(params)
    bids.value = d.items || []
    total.value = d.total || 0
  } finally {
    loading.value = false
  }
}

function onSelChange(rows: any[]) {
  // reserve-selection：rows 为跨页全部勾选，直接作为已选列表（保序 = 勾选顺序）
  if (rows.length > LIMIT) {
    ElMessage.warning(`单次最多 ${LIMIT} 条，已取消超出部分`)
    for (const extra of rows.slice(LIMIT)) {
      bidTableRef.value?.toggleRowSelection?.(extra, false)
    }
    rows = rows.slice(0, LIMIT)
  }
  selected.value = rows
}

function removeSel(id: number) {
  const rows = bidTableRef.value?.getSelectionRows?.() || []
  const target = rows.find((r: any) => r.id === id)
  if (target) {
    bidTableRef.value?.toggleRowSelection?.(target, false) // 触发 selection-change 同步
  } else {
    selected.value = selected.value.filter(b => b.id !== id)
  }
}
function moveSel(i: number, dir: number) {
  const arr = selected.value
  const j = i + dir
  if (j < 0 || j >= arr.length) return
  ;[arr[i], arr[j]] = [arr[j], arr[i]]
  selected.value = [...arr]
}

async function previewBids() {
  if (!selected.value.length) return
  previewing.value = true
  try {
    const d = await previewManualPush({
      kind: 'bids', bid_ids: selectedIds.value,
      header: bidsHeader.value, format: bidsFormat.value,
    })
    await ElMessageBox.alert(
      `<div class="pv-body">${mdLite(d.content)}</div>`,
      `预览（${d.count} 条 · ${d.length.bytes}/${d.length.limit} 字节）`,
      { dangerouslyUseHTMLString: true, customStyle: { maxWidth: '560px' } },
    )
  } finally {
    previewing.value = false
  }
}

async function sendBids() {
  const r = await ElMessageBox.confirm(
    `确认将 ${selected.value.length} 条标讯发送到企业微信群？`, '发送确认', { type: 'warning' },
  ).catch(() => null)
  if (!r) return
  const res: any = await sendManualBids({
    bid_ids: selectedIds.value, header: bidsHeader.value, format: bidsFormat.value,
  })
  ElMessage.success(res?.msg || '已发送')
  bidTableRef.value?.clearSelection?.()
  selected.value = []
}

// ---------- Tab B ----------
const PRESETS = [
  { name: '系统维护通知', content: '## 系统维护通知\n\n系统将于 **{时间}** 进行例行维护，期间服务暂停使用，预计 **{时长}** 后恢复。给您带来不便，敬请谅解。' },
  { name: '节假日推送调整', content: '## 节假日推送安排\n\n节假日期间标讯推送频率调整为 **每日一次（09:00）**，到期预警照常发送。祝大家节日快乐！' },
  { name: '新功能上线', content: '## 新功能上线\n\n**AI 智能检索**现已上线，支持大白话查找标讯，快来体验吧！' },
  { name: '数据异常提醒', content: '## 数据提醒\n\n部分标讯数据正在补采，**截止时间/中标信息** 字段可能暂缺，预计今日内完成，届时自动更新。' },
]
const textContent = ref('')
const textFormat = ref('markdown')
const textPreviewHtml = ref('')
const textLen = computed(() => new TextEncoder().encode(textContent.value).length)

function applyPreset(p: { content: string }) {
  textContent.value = p.content
  textPreviewHtml.value = mdLite(p.content)
}

async function previewText() {
  previewing.value = true
  try {
    const d = await previewManualPush({ kind: 'text', content: textContent.value, format: textFormat.value })
    textPreviewHtml.value = mdLite(d.content)
    ElMessage.success(`预览已生成（${d.length.bytes}/${d.length.limit} 字节，已记录预览日志）`)
  } finally {
    previewing.value = false
  }
}

async function sendText() {
  const r = await ElMessageBox.confirm('确认将这段文字发送到企业微信群？', '发送确认', { type: 'warning' })
    .catch(() => null)
  if (!r) return
  const res: any = await sendManualText({ content: textContent.value, format: textFormat.value })
  ElMessage.success(res?.msg || '已发送')
}

// ---------- Tab C：AI ----------
const aiMsgs = ref<{ role: string; content: string }[]>([])
const aiInput = ref('')
const aiLoading = ref(false)
const aiDraft = ref<string | null>(null)
const aiCited = ref<number[]>([])
const aiPreviewHtml = ref('')
const msgsRef = ref()
const aiLen = computed(() => new TextEncoder().encode(aiDraft.value || '').length)

async function sendAi() {
  const text = aiInput.value.trim()
  if (!text || aiLoading.value) return
  aiMsgs.value.push({ role: 'user', content: text })
  aiInput.value = ''
  aiLoading.value = true
  scrollMsgs()
  try {
    const d = await aiGeneratePush(aiMsgs.value)
    aiMsgs.value.push({ role: 'assistant', content: d.reply })
    if (d.full) {
      aiDraft.value = d.reply
      aiCited.value = d.cited_bid_ids || []
      aiPreviewHtml.value = mdLite(d.reply)
    }
    scrollMsgs()
  } catch { /* 拦截器已提示 */ } finally {
    aiLoading.value = false
    scrollMsgs()
  }
}

function scrollMsgs() {
  nextTick(() => {
    const el = msgsRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

async function previewAi() {
  previewing.value = true
  try {
    const d = await previewManualPush({ kind: 'text', content: aiDraft.value, format: 'markdown' })
    aiPreviewHtml.value = mdLite(d.content)
    ElMessage.success(`预览已生成（${d.length.bytes}/${d.length.limit} 字节）`)
  } finally {
    previewing.value = false
  }
}

async function sendAiResult() {
  const r = await ElMessageBox.confirm(
    `确认发送？引用标讯 ${aiCited.value.length} 条。`, '发送确认', { type: 'warning' },
  ).catch(() => null)
  if (!r) return
  const res: any = await aiSendPush({
    content: aiDraft.value, bid_ids: aiCited.value, format: 'markdown',
  })
  ElMessage.success(res?.msg || '已发送')
}

onMounted(async () => {
  loadBids()
  noticeTypes.value = (await fetchNoticeTypes()) || []
  regions.value = (await fetchRegions(0)) || []
  fetchPushChannels().then(c => { channels.value = c }).catch(() => {})
})
</script>

<style scoped>
.filter-bar { margin-bottom: 8px; }
.mb12 { margin-bottom: 12px; }
.pag { margin-top: 12px; justify-content: flex-end; display: flex; }

/* Tab A */
.bid-layout { display: grid; grid-template-columns: 1fr 320px; gap: 14px; }
.sel-panel { border: 1px solid #ebeef5; border-radius: 6px; padding: 12px; display: flex; flex-direction: column; gap: 10px; }
.sel-head { font-size: 14px; }
.sel-head b { color: #409eff; }
.sel-head b.over { color: #f56c6c; }
.sel-list { max-height: 320px; overflow: auto; display: flex; flex-direction: column; gap: 4px; }
.sel-item { display: flex; justify-content: space-between; align-items: center; background: #f5f7fa;
  border-radius: 4px; padding: 4px 8px; font-size: 12px; }
.sel-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.sel-ops { display: flex; flex-shrink: 0; }
.send-ops { display: flex; gap: 8px; }

/* Tab B */
.text-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.preset-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 10px; }
.preset-row .lbl { font-size: 13px; color: #606266; }
.text-ops { display: flex; gap: 14px; align-items: center; margin-top: 10px; flex-wrap: wrap; }
.len { font-size: 12px; color: #909399; }
.len.over { color: #f56c6c; font-weight: 600; }
.text-right { background: #f2f3f5; border-radius: 8px; padding: 14px; font-size: 13px; line-height: 1.7; min-height: 300px; }
.text-right :deep(.md-h) { font-weight: 600; margin-bottom: 6px; }
.text-right :deep(.md-p) { margin: 3px 0; }
.text-right :deep(ul) { padding-left: 18px; }
.text-right :deep(a) { color: #2b6de5; }

/* Tab C */
.ai-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.ai-chat { border: 1px solid #ebeef5; border-radius: 6px; display: flex; flex-direction: column; }
.ai-msgs { height: 420px; overflow: auto; padding: 14px; display: flex; flex-direction: column; gap: 12px; }
.ai-msg .ai-role { font-size: 12px; color: #909399; margin-bottom: 4px; }
.ai-msg .ai-body { padding: 10px 12px; border-radius: 6px; font-size: 13px; line-height: 1.7;
  white-space: pre-wrap; word-break: break-word; max-width: 92%; }
.ai-msg.user .ai-body { background: #ecf5ff; align-self: flex-end; }
.ai-msg.user { align-items: flex-end; display: flex; flex-direction: column; }
.ai-msg.assistant .ai-body { background: #f5f7fa; }
.ai-empty { color: #c0c4cc; font-size: 13px; text-align: center; margin-top: 160px; padding: 0 20px; }
.loading-dot { color: #909399; }
.ai-input { border-top: 1px solid #ebeef5; padding: 10px; display: flex; gap: 8px; }
.ai-input :deep(.el-textarea) { flex: 1; }
.ai-result { border: 1px solid #ebeef5; border-radius: 6px; padding: 14px; display: flex; flex-direction: column; gap: 10px; }
.ai-result-head { font-size: 14px; font-weight: 600; display: flex; justify-content: space-between; }
.cited { font-size: 12px; color: #67c23a; font-weight: 400; }
.len-row { display: flex; justify-content: space-between; font-size: 12px; }
.ai-result-ops { display: flex; gap: 8px; }
.ai-bubble { background: #f2f3f5; border-radius: 8px; padding: 12px; font-size: 13px; line-height: 1.7; }
.ai-bubble :deep(.md-h) { font-weight: 600; margin-bottom: 6px; }
.ai-bubble :deep(.md-p) { margin: 3px 0; }
.ai-bubble :deep(ul) { padding-left: 18px; }
.ai-bubble :deep(a) { color: #2b6de5; }
:deep(.pv-body) { line-height: 1.7; font-size: 13px; }
:deep(.pv-body .md-h) { font-weight: 600; margin-bottom: 6px; }
:deep(.pv-body .md-p) { margin: 3px 0; }
:deep(.pv-body ul) { padding-left: 18px; }
:deep(.pv-body a) { color: #2b6de5; }

@media (max-width: 1100px) {
  .bid-layout, .text-layout, .ai-layout { grid-template-columns: 1fr; }
}
</style>
