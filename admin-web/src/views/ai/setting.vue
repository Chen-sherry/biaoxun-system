<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchAISettings, saveAISetting, testAIConnection } from '@/api'
import { Top, Bottom } from '@element-plus/icons-vue'

// ========== Provider 预设 ==========
// 选 Provider 自动填 base_url；自定义则全手填
const PROVIDERS = [
  { value: 'deepseek', label: 'DeepSeek (深度求索)', base_url: 'https://api.deepseek.com/v1',
    hint: '推荐：deepseek-chat（通用）/ deepseek-reasoner（推理）' },
  { value: 'doubao',   label: '豆包 / 火山引擎',     base_url: 'https://ark.cn-beijing.volces.com/api/v3',
    hint: '模型名填 Endpoint ID，如 ep-xxxxx' },
  { value: 'qwen',     label: '通义千问 / DashScope', base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    hint: 'qwen-plus / qwen-max / qwen-turbo' },
  { value: 'openrouter', label: 'OpenRouter',        base_url: 'https://openrouter.ai/api/v1',
    hint: '聚合多模型，API Key 在 openrouter.ai 申请' },
  { value: 'custom',   label: '自定义（兼容 OpenAI）', base_url: '',
    hint: '只要接口兼容 /chat/completions 就能接' },
]
const providerMeta = (p: string) => PROVIDERS.find(x => x.value === p)

// ========== 场景配置 ==========
// 4 个 model key，每个独立一张卡片
const SCENES = [
  { key: 'model.chat_system',   name: 'AI 悬浮球 / 对话', icon: '💬', tip: '主模型，负责聊天 + 工具调用' },
  { key: 'model.search',        name: 'AI 检索',         icon: '🔍', tip: '把大白话转成检索条件 + 结果打分' },
  { key: 'model.push_generate', name: '推送文案 AI',     icon: '📧', tip: '每天给订阅用户生成推送文案' },
  { key: 'model.extract_ai',    name: '字段补提取 AI',   icon: '📑', tip: '爬虫兜底：补金额/分类/采购人' },
]

// ========== 状态 ==========
const loading = ref(false)
// 每个 scene 的表单状态：{ provider, base_url, api_key, model }
const scenes = ref<Record<string, any>>({})
// prompt 草稿：key → text
const prompts = ref<Record<string, string>>({})
// 基础参数
const params = ref<Record<string, string>>({})
// 当前选中的主 Prompt（大 textarea 展示）
const activePromptKey = ref('prompt.chat_system')
const promptKeys = computed(() => Object.keys(prompts.value))
// 全局展开：默认只展开 chat_system
const expanded = ref<Record<string, boolean>>({
  'model.chat_system': true,
  'model.search': false,
  'model.push_generate': false,
  'model.extract_ai': false,
})

async function load() {
  loading.value = true
  try {
    const data: any = await fetchAISettings()
    const flat: any[] = data?.flat || []
    for (const row of flat) {
      // admin API 返回字段名是 row.key，不是 row.setting_key
      const k = row.key ?? row.setting_key
      if (row.idx_set === 'model') {
        try {
          const j = JSON.parse(row.value || '{}')
          scenes.value[k] = {
            provider: j.provider || 'deepseek',
            base_url: j.base_url || '',
            api_key: j.api_key || '',
            model: j.model || '',
          }
        } catch {
          scenes.value[k] = { provider: 'deepseek', base_url: '', api_key: '', model: '' }
        }
      } else if (row.idx_set === 'prompt') {
        prompts.value[k] = row.value || ''
      } else if (row.idx_set === 'param') {
        params.value[k] = row.value || ''
      }
    }
    // 确保所有 scene 都有初始值（DB 没配置的兜底）
    for (const s of SCENES) {
      if (!scenes.value[s.key]) {
        scenes.value[s.key] = { provider: 'deepseek', base_url: 'https://api.deepseek.com/v1', api_key: '', model: 'deepseek-chat' }
      }
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '加载失败')
  } finally { loading.value = false }
}

