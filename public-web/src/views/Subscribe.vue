<template>
  <div class="sub-page">
    <div class="sub-head">
      <span class="section-kicker">MY SUBSCRIPTION</span>
      <h1><el-icon><Bell /></el-icon> 我的订阅</h1>
      <p>按关键词订阅标讯，命中后自动推送到邮箱</p>
    </div>

    <!-- 未登录 -->
    <div v-if="!isLoggedIn" class="tech-card login-hint">
      <el-icon :size="24" color="var(--ink-400)"><Lock /></el-icon>
      <p>登录后管理您的订阅（会员专属）</p>
      <el-button type="primary" plain @click="$router.push('/login?redirect=/subscribe')">立即登录</el-button>
    </div>

    <!-- 会员校验中 -->
    <div v-else-if="!memberChecked" class="tech-card" style="padding: 40px; text-align: center;">
      <el-icon class="is-loading" :size="22" color="var(--accent)"><Loading /></el-icon>
      <p style="color: var(--ink-400); margin-top: 10px;">正在校验会员状态…</p>
    </div>

    <!-- 非会员：禁止使用 -->
    <div v-else-if="!isMember" class="tech-card member-gate">
      <el-icon :size="30" color="var(--accent-strong)"><Medal /></el-icon>
      <h3>订阅推送为会员专属功能</h3>
      <p>开通会员后即可创建专属订阅，命中标讯自动推送到邮箱</p>
      <el-button type="primary" @click="$router.push('/member')">查看会员套餐</el-button>
    </div>

    <template v-else>
      <!-- 概览条 -->
      <div class="tech-card overview">
        <div class="ov-item">
          <span class="ov-label">已用订阅</span>
          <span class="ov-value">{{ subscribes.length }}<em>/ {{ maxSubscribe }}</em></span>
        </div>
        <div class="ov-item">
          <span class="ov-label">当前套餐</span>
          <span class="ov-value small">{{ memberStatus.package_name || '免费版' }}</span>
        </div>
        <div class="ov-item">
          <span class="ov-label">接收邮箱</span>
          <span class="ov-value small">{{ userEmail || '未绑定' }}</span>
        </div>
        <el-button type="primary" :disabled="subscribes.length >= maxSubscribe" @click="openDialog()">
          新建订阅
        </el-button>
      </div>

      <el-alert
        v-if="!userEmail"
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 14px"
        title="账号未绑定邮箱，推送将无法送达，请先在个人中心补充邮箱"
      />
      <el-alert
        v-if="subscribes.length >= maxSubscribe"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 14px"
        :title="`已达当前套餐订阅上限（${maxSubscribe} 个），升级会员可创建更多订阅`"
      />

      <el-tabs v-model="activeTab" class="tech-card sub-tabs">
        <!-- 订阅列表 -->
        <el-tab-pane label="我的订阅" name="list">
          <el-table :data="subscribes" v-loading="loading" stripe>
            <el-table-column prop="keyword" label="关键词" min-width="160" show-overflow-tooltip />
            <el-table-column label="地区" width="110">
              <template #default="{ row }">{{ regionName(row.region_code) }}</template>
            </el-table-column>
            <el-table-column label="公告类型" width="120">
              <template #default="{ row }">{{ noticeTypeName(row.notice_type_id) }}</template>
            </el-table-column>
            <el-table-column label="推送" width="90">
              <template #default="{ row }">
                <el-tag :type="row.push_email ? 'success' : 'info'" size="small">
                  {{ row.push_email ? '邮件' : '关闭' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="频率" width="90">
              <template #default="{ row }">{{ freqText(row.frequency) }}</template>
            </el-table-column>
            <el-table-column label="最后推送" width="160">
              <template #default="{ row }">{{ formatTime(row.last_push_at) || '—' }}</template>
            </el-table-column>
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.status ? 'success' : 'info'" size="small">{{ row.status ? '启用' : '停用' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="220" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" :loading="pushingId === row.id" @click="pushNow(row)">立即推送</el-button>
                <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
                <el-popconfirm title="确定删除该订阅？" @confirm="remove(row)">
                  <template #reference>
                    <el-button link type="danger">删除</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="subscribes.length === 0 && !loading" description="还没有订阅，点击右上角新建" :image-size="100" />
        </el-tab-pane>

        <!-- 推送记录 -->
        <el-tab-pane label="推送记录" name="records">
          <el-table :data="records" v-loading="recordsLoading" stripe>
            <el-table-column prop="push_time" label="推送时间" width="170">
              <template #default="{ row }">{{ formatTime(row.push_time) }}</template>
            </el-table-column>
            <el-table-column prop="subject" label="主题" min-width="180" show-overflow-tooltip />
            <el-table-column label="命中标讯" min-width="240">
              <template #default="{ row }">
                <div v-if="row.bids && row.bids.length">
                  <a v-for="b in row.bids.slice(0, 2)" :key="b.id" :href="detailUrl(b.id)" target="_blank" class="bid-link">
                    {{ b.title }}
                  </a>
                  <span v-if="row.bids.length > 2" class="more">等 {{ row.bids.length }} 条</span>
                </div>
                <span v-else class="more">—</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.status === 0 ? 'success' : 'danger'" size="small">
                  {{ row.status === 0 ? '已送达' : '失败' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="records.length === 0 && !recordsLoading" description="暂无推送记录" :image-size="100" />
          <el-pagination
            v-if="recordsTotal > recordsPageSize"
            style="margin-top: 12px; justify-content: flex-end"
            background
            layout="total, prev, pager, next"
            :total="recordsTotal"
            :page-size="recordsPageSize"
            v-model:current-page="recordsPage"
            @current-change="loadRecords"
          />
        </el-tab-pane>
      </el-tabs>
    </template>

    <!-- 新建/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="editing ? '编辑订阅' : '新建订阅'" width="520px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="关键词" prop="keyword">
          <el-input v-model="form.keyword" placeholder="多个关键词用空格分隔" />
        </el-form-item>
        <el-form-item label="地区">
          <el-select v-model="form.region_code" clearable placeholder="不限" style="width: 100%">
            <el-option v-for="r in regions" :key="r.code" :label="r.name" :value="r.code" />
          </el-select>
        </el-form-item>
        <el-form-item label="公告类型">
          <el-select v-model="form.notice_type_id" clearable placeholder="不限" style="width: 100%">
            <el-option v-for="t in noticeTypes" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="推送方式">
          <el-switch v-model="form.push_email" active-text="邮件" />
        </el-form-item>
        <el-form-item label="推送频率">
          <el-select v-model="form.frequency" style="width: 100%">
            <el-option label="每天" value="daily" />
            <el-option label="每小时" value="hourly" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="editing" label="状态">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" active-text="启用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Bell, Lock, Loading, Medal } from '@element-plus/icons-vue'
import {
  fetchMySubscribes, createSubscribe, updateSubscribe, deleteSubscribe, pushSubscribeNow,
  fetchMyPushRecords, fetchMyMemberStatus, fetchMe, fetchPublicRegions, fetchPublicNoticeTypes,
} from '@/api'

const isLoggedIn = computed(() => !!localStorage.getItem('token'))
const loading = ref(false)
const saving = ref(false)
const pushingId = ref<number | null>(null)
const subscribes = ref<any[]>([])
const memberStatus = ref<any>({ max_subscribe: 3 })
const isMember = ref(false)
const memberChecked = ref(false)
const userEmail = ref('')
const regions = ref<any[]>([])
const noticeTypes = ref<any[]>([])
const activeTab = ref('list')

const records = ref<any[]>([])
const recordsLoading = ref(false)
const recordsTotal = ref(0)
const recordsPage = ref(1)
const recordsPageSize = 20

const maxSubscribe = computed(() => memberStatus.value?.max_subscribe ?? 3)

const dialogVisible = ref(false)
const editing = ref<any>(null)
const formRef = ref<FormInstance>()
const form = reactive<any>({ keyword: '', region_code: '', notice_type_id: undefined, push_email: true, frequency: 'daily', status: 1 })
const rules: FormRules = {
  keyword: [{ required: true, message: '请输入关键词', trigger: 'blur' }],
}

function formatTime(t: any) {
  if (!t) return ''
  return String(t).replace('T', ' ').slice(0, 16)
}
function freqText(f: string) {
  return { daily: '每天', hourly: '每小时', realtime: '实时' }[f] || f
}
function regionName(code: string) {
  if (!code) return '不限'
  return regions.value.find((r) => r.code === code)?.name || code
}
function noticeTypeName(id: number) {
  if (!id) return '不限'
  return noticeTypes.value.find((t) => t.id === id)?.name || id
}
function detailUrl(id: number) {
  return `${import.meta.env.BASE_URL}bid/${id}`
}

async function loadDicts() {
  try { regions.value = await fetchPublicRegions(0) } catch {}
  try { noticeTypes.value = await fetchPublicNoticeTypes() } catch {}
}
async function loadSubscribes() {
  loading.value = true
  try { subscribes.value = (await fetchMySubscribes()) || [] } catch {} finally { loading.value = false }
}
async function loadMember() {
  try {
    const me = await fetchMe()
    userEmail.value = me?.email || ''
  } catch {}
  try {
    memberStatus.value = await fetchMyMemberStatus()
    isMember.value = !!memberStatus.value?.is_member
  } catch {
    isMember.value = false
  } finally {
    memberChecked.value = true
  }
}
async function loadRecords() {
  recordsLoading.value = true
  try {
    const res = await fetchMyPushRecords({ page: recordsPage.value, page_size: recordsPageSize })
    records.value = res.items || []
    recordsTotal.value = res.total || 0
  } catch {} finally { recordsLoading.value = false }
}

function openDialog(row?: any) {
  editing.value = row || null
  Object.assign(form, row
    ? { keyword: row.keyword, region_code: row.region_code || '', notice_type_id: row.notice_type_id || undefined, push_email: row.push_email, frequency: row.frequency || 'daily', status: row.status }
    : { keyword: '', region_code: '', notice_type_id: undefined, push_email: true, frequency: 'daily', status: 1 })
  dialogVisible.value = true
}

async function save() {
  await formRef.value?.validate()
  saving.value = true
  try {
    const payload = {
      keyword: form.keyword,
      region_code: form.region_code || null,
      notice_type_id: form.notice_type_id ?? null,
      push_email: form.push_email,
      frequency: form.frequency,
      status: form.status,
    }
    if (editing.value) {
      await updateSubscribe(editing.value.id, payload)
    } else {
      await createSubscribe(payload)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    loadSubscribes()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '保存失败')
  } finally { saving.value = false }
}

async function pushNow(row: any) {
  pushingId.value = row.id
  try {
    await pushSubscribeNow(row.id)
    ElMessage.success('已触发推送')
    loadSubscribes()
    loadRecords()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '推送失败')
  } finally { pushingId.value = null }
}

async function remove(row: any) {
  try {
    await deleteSubscribe(row.id)
    ElMessage.success('已删除')
    loadSubscribes()
  } catch { ElMessage.error('删除失败') }
}

onMounted(async () => {
  if (!isLoggedIn.value) return
  await loadMember()
  if (!isMember.value) return   // 非会员不加载订阅数据
  loadDicts()
  loadSubscribes()
  loadRecords()
})
</script>

<style scoped>
.sub-page { max-width: 1000px; margin: 28px auto; padding: 0 24px 30px; }
.sub-head { margin-bottom: 20px; }
.sub-head h1 { font-size: 27px; font-weight: 800; color: var(--ink-900); margin: 8px 0 6px; display: flex; align-items: center; gap: 10px; }
.sub-head h1 :deep(.el-icon) { color: var(--accent-strong); }
.sub-head p { color: var(--ink-500); font-size: 14px; }
.login-hint { padding: 30px; text-align: center; }
.login-hint p { color: var(--ink-500); margin: 10px 0 16px; }
.member-gate { padding: 40px 30px; text-align: center; }
.member-gate h3 { margin: 12px 0 8px; font-size: 18px; color: var(--ink-900); }
.member-gate p { color: var(--ink-500); margin: 0 0 18px; font-size: 14px; }
.overview { display: flex; align-items: center; gap: 28px; padding: 16px 20px; margin-bottom: 16px; flex-wrap: wrap; }
.ov-item { display: flex; flex-direction: column; gap: 4px; }
.ov-label { font-size: 12px; color: var(--ink-400); }
.ov-value { font-size: 22px; font-weight: 800; color: var(--accent-strong); }
.ov-value em { font-size: 13px; font-style: normal; color: var(--ink-400); font-weight: 500; }
.ov-value.small { font-size: 15px; font-weight: 600; color: var(--ink-800); }
.overview > .el-button { margin-left: auto; }
.sub-tabs { padding: 6px 16px 16px; }
.bid-link { display: block; font-size: 13px; color: var(--accent-strong); text-decoration: none; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bid-link:hover { text-decoration: underline; }
.more { font-size: 12px; color: var(--ink-400); }
@media (max-width: 768px) {
  .sub-page { margin: 16px auto; padding: 0 12px; }
  .sub-head h1 { font-size: 21px; }
  .overview { gap: 16px; }
  .overview > .el-button { margin-left: 0; width: 100%; }
}
</style>
