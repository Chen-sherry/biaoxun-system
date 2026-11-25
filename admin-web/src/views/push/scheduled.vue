<template>
  <div class="push-scheduled">
    <el-alert
      v-if="channels && !channels.wecom_configured"
      type="warning" :closable="false" class="mb12"
      title="企微 Webhook 未配置"
      description="服务器 backend/.env 中 WECOM_WEBHOOK 为空，测试发送与定时推送都不会真正发出。"
    />

    <!-- 三张模板卡片 -->
    <div class="cards">
      <el-card v-for="tpl in templates" :key="tpl.code" class="tpl-card" shadow="hover">
        <div class="card-head">
          <div>
            <div class="tpl-name">{{ meta[tpl.code]?.name || tpl.code }}</div>
            <div class="tpl-schedule">{{ meta[tpl.code]?.schedule }}</div>
          </div>
          <el-switch
            :model-value="tpl.enabled"
            active-text="启用" inactive-text="停用"
            @change="(v: any) => toggleEnabled(tpl, v)"
          />
        </div>

        <div class="tpl-title-preview">## {{ tpl.title }}</div>
        <div class="tpl-content-preview" v-html="mdLite(truncate(tpl.content, 160))"></div>

        <div class="last-exec" v-if="lastByCode[tpl.code]">
          上次执行：{{ fmtTime(lastByCode[tpl.code].push_time) }}
          <el-tag size="small" :type="lastByCode[tpl.code].status ? 'danger' : 'success'">
            {{ lastByCode[tpl.code].status ? '失败' : '成功' }}
          </el-tag>
        </div>
        <div class="last-exec" v-else>尚无执行记录</div>

        <div class="card-actions">
          <el-button type="primary" @click="openEditor(tpl)">编辑模板</el-button>
          <el-button @click="doPreview(tpl.code)" :loading="previewing === tpl.code">真实数据预览</el-button>
          <el-button @click="doTest(tpl.code)" :loading="testing === tpl.code" type="warning" plain>测试发送</el-button>
        </div>
      </el-card>
    </div>

    <!-- 编辑抽屉 -->
    <el-drawer v-model="drawer" :title="`编辑模板：${meta[editing?.code || '']?.name || ''}`" size="720px">
      <template v-if="editing">
        <el-form label-position="top">
          <el-form-item label="消息标题（发送时自动加 ## 前缀）">
            <el-input v-model="editing.title" placeholder="标题" />
          </el-form-item>

          <el-form-item label="正文模板（{变量} 会被真实数据替换）">
            <div class="vars">
              <el-button
                v-for="v in editing.variables" :key="v"
                size="small" round plain type="primary"
                @click="insertVar(v)"
              >{{ varLabel(v) }}</el-button>
            </div>
            <el-input
              ref="contentRef" v-model="editing.content" type="textarea" :rows="10"
              placeholder="模板正文" @input="liveRender"
            />
          </el-form-item>

          <div class="drawer-actions">
            <el-button @click="resetDefault">恢复默认文案</el-button>
            <el-button @click="liveRender" :loading="previewing === editing.code">用真实数据预览</el-button>
            <el-button type="warning" plain @click="doTest(editing.code, true)" :loading="testing === editing.code">测试发送</el-button>
            <el-button type="primary" @click="doSave" :loading="saving">保存模板</el-button>
          </div>
        </el-form>

        <!-- 预览：企微群消息气泡效果 -->
        <div class="preview-box">
          <div class="preview-label">
            效果预览
            <span class="len" :class="{ over: lengthInfo && !lengthInfo.ok }">
              {{ lengthInfo ? `${lengthInfo.bytes}/${lengthInfo.limit} 字节` : '' }}
            </span>
          </div>
          <div class="wecom-bubble">
            <div class="wecom-avatar">标</div>
            <div class="wecom-msg">
              <div class="wecom-name">标讯推送助手</div>
              <div class="wecom-card" v-html="previewHtml || '<span class=ph>点击「用真实数据预览」查看效果</span>'"></div>
            </div>
          </div>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  fetchPushTemplates, savePushTemplate, previewPushTemplate, testPushTemplate,
  fetchPushRecords, fetchPushChannels,
} from '@/api'
import { mdLite } from '@/utils/mdLite'

