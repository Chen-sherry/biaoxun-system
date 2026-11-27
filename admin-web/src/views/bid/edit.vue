<template>
  <div class="page-container">
    <div class="page-card">
      <el-page-header @back="router.back()" :content="isEdit ? '编辑标讯' : '新增标讯'" />

      <div v-if="suggestionChips.length" class="suggest-bar">
        <span class="suggest-title">建议（规则/源站提取，点击填入）：</span>
        <el-tag
          v-for="s in suggestionChips"
          :key="s.field"
          class="suggest-chip"
          type="success"
          effect="plain"
          @click="applyValue(s.field, s.value)"
        >{{ s.label }}：{{ s.display }}</el-tag>
      </div>

      <el-row :gutter="16" style="margin-top: 16px">
        <el-col :span="15">
          <el-form :model="form" :rules="rules" ref="formRef" label-width="110px">
            <el-form-item label="标题" prop="title">
              <el-input v-model="form.title" maxlength="500" show-word-limit />
            </el-form-item>
            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="项目编号">
                  <el-input v-model="form.project_code">
                    <template #append><el-button @click="fillFromSelection('project_code')">原文</el-button></template>
                  </el-input>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="采购人">
                  <el-input v-model="form.tenderee">
                    <template #append><el-button @click="fillFromSelection('tenderee')">原文</el-button></template>
                  </el-input>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="代理机构">
                  <el-input v-model="form.agency">
                    <template #append><el-button @click="fillFromSelection('agency')">原文</el-button></template>
                  </el-input>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="公告类型">
                  <el-select v-model="form.notice_type_id" placeholder="请选择" style="width: 100%">
                    <el-option v-for="t in noticeTypes" :key="t.id" :label="t.name" :value="t.id" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="地区代码">
                  <el-input v-model="form.region_code">
                    <template #append><el-button @click="fillFromSelection('region_code')">原文</el-button></template>
                  </el-input>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="预算">
                  <el-input v-model="form.budget" placeholder="如 100 万元">
                    <template #append><el-button @click="fillFromSelection('budget')">原文</el-button></template>
                  </el-input>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="12">
              <el-col :span="12"><el-form-item label="公告发布时间">
                <el-date-picker v-model="form.publish_time" type="datetime" placeholder="选择时间" style="width: 100%" />
              </el-form-item></el-col>
              <el-col :span="12"><el-form-item label="投标截止时间">
                <el-date-picker v-model="form.deadline" type="datetime" placeholder="选择时间" style="width: 100%" />
              </el-form-item></el-col>
            </el-row>

            <el-divider content-position="left">中标信息</el-divider>
            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="中标单位">
                  <el-input v-model="form.winner_unit">
                    <template #append><el-button @click="fillFromSelection('winner_unit')">原文</el-button></template>
                  </el-input>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="中标金额(元)">
                  <el-input v-model="form.win_amount" placeholder="如 500000.00">
                    <template #append><el-button @click="fillFromSelection('win_amount')">原文</el-button></template>
                  </el-input>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="12">
              <el-col :span="8"><el-form-item label="招采类型">
                <el-input v-model="form.procure_type" placeholder="如 公开招标" />
              </el-form-item></el-col>
              <el-col :span="8"><el-form-item label="客群">
                <el-input v-model="form.customer_group" placeholder="如 政务/国企" />
              </el-form-item></el-col>
              <el-col :span="8"><el-form-item label="中标时间">
                <el-date-picker v-model="form.winner_publish_time" type="datetime" placeholder="选择时间" style="width: 100%" />
              </el-form-item></el-col>
            </el-row>
            <el-form-item label="公告正文">
              <el-input v-model="form.content" type="textarea" :rows="6" placeholder="支持粘贴 HTML 或纯文本" />
            </el-form-item>
            <el-form-item label="原文链接"><el-input v-model="form.source_url" /></el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="saving" @click="onSubmit">保存</el-button>
              <el-button v-if="isEdit" type="warning" plain :loading="extracting" @click="onReextract">
                重新提取
              </el-button>
              <el-button @click="router.back()">取消</el-button>
            </el-form-item>
          </el-form>
        </el-col>

        <el-col :span="9">
          <div class="origin-card">
            <div class="origin-head">
              <span>原文</span>
              <span class="origin-tip">
                选中文字后点字段右侧「原文」即可填入
                <template v-if="selectionText"> · 已选 {{ selectionText.length }} 字</template>
              </span>
            </div>
            <div class="origin-body" @mouseup="onTextMouseUp">
              <template v-if="plainText">
                <p v-for="(line, i) in plainLines" :key="i" class="origin-line">{{ line }}</p>
              </template>
              <el-empty v-else description="暂无正文" :image-size="60" />
            </div>
            <div v-if="highlight" class="origin-selected">
              <span class="sel-label">当前选中：</span>{{ highlight }}
            </div>
          </div>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import {
  fetchBidDetail, createBid, updateBid, fetchNoticeTypes,
  fetchBidSuggestions, reextractBid,
} from '@/api'
import dayjs from 'dayjs'

const route = useRoute()
const router = useRouter()
const formRef = ref<FormInstance>()
const saving = ref(false)
const extracting = ref(false)
const noticeTypes = ref<any[]>([])
const suggestions = ref<Record<string, any>>({})
const selectionText = ref('')