function toggleExpand(k: string) {
  expanded.value[k] = !expanded.value[k]
}

// Provider 变更 → 自动填 base_url（custom 除外）
function onProviderChange(k: string) {
  const s = scenes.value[k]
  const meta = providerMeta(s.provider)
  if (meta && meta.value !== 'custom') s.base_url = meta.base_url
}

// ========== 保存 ==========
async function saveScene(k: string) {
  const s = scenes.value[k]
  if (!s.base_url || !s.model) {
    ElMessage.warning('Base URL 和模型名不能为空')
    return
  }
  try {
    await saveAISetting(k, {
      value: JSON.stringify({
        provider: s.provider, base_url: s.base_url,
        api_key: s.api_key, model: s.model,
      }, null, 2),
    })
    ElMessage.success('已保存（立即生效）')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  }
}

async function savePrompt() {
  try {
    await saveAISetting(activePromptKey.value, { value: prompts.value[activePromptKey.value] ?? '' })
    ElMessage.success('Prompt 已保存')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  }
}

async function saveParam(k: string) {
  try {
    await saveAISetting(k, { value: params.value[k] ?? '' })
    ElMessage.success('已保存')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  }
}

// ========== 测试连接 ==========
const testLoading = ref<Record<string, boolean>>({})
async function testScene(k: string) {
  const s = scenes.value[k]
  if (!s.base_url || !s.api_key || !s.model) {
    ElMessage.warning('请先填完 Base URL / API Key / 模型名')
    return
  }
  testLoading.value[k] = true
  try {
    const res: any = await testAIConnection({
      base_url: s.base_url, api_key: s.api_key, model: s.model,
      temperature: 0, timeout: 15,
    })
    // request 拦截器已解包
    if (res?.ok) ElMessage.success(`✅ 连通！${res.model} · ${res.latency_ms}ms`)
    else ElMessage.error(`❌ ${res?.reason || '连接失败'}`)
  } catch (e: any) {
    ElMessage.error(e?.message || '测试失败')
  } finally { testLoading.value[k] = false }
}

onMounted(load)
</script>

