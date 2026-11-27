<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { TabPane, FormInstance } from 'element-plus'
import {
  fetchAISettings, saveAISetting, fetchAISnapshots, rollbackAISetting,
  testAIConnection, tryAIPrompt,
} from '@/api'

// ===== 状态 =====
const loading = ref(false)
const groups = ref<Record<string, any[]>>({ model: [], prompt: [], param: [] })
const activeTab = ref<'model' | 'prompt' | 'param' | 'snapshot'>('model')

// 每个 setting 存 draft（value + remark）
const drafts = ref<Record<string, { value: string; remark: string }>>({})
function initDraft(rows: any[]) {
  for (const r of rows) {
    drafts.value[r.key] = {
      value: r.value ?? '',
      remark: r.remark ?? '',
    }
  }
}

function setDraft(key: string, v: any, field: 'value' | 'remark' = 'value') {
  const d = drafts.value[key]
  if (d) d[field] = v
}

async function load() {
  loading.value = true
  try {
    const res = await fetchAISettings()
    if (res?.code === 0) {
      const g = res.data?.groups || { model: [], prompt: [], param: [] }
      groups.value = g
      initDraft(res.data?.flat || [])
    } else {
      ElMessage.error(res?.msg || '加载失败')
    }
  } finally { loading.value = false }
}

