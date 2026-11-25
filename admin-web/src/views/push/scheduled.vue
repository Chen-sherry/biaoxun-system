<template>
  <div class="push-scheduled">
    <el-alert
      v-if="channels && !channels.wecom_configured"
      type="warning" :closable="false" class="mb12"
      title="企微 Webhook 未配置"
      description="服务器 backend/.env 中 WECOM_WEBHOOK 为空，测试发送与定时推送都不会真正发出。"
    />

    <div class="toolbar">
      <span class="hint">执行时间改动即时生效（每 5 分钟自检，无需重启服务）</span>
      <div>
        <el-button @click="openVars">变量管理</el-button>
        <el-button type="primary" @click="openCreate">＋ 新增定时推送</el-button>
      </div>
    </div>

    <!-- 模板卡片 -->
    <div class="cards">
      <el-card v-for="tpl in templates" :key="tpl.code" class="tpl-card" shadow="hover">
        <div class="card-head">
          <div>
            <div class="tpl-name">
              {{ tpl.name || tpl.code }}
              <el-tag size="small" :type="tpl.kind === 'custom' ? 'warning' : 'info'" effect="plain">
                {{ tpl.kind === 'custom' ? '自定义' : '内置' }}
              </el-tag>
            </div>
            <div class="tpl-schedule">
              <template v-if="tpl.kind === 'custom' && tpl.frequency === 'weekly'">
                每周{{ WEEK_CN[tpl.weekday ?? 0] }}
              </template>
              <template v-else>每天</template>
            </div>
          </div>
          <el-switch
            :model-value="tpl.enabled"
            active-text="启用" inactive-text="停用"
            @change="(v: any) => toggleEnabled(tpl, v)"
          />
        </div>

        <!-- 执行时间（可改，改动即保存） -->
        <div class="time-row">
          <el-time-picker
            v-model="tpl.schedule_time"
            format="HH:mm" value-format="HH:mm"
            placeholder="执行时间" style="width: 110px"
            @change="(v: string | null) => saveTime(tpl, v)"
          />
          <span class="time-label">执行</span>
          <span v-if="tpl.schedule_is_default" class="default-tag">默认时间</span>
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
          <el-button
            v-if="tpl.kind === 'custom'"
            type="danger" link @click="onDelete(tpl)"
          >删除</el-button>
        </div>
      </el-card>
    </div>

    <!-- 编辑抽屉 -->
    <el-drawer v-model="drawer" :title="`编辑模板：${editing?.name || editing?.code || ''}`" size="720px">
      <template v-if="editing">
        <el-form label-position="top">
          <div class="edit-meta">
            <el-form-item label="显示名" class="half">
              <el-input v-model="editing.name" />
            </el-form-item>
            <el-form-item label="执行时间" class="half">
              <el-time-picker v-model="editing.schedule_time" format="HH:mm" value-format="HH:mm"
                placeholder="执行时间" style="width: 100%" />
            </el-form-item>
            <el-form-item v-if="editing.kind === 'custom'" label="频率" class="half">
              <el-select v-model="editing.frequency" style="width: 100%">
                <el-option value="daily" label="每天" />
                <el-option value="weekly" label="每周" />
              </el-select>
            </el-form-item>
            <el-form-item
              v-if="editing.kind === 'custom' && editing.frequency === 'weekly'"
              label="星期" class="half"
            >
              <el-select v-model="editing.weekday" style="width: 100%">
                <el-option v-for="(cn, i) in WEEK_CN" :key="i" :value="i" :label="'每' + cn" />
              </el-select>
            </el-form-item>
          </div>

          <el-form-item label="消息标题（发送时自动加 ## 前缀）">
            <el-input v-model="editing.title" placeholder="标题" />
          </el-form-item>

          <el-form-item :label="editing.kind === 'custom' ? '正文模板（可用变量 {date} {count}）' : '正文模板（{变量} 会被真实数据替换）'">
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
            <el-button type="success" plain @click="doSaveAsDefault" :loading="saving">
              应用为默认模板
            </el-button>
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

    <!-- 变量管理（与新增按钮同级入口） -->
    <el-dialog v-model="varsDlg" title="变量管理" width="760px" destroy-on-close>
      <el-alert type="info" :closable="false" class="mb12"
        title="模板正文/标题中写 {变量名}，发送时替换为真实数据；点击「复制」拿到变量写法" />
      <el-table :data="varsList" size="small">
        <el-table-column label="变量" width="120">
          <template #default="{ row }">
            <el-tag type="primary" effect="plain">{{ '{' + row.code + '}' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" width="120" />
        <el-table-column label="说明" min-width="260">
          <template #default="{ row }">
            <div style="white-space: pre-line; line-height: 1.5">{{ row.desc }}</div>
          </template>
        </el-table-column>
        <el-table-column label="示例" min-width="160">
          <template #default="{ row }">
            <div style="white-space: pre-line; line-height: 1.5; color: var(--el-text-color-secondary)">
              {{ row.example }}
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="scope" label="适用模板" width="130" />
        <el-table-column label="" width="70">
          <template #default="{ row }">
            <el-button link type="primary" @click="copyVar(row.code)">复制</el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="varsDlg = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 新增定时推送 -->
    <el-dialog v-model="createDlg" title="新增定时推送" width="560px" destroy-on-close>
      <el-form label-width="90px" :model="createForm">
        <el-form-item label="编码 code" required>
          <el-input v-model="createForm.code" placeholder="小写字母开头，如 weekly_report" />
        </el-form-item>
        <el-form-item label="显示名" required>
          <el-input v-model="createForm.name" placeholder="如：每周汇总" />
        </el-form-item>
        <el-form-item label="执行时间" required>
          <el-time-picker v-model="createForm.schedule_time" format="HH:mm" value-format="HH:mm"
            placeholder="每天几点发" style="width: 100%" />
        </el-form-item>
        <el-form-item label="频率">
          <el-select v-model="createForm.frequency" style="width: 140px">
            <el-option value="daily" label="每天" />
            <el-option value="weekly" label="每周" />
          </el-select>
          <el-select
            v-if="createForm.frequency === 'weekly'"
            v-model="createForm.weekday" style="width: 140px; margin-left: 8px"
          >
            <el-option v-for="(cn, i) in WEEK_CN" :key="i" :value="i" :label="'每' + cn" />
          </el-select>
        </el-form-item>
        <el-form-item label="消息标题" required>
          <el-input v-model="createForm.title" placeholder="如：本周标讯汇总" />
        </el-form-item>
        <el-form-item label="正文" required>
          <el-input v-model="createForm.content" type="textarea" :rows="7"
            placeholder="支持变量 {date}（当天日期）、{count}（数量）、{bid_list}（最新3条标讯卡片）；点右上「变量管理」看全部" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="createForm.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDlg = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="doCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  fetchPushTemplates, savePushTemplate, createPushTemplate, deletePushTemplate,
  previewPushTemplate, testPushTemplate, fetchPushRecords, fetchPushChannels,
  fetchPushVariables,
} from '@/api'
import { mdLite } from '@/utils/mdLite'

const WEEK_CN = ['一', '二', '三', '四', '五', '六', '日']

// 内置任务说明（仅用于兜底显示，实际时间以库里为准）
const meta: Record<string, { name: string }> = {
  daily_summary: { name: '每日推送' },
  expiring_alert: { name: '到期预警' },
  archive_notice: { name: '归档通知' },
}
// 内置默认文案（恢复默认用）
const DEFAULTS: Record<string, { title: string; content: string }> = {
  daily_summary: {
    title: '今日新增{count}条标讯',
    content: '**最新标讯**：\n{bid_list}',
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
const cachedVars = ref<Record<string, string>>({})

const createDlg = ref(false)

// ===== 变量管理（顶栏入口，与新增按钮同级） =====
const varsDlg = ref(false)
const varsList = ref<any[]>([])
async function openVars() {
  varsDlg.value = true
  if (!varsList.value.length) {
    try {
      const r: any = await fetchPushVariables()
      // 拦截器已解包 response.data，r 直接就是数组（兼容包了一层的返回）
      varsList.value = Array.isArray(r) ? r : (r?.data || [])
    } catch { /* 弹窗已开，空表提示即可 */ }
  }
}
async function copyVar(code: string) {
  const text = `{${code}}`
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success(`已复制 ${text}`)
  } catch {
    ElMessage.info(`变量写法：${text}`)
  }
}
const creating = ref(false)
const createForm = reactive({
  code: '', name: '', schedule_time: '', frequency: 'daily',
  weekday: 0, title: '', content: '', enabled: true,
})

function truncate(s: string, n: number) { return (s || '').length > n ? s.slice(0, n) + '…' : s }
function fmtTime(t?: string) { return t ? t.replace('T', ' ').slice(0, 16) : '' }
function varLabel(v: string) { return '{' + v + '}' }

async function load() {
  const [tpls, chans] = await Promise.all([fetchPushTemplates(), fetchPushChannels()])
  templates.value = tpls || []
  channels.value = chans
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

async function saveTime(tpl: any, v: string | null) {
  if (!v) return
  await savePushTemplate(tpl.code, { schedule_time: v })
  tpl.schedule_is_default = false
  ElMessage.success(`执行时间已改为每天 ${v}，即时生效`)
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
  const token = varLabel(v)
  const pos = el?.selectionStart ?? editing.value.content.length
  const c = editing.value.content
  editing.value.content = c.slice(0, pos) + token + c.slice(pos)
  liveRender()
}

function localRender(src: string): string {
  return (src || '').replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, (m, k) =>
    cachedVars.value[k] !== undefined ? cachedVars.value[k] : m,
  )
}

function liveRender() {
  if (!editing.value) return
  const full = `## ${localRender(editing.value.title)}\n${localRender(editing.value.content)}`
  previewHtml.value = cachedVars.value.__loaded ? mdLite(full) : ''
  const bytes = new TextEncoder().encode(full).length
  lengthInfo.value = { bytes, limit: 4096, ok: bytes <= 4096 }
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
  ).catch(() => null)
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
      name: editing.value.name,
      title: editing.value.title,
      content: editing.value.content,
      schedule_time: editing.value.schedule_time,
      frequency: editing.value.frequency,
      weekday: editing.value.weekday,
    })
    ElMessage.success('模板已保存，执行时间即时生效')
    drawer.value = false
    await load()
  } finally {
    saving.value = false
  }
}