<template>
  <div class="ai-setting-page">
    <div class="page-head">
      <h2>AI 设置</h2>
      <p class="desc">选择模型提供商 → 填 API Key → 给每个业务场景分配模型。改动立即生效。</p>
    </div>

    <!-- ========== 一、模型接入（4 场景卡片） ========== -->
    <div class="section">
      <div class="section-title">
        <span class="num">1</span>
        <span>模型接入</span>
        <span class="sub">（选 Provider → 填 Key → 分配场景）</span>
      </div>

      <div v-for="s in SCENES" :key="s.key" class="scene-card">
        <div class="scene-head" @click="toggleExpand(s.key)">
          <div class="scene-left">
            <span class="scene-icon">{{ s.icon }}</span>
            <span class="scene-name">{{ s.name }}</span>
            <span class="scene-key">{{ s.key }}</span>
          </div>
          <div class="scene-right">
            <template v-if="expanded[s.key]">
              <el-icon><Top /></el-icon>
            </template>
            <template v-else>
              <el-icon><Bottom /></el-icon>
            </template>
          </div>
        </div>

        <div v-if="expanded[s.key]" class="scene-body">
          <div v-if="s.tip" class="scene-tip">{{ s.tip }}</div>

          <el-form :model="scenes[s.key]" label-width="110px" size="default">
            <el-form-item label="服务商">
              <el-select v-model="scenes[s.key].provider" style="width: 320px"
                @change="onProviderChange(s.key)">
                <el-option v-for="p in PROVIDERS" :key="p.value" :label="p.label" :value="p.value" />
              </el-select>
              <span v-if="providerMeta(scenes[s.key].provider)?.hint" class="form-hint">
                {{ providerMeta(scenes[s.key].provider)?.hint }}
              </span>
            </el-form-item>

            <el-form-item label="Base URL">
              <el-input v-model="scenes[s.key].base_url" placeholder="如 https://api.deepseek.com/v1" style="width: 420px" />
              <span class="form-hint">接口根地址，选 Provider 会自动填；自定义时手动输入</span>
            </el-form-item>

            <el-form-item label="API Key">
              <el-input v-model="scenes[s.key].api_key" type="password" show-password
                placeholder="sk-xxxxxxxxxxxxxxxxxxxxxxxx" style="width: 420px" />
              <div v-if="!scenes[s.key].api_key" class="warn-hint">
                🔴 当前页面未配置 → 系统自动走服务器 <code>backend/.env</code> 里的默认 <code>DEEPSEEK_API_KEY</code>（正在生效，余额在扣）。
                在这里填新 key 并保存 → 覆盖旧 key，立即生效。
              </div>
              <div v-else class="ok-hint">
                ✅ 已在本页面配置，保存后会覆盖服务器 .env 默认值
              </div>
            </el-form-item>

            <el-form-item label="模型名">
              <el-input v-model="scenes[s.key].model" placeholder="如 deepseek-chat" style="width: 420px" />
              <span class="form-hint">
                <template v-if="scenes[s.key].provider === 'deepseek'">
                  deepseek-chat（通用）/ deepseek-reasoner（推理）
                </template>
                <template v-else-if="scenes[s.key].provider === 'doubao'">
                  火山引擎控制台创建的 Endpoint ID（ep-xxxx）
                </template>
                <template v-else-if="scenes[s.key].provider === 'qwen'">
                  qwen-plus / qwen-max / qwen-turbo
                </template>
              </span>
            </el-form-item>

            <el-form-item label=" ">
              <el-button type="primary" :loading="testLoading[s.key]" @click="testScene(s.key)">
                🔌 测试连接
              </el-button>
              <el-button type="success" @click="saveScene(s.key)" style="margin-left:8px">💾 保存</el-button>
              <span class="form-hint">先测试连通再保存更稳妥</span>
            </el-form-item>
          </el-form>
        </div>
      </div>
    </div>

    <!-- ========== 二、全局参数 ========== -->
    <div class="section">
      <div class="section-title">
        <span class="num">2</span>
        <span>全局参数</span>
        <span class="sub">（控制 AI 调用行为，一般不用改）</span>
      </div>
      <div class="params-grid">
        <div class="param-item" v-for="(label, key) in {
          'param.chat_daily_limit': '每日对话上限（会员）',
          'param.llm_temperature': 'Temperature（0 保守 → 1 发散）',
          'param.llm_max_tokens': '单次回复上限 tokens',
          'param.llm_timeout_s': '请求超时（秒）',
          'param.llm_max_retries': '失败重试次数',
        }" :key="key">
          <div class="param-label">{{ label }}</div>
          <div class="param-row">
            <el-input v-model="params[key]" size="small" style="width: 140px" />
            <el-button size="small" type="success" @click="saveParam(key)">保存</el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- ========== 三、系统提示词 ========== -->
    <div class="section">
      <div class="section-title">
        <span class="num">3</span>
        <span>系统提示词（Prompt）</span>
        <span class="sub">（控制 AI 的"人设"和输出风格）</span>
      </div>
      <div class="prompt-wrap">
        <div class="prompt-tabs">
          <el-radio-group v-model="activePromptKey" size="small">
            <el-radio-button v-for="k in promptKeys" :key="k" :value="k">{{
              k === 'prompt.chat_system' ? '💬 对话主 Prompt' :
              k === 'prompt.push_generate' ? '📧 推送文案' :
              k === 'prompt.extract_ai' ? '📑 字段补提取' :
              k === 'prompt.search_translate' ? '🔍 检索转译' :
              k === 'prompt.search_score' ? '⭐ 相关性评分' : k
            }}</el-radio-button>
          </el-radio-group>
          <el-button type="success" size="small" @click="savePrompt" style="margin-left:auto">💾 保存当前 Prompt</el-button>
        </div>
        <el-input
          v-model="prompts[activePromptKey]"
          type="textarea"
          :autosize="{ minRows: 12, maxRows: 30 }"
          resize="none"
          class="prompt-editor"
        />
      </div>
    </div>

    <!-- ========== 页脚 ========== -->
    <div class="footer-hint">
      💡 改完立即生效（60 秒进程内缓存自动刷新）· API Key 加密存在数据库中 · 想回滚？改回原值保存即可
    </div>
  </div>
