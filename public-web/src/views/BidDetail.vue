<template>
  <div v-loading="loading" class="detail-page" v-if="detail">
    <div class="page-head">
      <el-page-header @back="$router.back()" :content="detail.title">
        <template #content>
          <h1 class="title"><span v-if="detail.ai_processed" class="ai-pill">AI</span>{{ detail.title }}</h1>
          <div class="meta">
            <el-tag v-if="detail.notice_type" size="small" type="primary" effect="dark">{{ detail.notice_type }}</el-tag>
            <span><el-icon><Calendar /></el-icon> 发布：{{ formatTime(detail.publish_time) }}</span>
            <span v-if="detail.region_name"><el-icon><Location /></el-icon> {{ detail.region_name }}</span>
            <span><el-icon><View /></el-icon> {{ detail.view_count }}</span>
          </div>
        </template>
      </el-page-header>
    </div>

    <div class="detail-card tech-card">
      <div class="card-heading"><el-icon><Document /></el-icon><h3>标讯信息</h3></div>
      <el-descriptions :column="descColumn" border size="small">
        <el-descriptions-item label="项目编号">{{ detail.project_code || '—' }}</el-descriptions-item>
        <el-descriptions-item label="采购人">{{ detail.tenderee || '—' }}</el-descriptions-item>
        <el-descriptions-item label="地区">{{ detail.region_name || '—' }}</el-descriptions-item>
        <!-- 招标类模板：投标截止 / 预算，不显示中标字段 -->
        <template v-if="!isResultType">
          <el-descriptions-item label="投标截止">{{ formatTime(detail.deadline) || '—' }}</el-descriptions-item>
          <el-descriptions-item label="预算">{{ detail.budget && Number(detail.budget) > 0 ? detail.budget : '—' }}</el-descriptions-item>
        </template>
        <!-- 中标/成交类模板：中标单位 / 中标金额 / 中标时间，不显示投标截止 -->
        <template v-else>
          <el-descriptions-item label="中标单位">{{ detail.winner_unit || '—' }}</el-descriptions-item>
          <el-descriptions-item label="中标金额">{{ detail.win_amount ? '¥' + detail.win_amount.toLocaleString() : '—' }}</el-descriptions-item>
          <el-descriptions-item label="中标时间">{{ formatTime(detail.winner_publish_time) || '—' }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.budget && Number(detail.budget) > 0" label="预算">{{ detail.budget }}</el-descriptions-item>
        </template>
        <el-descriptions-item label="客群">{{ detail.customer_group || '—' }}</el-descriptions-item>
        <el-descriptions-item label="行业">{{ detail.industry_name || '—' }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <div class="detail-card tech-card" v-if="detail.content">
      <div class="card-heading"><el-icon><Files /></el-icon><h3>公告正文</h3></div>
      <div class="content-body" v-html="detail.content"></div>
    </div>

    <div class="detail-card tech-card source-card" v-if="detail.source_url">
      <el-link :href="detail.source_url" target="_blank" type="primary">
        查看原文 <el-icon><TopRight /></el-icon>
      </el-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Calendar, Location, View, Document, Files, TopRight } from '@element-plus/icons-vue'
import { fetchPublicBidDetail } from '@/api'

const route = useRoute()
const loading = ref(false)
const detail = ref<any>(null)

// 详情字段表：手机单列、桌面双列
const descColumn = ref(window.innerWidth < 768 ? 1 : 2)
function onResize() { descColumn.value = window.innerWidth < 768 ? 1 : 2 }

function formatTime(t: any) { return t ? String(t).replace('T',' ').slice(0,19) : '' }

// 结果类公告（中标/成交/合同）→ 中标模板；其余 → 招标模板
const RESULT_TYPES = ['中标公告', '成交公告', '合同公告']
const isResultType = computed(() => RESULT_TYPES.includes(detail.value?.notice_type || ''))

onMounted(async () => {
  window.addEventListener('resize', onResize)
  loading.value = true
  try { detail.value = await fetchPublicBidDetail(Number(route.params.id)) } catch {}
  finally { loading.value = false }
})
onUnmounted(() => window.removeEventListener('resize', onResize))
</script>

<style scoped>
.detail-page { max-width: 1000px; margin: 26px auto; padding: 0 24px 20px; }
.page-head { margin-bottom: 8px; }
.title { font-size: 23px; font-weight: 700; color: var(--ink-900); margin: 0 0 10px; line-height: 1.5; }
.meta { display: flex; gap: 14px; align-items: center; flex-wrap: wrap; color: var(--ink-500); font-size: 13px; margin-top: 10px; }
.meta span { display: inline-flex; align-items: center; gap: 4px; }
.detail-card { margin-top: 16px; padding: 24px; }
.card-heading { display: flex; align-items: center; gap: 9px; margin-bottom: 18px; }
.card-heading :deep(.el-icon) { color: var(--accent-strong); font-size: 18px; }
.card-heading h3 { margin: 0; font-size: 16px; font-weight: 700; color: var(--ink-900); }
.card-heading::after { content: ''; flex: 1; height: 1px; background: linear-gradient(90deg, var(--line), transparent); margin-left: 8px; }
.detail-card :deep(.el-descriptions__label) { font-weight: 600; color: var(--ink-700); }
.detail-card :deep(.el-descriptions__content) { color: var(--ink-900); }
.content-body { font-size: 14px; line-height: 1.85; color: var(--ink-800); }
.content-body :deep(img) { max-width: 100%; height: auto; }
.content-body :deep(table) { max-width: 100%; border-collapse: collapse; }
.source-card { text-align: right; padding: 16px 24px; }
.source-card :deep(.el-link) { font-weight: 600; }

/* ===== 移动端（≤768px）===== */
@media (max-width: 768px) {
  .detail-page { margin: 14px auto; padding: 0 12px 16px; }
  .title { font-size: 17px; }
  .meta { gap: 10px; }
  .detail-card { padding: 14px; }
}
</style>