// 模板元信息（与 Celery 任务时间对应）
const meta: Record<string, { name: string; schedule: string }> = {
  daily_summary: { name: '每日推送', schedule: '每天 08:00 · 新增标讯汇总' },
  expiring_alert: { name: '到期预警', schedule: '每天 09:00 · 24h 内截止标讯' },
  archive_notice: { name: '归档通知', schedule: '每天 02:00 · 归档汇总' },
}
// 默认文案（与 SQL 种子一致）
const DEFAULTS: Record<string, { title: string; content: string }> = {
  daily_summary: {
    title: '📢 {date} 新增标讯汇总',
    content: '**新增数量**：{count} 条\n\n**Top 关键词**：\n{top_keywords}\n{top_regions}',
  },
  expiring_alert: {
    title: '⏰ {date} 截止时间临近预警',
    content: '**{count} 条标讯在 24 小时内截止报名**\n\n**样例**：\n{bid_list}',
  },
  archive_notice: {
    title: '📦 {date} 归档汇总',
    content: '**昨日归档标讯**：{count} 条\n\n{bid_list}',
  },
}

const templates = ref<any[]>([])
const lastByCode = reactive<Record<string, any>>({})
const channels = ref<any>(null)
const drawer = ref(false)
const editing = ref<any>(null)
const saving = ref(false)
const previewing = ref('')
const testing = ref('')
const previewHtml = ref('')
const lengthInfo = ref<any>(null)
const contentRef = ref()
// 缓存最近一次真实预览的变量，编辑时本地实时重渲染（不重复落库）
const cachedVars = ref<Record<string, string>>({})

function truncate(s: string, n: number) { return (s || '').length > n ? s.slice(0, n) + '…' : s }
function fmtTime(t?: string) { return t ? t.replace('T', ' ').slice(0, 16) : '' }
function varLabel(v: string) { return '{' + v + '}' }

async function load() {
  const [tpls, chans] = await Promise.all([fetchPushTemplates(), fetchPushChannels()])
  templates.value = tpls || []
  channels.value = chans
  // 最近执行记录（按模板 code 分组取最新）
  try {
    const rec = await fetchPushRecords({ page: 1, page_size: 100 })
    for (const r of rec.items || []) {
      if (r.template_code && !lastByCode[r.template_code]) lastByCode[r.template_code] = r
    }
  } catch { /* 记录查询失败不影响主功能 */ }
}

async function toggleEnabled(tpl: any, val: any) {
  await savePushTemplate(tpl.code, { enabled: !!val })
  tpl.enabled = !!val
  ElMessage.success(tpl.enabled ? '已启用，到点将正常推送' : '已停用，到点将跳过不发')
}

function openEditor(tpl: any) {
  editing.value = { ...tpl, variables: tpl.variables || [] }
  previewHtml.value = ''
  lengthInfo.value = null
  cachedVars.value = {}
  drawer.value = true
}

function insertVar(v: string) {
  const el = contentRef.value?.textarea || contentRef.value?.$el?.querySelector('textarea')
  const token = `{${v}}`
  const pos = el?.selectionStart ?? editing.value.content.length
  const c = editing.value.content
  editing.value.content = c.slice(0, pos) + token + c.slice(pos)
  liveRender()
}

function localRender(src: string): string {
  // 用缓存的真实变量本地替换（打字实时反馈）
  return (src || '').replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, (m, k) =>
    cachedVars.value[k] !== undefined ? cachedVars.value[k] : m,
  )
}

function liveRender() {
  if (!editing.value) return
  const full = `## ${localRender(editing.value.title)}\n${localRender(editing.value.content)}`
  previewHtml.value = cachedVars.value.__loaded ? mdLite(full) : ''
  lengthInfo.value = { bytes: new TextEncoder().encode(full).length, limit: 4096,
    ok: new TextEncoder().encode(full).length <= 4096 }
}