</template>

<style scoped>
.ai-setting-page { padding: 20px; max-width: 960px; }
.page-head h2 { margin: 0 0 4px; font-size: 20px; }
.page-head .desc { margin: 0 0 20px; font-size: 13px; color: var(--el-text-color-secondary); }

.section { margin-bottom: 28px; }
.section-title {
  display: flex; align-items: baseline; gap: 8px; margin-bottom: 14px;
  font-weight: 600; font-size: 15px;
}
.section-title .num {
  display: inline-flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; border-radius: 50%; background: #409eff; color: #fff;
  font-size: 12px; font-weight: 700; flex-shrink: 0;
}
.section-title .sub { font-weight: 400; font-size: 12px; color: var(--el-text-color-secondary); }

/* ===== 场景卡片 ===== */
.scene-card {
  border: 1px solid var(--el-border-color-lighter); border-radius: 10px;
  margin-bottom: 12px; background: #fff; overflow: hidden;
}
.scene-head {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 18px; cursor: pointer; user-select: none;
  background: #fafbfc; transition: background .15s;
}
.scene-head:hover { background: #f0f7ff; }
.scene-left { display: flex; align-items: center; gap: 10px; }
.scene-icon { font-size: 18px; }
.scene-name { font-weight: 600; font-size: 14px; }
.scene-key {
  font-family: ui-monospace, Consolas, monospace; font-size: 11.5px;
  color: #0369a1; background: #e0f2fe; padding: 1px 8px; border-radius: 4px;
}
.scene-body { padding: 16px 18px 20px; border-top: 1px solid var(--el-border-color-lighter); }
.scene-tip {
  font-size: 12px; color: var(--el-text-color-secondary); margin-bottom: 12px;
  padding: 8px 12px; background: #f8fafc; border-radius: 6px; border-left: 3px solid #409eff;
}
.form-hint {
  margin-left: 10px; font-size: 12px; color: var(--el-text-color-secondary);
}
.warn-hint {
  margin-top: 6px; font-size: 12px; color: #991b1b;
  padding: 8px 12px; background: #fef2f2; border-radius: 6px; border-left: 3px solid #dc2626;
  line-height: 1.5;
}
.warn-hint code {
  background: #fee2e2; padding: 1px 5px; border-radius: 3px; font-family: ui-monospace, Consolas, monospace;
  font-size: 11.5px;
}
.ok-hint {
  margin-top: 6px; font-size: 12px; color: #065f46;
  padding: 6px 10px; background: #ecfdf5; border-radius: 6px; border-left: 3px solid #059669;
}

/* ===== 全局参数 ===== */
.params-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
}
.param-item {
  border: 1px solid var(--el-border-color-lighter); border-radius: 8px;
  padding: 12px 14px; background: #fff;
}
.param-label { font-size: 13px; margin-bottom: 8px; font-weight: 500; }
.param-row { display: flex; gap: 8px; align-items: center; }

/* ===== Prompt ===== */
.prompt-wrap { border: 1px solid var(--el-border-color-lighter); border-radius: 10px; padding: 14px; background: #fff; }
.prompt-tabs { display: flex; gap: 10px; align-items: center; margin-bottom: 12px; }
.prompt-editor :deep(.el-textarea__inner) {
  font-family: ui-monospace, Consolas, monospace; font-size: 13px; line-height: 1.6;
  background: #fafafa;
}

.footer-hint {
  margin-top: 10px; padding: 12px 16px; border-radius: 8px;
  background: #fffbeb; border: 1px solid #fef3c7;
  font-size: 12.5px; color: #92400e;
}
</style>