const isEdit = computed(() => !!route.params.id)
const form = reactive<any>({
  title: '', project_code: '', tenderee: '', agency: '', notice_type_id: null,
  region_code: '', publish_time: null, deadline: null, budget: '',
  winner_unit: '', win_amount: '', procure_type: '', customer_group: '',
  winner_publish_time: null, content: '', source_url: '',
})

const rules: FormRules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
}

const FIELD_LABELS: Record<string, string> = {
  tenderee: '采购人', agency: '代理机构', budget: '预算', project_code: '项目编号',
  region_code: '地区', deadline: '截止时间', winner_unit: '中标单位', win_amount: '中标金额',
}

const plainText = computed(() => {
  let s = String(form.content || '')
  if (!s) return ''
  s = s.replace(/<br\s*\/?>/gi, '\n').replace(/<\/(p|div|tr|li|h\d)>/gi, '\n')
  s = s.replace(/<[^>]+>/g, '')
  s = s.replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
  return s.replace(/\n{3,}/g, '\n\n').trim()
})
const plainLines = computed(() => plainText.value.split('\n').filter((l) => l.trim()))

const highlight = computed(() => selectionText.value.slice(0, 80))

const suggestionChips = computed(() =>
  Object.entries(suggestions.value)
    .filter(([f, v]) => v !== null && v !== undefined && v !== '' && FIELD_LABELS[f])
    .map(([field, value]) => ({
      field,
      value,
      label: FIELD_LABELS[field],
      display: field === 'win_amount' ? `${Number(value).toLocaleString()} 元` : String(value).slice(0, 26),
    })),
)

function onTextMouseUp() {
  const sel = window.getSelection()
  const t = (sel?.toString() || '').trim()
  if (t) selectionText.value = t.slice(0, 300)
}

function applyValue(field: string, raw: any) {
  if (raw === null || raw === undefined || raw === '') return
  if (field === 'win_amount') {
    const num = String(raw).replace(/[^\d.]/g, '')
    form.win_amount = num || String(raw)
    return
  }
  if (['publish_time', 'deadline', 'winner_publish_time'].includes(field)) {
    const d = dayjs(String(raw))
    if (d.isValid()) form[field] = d.toDate()
    return
  }
  form[field] = typeof raw === 'string' ? raw.trim() : raw
}

function fillFromSelection(field: string) {
  if (!selectionText.value) {
    ElMessage.warning('请先在右侧原文中选中要填入的文字')
    return
  }
  applyValue(field, selectionText.value)
  ElMessage.success('已填入')
}

async function loadSuggestions() {
  if (!isEdit.value) return
  try {
    const d = await fetchBidSuggestions(Number(route.params.id))
    suggestions.value = d.fields || {}
  } catch {
    suggestions.value = {}
  }
}

async function onReextract() {
  extracting.value = true
  try {
    const d = await reextractBid(Number(route.params.id))
    const n = Object.keys(d.updated || {}).length
    ElMessage.success(n ? `已补全 ${n} 个字段` : '没有可补全的字段')
    const detail = await fetchBidDetail(Number(route.params.id))
    Object.assign(form, detail)
    await loadSuggestions()
  } finally {
    extracting.value = false
  }
}

async function onSubmit() {
  await formRef.value?.validate()
  saving.value = true
  try {
    const payload = { ...form }
    ;['publish_time', 'deadline', 'winner_publish_time'].forEach((k) => {
      if (payload[k] && typeof payload[k] !== 'string') {
        payload[k] = dayjs(payload[k]).toISOString()
      }
    })
    if (isEdit.value) {
      payload.id = Number(route.params.id)
      await updateBid(payload)
      ElMessage.success('更新成功')
    } else {
      await createBid(payload)
      ElMessage.success('创建成功')
    }
    router.replace('/bid/list')
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  noticeTypes.value = await fetchNoticeTypes()
  if (isEdit.value) {
    const detail = await fetchBidDetail(Number(route.params.id))
    Object.assign(form, detail)
    // 日期字符串 → Date，保证日期控件正常显示
    ;['publish_time', 'deadline', 'winner_publish_time'].forEach((k) => {
      if (form[k] && typeof form[k] === 'string') {
        const d = dayjs(form[k])
        form[k] = d.isValid() ? d.toDate() : null
      }
    })
    await loadSuggestions()
  }
})
</script>

<style scoped>
.suggest-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 14px; }
.suggest-title { font-size: 12px; color: #909399; }
.suggest-chip { cursor: pointer; }
.origin-card { border: 1px solid #ebeef5; border-radius: 6px; background: #fafafa; position: sticky; top: 80px; }
.origin-head { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; border-bottom: 1px solid #ebeef5; font-size: 13px; font-weight: 600; }
.origin-tip { font-size: 11px; font-weight: 400; color: #909399; }
.origin-body { max-height: 560px; overflow-y: auto; padding: 10px 12px; font-size: 12px; line-height: 1.7; color: #606266; user-select: text; }
.origin-line { margin: 0 0 4px; word-break: break-all; }
.origin-selected { border-top: 1px dashed #dcdfe6; padding: 8px 12px; font-size: 12px; color: #e6a23c; background: #fdf6ec; }
.sel-label { color: #909399; }
</style>