// ===== 保存单条 =====
async function saveOne(key: string) {
  const d = drafts.value[key]
  if (d === undefined) return
  try {
    const res = await saveAISetting(key, { value: d.value ?? '', remark: d.remark })
    if (res?.code === 0) {
      ElMessage.success('已保存（60s 热更缓存，立即生效）')
    } else {
      ElMessage.error(res?.msg || '保存失败')
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  }
}

// ===== Tab 1: 模型（每行一个 JSON 编辑器 + 连通性测试）=====
const PROVIDERS = ['deepseek', 'doubao', 'qwen', 'openrouter', 'custom']

function parseJsonSafe(s: string): { ok: boolean; data?: any; err?: string } {
  if (!s || !s.trim()) return { ok: true, data: null }
  try { return { ok: true, data: JSON.parse(s) } }
  catch (e: any) { return { ok: false, err: String(e) } }
}

function testKey(key: string) {
  const d = drafts.value[key]
  const p = parseJsonSafe(d?.value || '')
  if (!p.ok) {
    ElMessage.error(`JSON 不合法：${p.err}`)
    return
  }
  if (!p.data?.api_key || !p.data?.base_url || !p.data?.model) {
    ElMessage.error('缺少 api_key / base_url / model')
    return
  }
  const payload = {
    base_url: p.data.base_url,
    api_key: p.data.api_key,
    model: p.data.model,
    temperature: 0,
    timeout: 15,
  }
  ElMessage.info('发起连通性测试…')
  testAIConnection(payload).then(res => {
    if (res?.code === 0) {
      const r = res.data
      if (r?.ok) {
        ElMessage.success(`✅ 连通！延迟 ${r.latency_ms}ms · ${r.model}`)
      } else {
        ElMessage.error(`❌ ${r.reason}（${r.latency_ms}ms）`)
      }
    } else ElMessage.error(res?.msg || '接口失败')
  }).catch(e => ElMessage.error(String(e)))
}

function jsonPretty(key: string) {
  const d = drafts.value[key]
  const p = parseJsonSafe(d?.value || '')
  if (p.ok && p.data) {
    drafts.value[key].value = JSON.stringify(p.data, null, 2)
  }
}

// ===== Tab 2: Prompt（选择 + textarea + 试运行）=====
const promptKey = ref('prompt.chat_system')
const promptKeys = computed(() =>
  groups.value.prompt?.map((r: any) => r.key) || [])
const promptInput = ref('你好，请先做自我介绍')
const promptTrying = ref(false)
const promptResult = ref<any>(null)

async function tryPrompt() {
  promptTrying.value = true
  promptResult.value = null
  try {
    const res = await tryAIPrompt({
      setting_key: promptKey.value,
      input_text: promptInput.value,
    })
    if (res?.code === 0) {
      promptResult.value = res.data
    } else {
      promptResult.value = { error: true, message: res?.msg }
    }
  } catch (e: any) {
    promptResult.value = { error: true, message: e?.response?.data?.detail || String(e) }
  } finally { promptTrying.value = false }
}

// ===== Tab 3: 参数 =====
// 数字直接用 el-input-number，但存的字符串；保存时原样发后端

// ===== Tab 4: 快照 =====
const snapKey = ref('prompt.chat_system')
const snapKeys = computed(() =>
  groups.value.flat?.filter((r: any) => r.value_type !== 'json').map((r: any) => r.key) || [])
const snapshots = ref<any[]>([])
const snapLoading = ref(false)

async function loadSnaps() {
  snapLoading.value = true
  try {
    const res = await fetchAISnapshots(snapKey.value)
    if (res?.code === 0) snapshots.value = res.data || []
    else ElMessage.error(res?.msg || '加载失败')
  } finally { snapLoading.value = false }
}

async function doRollback(snap: any) {
  try {
    await ElMessageBox.confirm(
      `回滚 ${snap.setting_key} 到 #${snap.id}？操作后当前值会被覆盖，但新快照会自动入历史。`,
      '确认回滚', { type: 'warning', confirmButtonText: '回滚' })
  } catch { return }
  const res = await rollbackAISetting(snap.setting_key, snap.id)
  if (res?.code === 0) {
    ElMessage.success('已回滚，立即生效')
    await load()
    await loadSnaps()
  } else ElMessage.error(res?.msg || '回滚失败')
}

onMounted(load)
</script>

<template>
  <div class="ai-setting-page">
    <div class="page-head">
      <h2>AI 设置</h2>
      <p class="desc">AI 相关配置（模型 / Prompt / 参数）在这里统一管理，改动立即生效（60s 热更缓存）。管理员 / 运营可编辑。</p>
    </div>

    <el-tabs v-model="activeTab" type="border-card" class="ai-tabs">
      <!-- ===== Tab 1: 模型 ===== -->
      <el-tab-pane label="模型" name="model">
        <div v-if="!groups.model?.length" class="empty-hint">暂无模型配置（种子 SQL 未执行？）</div>
        <div v-for="row in groups.model" :key="row.key" class="model-row">
          <div class="row-head">
            <div class="row-info">
              <span class="key-badge">{{ row.key }}</span>
              <span class="row-remark">{{ row.remark }}</span>
            </div>
            <div class="row-actions">
              <el-button link size="small" @click="jsonPretty(row.key)">格式化</el-button>
              <el-button size="small" type="primary" :loading="loading" @click="testKey(row.key)">
                连通性测试
              </el-button>
              <el-button size="small" type="success" @click="saveOne(row.key)">保存</el-button>
            </div>
          </div>
          <el-input
            :model-value="drafts[row.key]?.value"
            @update:model-value="(v: any) => setDraft(row.key, v)"
            type="textarea"
            :autosize="{ minRows: 5, maxRows: 12 }"
            resize="none"
            class="json-editor"
            placeholder='{"provider":"deepseek","base_url":"...","api_key":"","model":"deepseek-chat"}'
          />
          <div v-if="parseJsonSafe(drafts[row.key]?.value).ok === false" class="json-error">
            JSON 不合法：{{ parseJsonSafe(drafts[row.key]?.value).err }}
          </div>
        </div>
      </el-tab-pane>

      <!-- ===== Tab 2: Prompt ===== -->
      <el-tab-pane label="Prompt" name="prompt">
        <div class="prompt-wrap">
          <el-form inline>
            <el-form-item label="选择 Prompt">
              <el-select v-model="promptKey" style="width: 280px" @change="promptResult = null">
                <el-option v-for="k in promptKeys" :key="k" :label="k" :value="k" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button size="small" type="success" @click="saveOne(promptKey)">保存</el-button>
              <el-button size="small" @click="loadSnaps; snapKey = promptKey"
                style="margin-left:8px">看历史</el-button>
            </el-form-item>
          </el-form>
          <el-input
            :model-value="drafts[promptKey]?.value"
            @update:model-value="(v: any) => setDraft(promptKey, v)"
            type="textarea"
            :autosize="{ minRows: 14, maxRows: 26 }"
            resize="none"
            class="prompt-editor"
          />

          <!-- 试运行 -->
          <el-divider content-position="left">试运行</el-divider>
          <div class="try-box">
            <el-input v-model="promptInput" placeholder="喂给模型的示例输入" />
            <el-button type="primary" :loading="promptTrying" @click="tryPrompt">
              试运行 →
            </el-button>
          </div>
          <div v-if="promptResult" class="try-result">
            <div v-if="promptResult.error" class="try-err">
              ❌ {{ promptResult.message }}
            </div>
            <div v-else class="try-ok">
              <div class="try-meta">
                ✅ {{ promptResult.model }} · {{ promptResult.latency_ms }}ms
                <span v-if="promptResult.usage?.total_tokens">
                  · {{ promptResult.usage.total_tokens }} tokens
                </span>
              </div>
              <pre>{{ promptResult.content }}</pre>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- ===== Tab 3: 参数 ===== -->
      <el-tab-pane label="基础参数" name="param">
        <el-table :data="groups.param" size="small" class="param-table">
          <el-table-column prop="key" label="参数 Key" width="220" />
          <el-table-column label="值">
            <template #default="{ row }">
              <el-input
                :model-value="drafts[row.key]?.value"
                @update:model-value="(v: any) => setDraft(row.key, v)"
                size="small"
                style="width: 200px"
                :placeholder="row.value_type === 'number' ? '数字' : '值'"
              />
              <span class="vtype-tag">{{ row.value_type }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="remark" label="说明" />
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button size="small" type="success" @click="saveOne(row.key)">保存</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- ===== Tab 4: 快照 ===== -->
      <el-tab-pane label="变更历史 / 回滚" name="snapshot">
        <div class="snap-head">
          <el-select v-model="snapKey" style="width: 240px" @change="loadSnaps">
            <el-option v-for="k in snapKeys" :key="k" :label="k" :value="k" />
          </el-select>
          <el-button size="small" @click="loadSnaps">刷新</el-button>
        </div>
        <div v-if="snapLoading" class="empty-hint">加载中…</div>
        <el-table v-else :data="snapshots" size="small" class="snap-table">
          <el-table-column prop="id" label="#" width="60" />
          <el-table-column prop="created_at" label="时间" width="180" />
          <el-table-column prop="operator_name" label="操作人" width="120" />
          <el-table-column label="变更" min-width="320">
            <template #default="{ row }">
              <div class="snap-diff">
                <div class="snap-block old"><div class="lbl">旧</div><pre>{{ row.old_value?.slice(0, 120) }}</pre></div>
                <div class="snap-block new"><div class="lbl">新</div><pre>{{ row.new_value?.slice(0, 120) }}</pre></div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button size="small" @click="doRollback(row)">回滚</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.ai-setting-page { padding: 16px; }
.page-head h2 { margin: 0 0 6px; font-size: 18px; }
.page-head .desc { margin: 0 0 14px; font-size: 12.5px; color: var(--el-text-color-secondary); }

.ai-tabs { background: transparent; }

/* ===== 模型 ===== */
.model-row {
  border: 1px solid var(--el-border-color-lighter); border-radius: 8px;
  padding: 12px 14px; margin-bottom: 12px; background: #fff;
}
.row-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.row-info { display: flex; align-items: center; gap: 10px; }
.key-badge {
  background: #f0f9ff; color: #0369a1; padding: 2px 10px; border-radius: 999px;
  font-family: monospace; font-size: 12px; border: 1px solid #bae6fd;
}
.row-remark { font-size: 12.5px; color: var(--el-text-color-secondary); }
.row-actions { display: flex; gap: 6px; align-items: center; }
.json-editor :deep(.el-textarea__inner) { font-family: ui-monospace, Consolas, monospace; font-size: 12.5px; }
.json-error { margin-top: 6px; color: #dc2626; font-size: 12px; }
.empty-hint { color: var(--el-text-color-secondary); font-size: 13px; padding: 20px 0; text-align: center; }

/* ===== Prompt ===== */
.prompt-wrap .prompt-editor :deep(.el-textarea__inner) {
  font-family: ui-monospace, Consolas, monospace; font-size: 12.5px;
  line-height: 1.6; background: #fafafa;
}
.try-box { display: flex; gap: 8px; align-items: center; margin-top: 12px; }
.try-box .el-input { flex: 1; }
.try-result { margin-top: 12px; border: 1px solid var(--el-border-color-lighter); border-radius: 8px; padding: 12px; background: #fff; }
.try-result pre { white-space: pre-wrap; word-break: break-word; font-size: 12.5px; }
.try-meta { font-size: 12px; color: var(--el-text-color-secondary); margin-bottom: 6px; }
.try-err { color: #dc2626; font-size: 13px; }

/* ===== 参数 ===== */
.param-table { width: 100%; }
.vtype-tag {
  margin-left: 8px; font-size: 11px; padding: 1px 6px; border-radius: 4px;
  background: #f1f5f9; color: #475569; border: 1px solid #e2e8f0;
}

/* ===== 快照 ===== */
.snap-head { display: flex; gap: 8px; margin-bottom: 12px; align-items: center; }
.snap-table .snap-diff { display: flex; gap: 8px; }
.snap-table .snap-block {
  flex: 1; background: #fafafa; border-radius: 6px; padding: 6px 10px;
  border: 1px solid var(--el-border-color-lighter); min-width: 0;
}
.snap-table .snap-block pre {
  margin: 0; font-size: 12px; white-space: pre-wrap; word-break: break-word;
  font-family: ui-monospace, Consolas, monospace; max-height: 80px; overflow: hidden;
}
.snap-table .snap-block .lbl {
  font-size: 11px; font-weight: 700; margin-bottom: 4px; color: var(--el-text-color-secondary);
}
</style>