/** 应用为默认模板：保存当前文案 + 写入默认快照（恢复默认时回到这份） */
async function doSaveAsDefault() {
  if (!editing.value) return
  saving.value = true
  try {
    await savePushTemplate(editing.value.code, {
      name: editing.value.name,
      title: editing.value.title,
      content: editing.value.content,
      schedule_time: editing.value.schedule_time,
      frequency: editing.value.frequency,
      weekday: editing.value.weekday,
      apply_default: true,
    })
    editing.value.default_title = editing.value.title
    editing.value.default_content = editing.value.content
    ElMessage.success('已保存并应用为默认模板')
    drawer.value = false
    await load()
  } finally {
    saving.value = false
  }
}

function resetDefault() {
  // 优先用库里的默认快照（用户点过「应用为默认模板」），否则用内置出厂文案
  const snap = editing.value.default_content
    ? { title: editing.value.default_title || '', content: editing.value.default_content }
    : DEFAULTS[editing.value.code]
  if (!snap) return
  editing.value.title = snap.title
  editing.value.content = snap.content
  liveRender()
  ElMessage.info('已填入默认文案（点「保存模板」生效）')
}

function openCreate() {
  Object.assign(createForm, {
    code: 'custom_' + Math.random().toString(36).slice(2, 8),
    name: '', schedule_time: '09:30', frequency: 'daily',
    weekday: 0, title: '', content: '', enabled: true,
  })
  createDlg.value = true
}