async function doPreview(code: string) {
  previewing.value = code
  try {
    const body: any = {}
    if (editing.value && editing.value.code === code) {
      body.title = editing.value.title
      body.content = editing.value.content
    }
    const d = await previewPushTemplate(code, body)
    if (editing.value && editing.value.code === code) {
      cachedVars.value = { ...(d.variables || {}), __loaded: '1' }
      previewHtml.value = mdLite(d.full)
      lengthInfo.value = d.length
    } else {
      // 卡片上的预览：临时打开抽屉展示
      const tpl = templates.value.find(t => t.code === code)
      openEditor(tpl)
      await new Promise(r => setTimeout(r, 100))
      cachedVars.value = { ...(d.variables || {}), __loaded: '1' }
      previewHtml.value = mdLite(d.full)
      lengthInfo.value = d.length
    }
    ElMessage.success('预览已生成（已记录一条预览日志）')
  } finally {
    previewing.value = ''
  }
}

async function doTest(code: string, fromDrawer = false) {
  const body: any = {}
  if (fromDrawer && editing.value) {
    body.title = editing.value.title
    body.content = editing.value.content
  }
  await ElMessageBox.confirm(
    '将按当前模板内容 + 真实数据发送一条 [测试] 消息到企业微信群，确认发送？',
    '测试发送', { type: 'warning' },
  )
  testing.value = code
  try {
    const r: any = await testPushTemplate(code, body)
    ElMessage.success(r?.msg || '测试消息已发送')
    await load()
  } finally {
    testing.value = ''
  }
}

async function doSave() {
  if (!editing.value) return
  saving.value = true
  try {
    await savePushTemplate(editing.value.code, {
      title: editing.value.title, content: editing.value.content,
    })
    ElMessage.success('模板已保存，次日到点按新文案执行')
    drawer.value = false
    await load()
  } finally {
    saving.value = false
  }
}

function resetDefault() {
  const d = DEFAULTS[editing.value.code]
  if (!d) return
  editing.value.title = d.title
  editing.value.content = d.content
  liveRender()
}

onMounted(load)
</script>

<style scoped>
.mb12 { margin-bottom: 12px; }
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 14px; }
.tpl-card :deep(.el-card__body) { display: flex; flex-direction: column; gap: 10px; }
.card-head { display: flex; justify-content: space-between; align-items: flex-start; }
.tpl-name { font-size: 16px; font-weight: 600; }
.tpl-schedule { font-size: 12px; color: #909399; margin-top: 4px; }
.tpl-title-preview { font-weight: 600; font-size: 14px; color: #303133; }
.tpl-content-preview { font-size: 13px; color: #606266; line-height: 1.6; min-height: 60px; }
.last-exec { font-size: 12px; color: #909399; display: flex; gap: 8px; align-items: center; }
.card-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.vars { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }
.drawer-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
.preview-box { margin-top: 8px; }
.preview-label { font-size: 13px; color: #909399; margin-bottom: 8px; display: flex; justify-content: space-between; }
.len.over { color: #f56c6c; font-weight: 600; }
.wecom-bubble { display: flex; gap: 10px; background: #f2f3f5; padding: 14px; border-radius: 8px; }
.wecom-avatar { width: 36px; height: 36px; border-radius: 4px; background: #2b6de5; color: #fff;
  display: flex; align-items: center; justify-content: center; font-size: 15px; flex-shrink: 0; }
.wecom-name { font-size: 12px; color: #909399; margin-bottom: 4px; }
.wecom-card { background: #fff; border-radius: 6px; padding: 10px 12px; font-size: 13px; line-height: 1.7; }
.wecom-card :deep(.md-h) { font-weight: 600; margin-bottom: 6px; }
.wecom-card :deep(.md-p) { margin: 2px 0; }
.wecom-card :deep(.md-gap) { height: 8px; }
.wecom-card :deep(.md-quote) { border-left: 3px solid #d0d5e0; padding-left: 8px; color: #606266; margin: 2px 0; }
.wecom-card :deep(ul) { margin: 4px 0; padding-left: 18px; }
.wecom-card :deep(a) { color: #2b6de5; text-decoration: none; }
.ph { color: #c0c4cc; }
</style>