async function doCreate() {
  creating.value = true
  try {
    const r: any = await createPushTemplate({ ...createForm })
    ElMessage.success(r?.msg || '已创建')
    createDlg.value = false
    await load()
  } finally {
    creating.value = false
  }
}

async function onDelete(tpl: any) {
  await ElMessageBox.confirm(
    `删除自定义定时推送「${tpl.name || tpl.code}」？历史推送记录会保留。`, '删除确认',
    { type: 'warning' },
  ).catch(() => null)
  await deletePushTemplate(tpl.code)
  ElMessage.success('已删除')
  await load()
}

onMounted(load)
</script>

<style scoped>
.mb12 { margin-bottom: 12px; }
.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.hint { font-size: 12px; color: #909399; }
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 14px; }
.tpl-card :deep(.el-card__body) { display: flex; flex-direction: column; gap: 10px; }
.card-head { display: flex; justify-content: space-between; align-items: flex-start; }
.tpl-name { font-size: 16px; font-weight: 600; display: flex; gap: 8px; align-items: center; }
.tpl-schedule { font-size: 12px; color: #909399; margin-top: 4px; }
.time-row { display: flex; align-items: center; gap: 8px; }
.time-label { font-size: 13px; color: #606266; }
.default-tag { font-size: 11px; color: #c0c4cc; border: 1px dashed #dcdfe6; border-radius: 3px; padding: 1px 5px; }
.tpl-title-preview { font-weight: 600; font-size: 14px; color: #303133; }
.tpl-content-preview { font-size: 13px; color: #606266; line-height: 1.6; min-height: 48px; }
.last-exec { font-size: 12px; color: #909399; display: flex; gap: 8px; align-items: center; }
.card-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.edit-meta { display: grid; grid-template-columns: 1fr 1fr; gap: 0 12px; }
.half { margin-bottom: 8px; }
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
