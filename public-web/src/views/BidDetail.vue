<template>
  <div v-loading="loading" class="detail-page" v-if="detail">
    <el-page-header @back="$router.back()" :content="detail.title">
      <template #content>
        <h1 class="title">{{ detail.title }}</h1>
        <div class="meta">
          <el-tag v-if="detail.notice_type" size="small" type="success">{{ detail.notice_type }}</el-tag>
          <span>📅 发布：{{ formatTime(detail.publish_time) }}</span>
          <span v-if="detail.region_name">📍 {{ detail.region_name }}</span>
          <span>👁 {{ detail.view_count }}</span>
        </div>
      </template>
    </el-page-header>

    <div class="detail-card">
      <el-descriptions :column="descColumn" border size="small">
        <el-descriptions-item label="项目编号">{{ detail.project_code || '—' }}</el-descriptions-item>
        <el-descriptions-item label="采购人">{{ detail.tenderee || '—' }}</el-descriptions-item>
        <el-descriptions-item label="地区">{{ detail.region_name || '—' }}</el-descriptions-item>
        <el-descriptions-item label="投标截止">{{ formatTime(detail.deadline) || '—' }}</el-descriptions-item>
        <el-descriptions-item label="预算">{{ detail.budget || '—' }}</el-descriptions-item>
        <el-descriptions-item label="中标单位">{{ winnerText(detail.winner_unit) }}</el-descriptions-item>
        <el-descriptions-item label="中标金额">{{ detail.win_amount ? '¥' + detail.win_amount.toLocaleString() : winnerText(null) }}</el-descriptions-item>
        <el-descriptions-item label="中标时间">{{ formatTime(detail.winner_publish_time) || winnerText(null) }}</el-descriptions-item>
        <el-descriptions-item label="客群">{{ detail.customer_group || '—' }}</el-descriptions-item>
        <el-descriptions-item label="行业">{{ detail.industry_name || '—' }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <div class="detail-card" v-if="detail.content">
      <h3>公告正文</h3>
      <div class="content-body" v-html="detail.content"></div>
    </div>

    <div class="detail-card" v-if="detail.source_url">
      <el-link :href="detail.source_url" target="_blank" type="primary">查看原文 ↗</el-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { fetchPublicBidDetail } from '@/api'

const route = useRoute()
const loading = ref(false)
const detail = ref<any>(null)

// 详情字段表：手机单列、桌面双列
const descColumn = ref(window.innerWidth < 768 ? 1 : 2)
function onResize() { descColumn.value = window.innerWidth < 768 ? 1 : 2 }

function formatTime(t: any) { return t ? String(t).replace('T',' ').slice(0,19) : '' }

// 尚未开标的公告类型：中标信息本来就不存在，显示「未开标」而不是「—」
const PRE_AWARD_TYPES = ['招标公告', '采购公告', '邀请招标', '竞争性磋商公告', '竞争性谈判公告',
  '询价公告', '单一来源公示', '资格预审公告', '采购意向', '更正公告', '答疑澄清']
function winnerText(v: any) {
  if (v) return v
  const nt = detail.value?.notice_type
  return nt && PRE_AWARD_TYPES.includes(nt) ? '未开标' : '—'
}

onMounted(async () => {
  window.addEventListener('resize', onResize)
  loading.value = true
  try { detail.value = await fetchPublicBidDetail(Number(route.params.id)) } catch {}
  finally { loading.value = false }
})
onUnmounted(() => window.removeEventListener('resize', onResize))
</script>

<style scoped>
.detail-page { max-width: 1000px; margin: 24px auto; padding: 0 24px; }
.title { font-size: 22px; margin: 0 0 10px; line-height: 1.5; }
.meta { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; color: #909399; font-size: 13px; margin-top: 8px; }
.detail-card { background: #fff; border-radius: 8px; padding: 24px; margin-top: 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.04); }
.detail-card h3 { margin: 0 0 16px; font-size: 16px; }
.content-body { font-size: 14px; line-height: 1.8; color: #303133; }
.content-body :deep(img) { max-width: 100%; height: auto; }

/* ===== 移动端（≤768px）===== */
@media (max-width: 768px) {
  .detail-page { margin: 12px auto; padding: 0 12px; }
  .title { font-size: 16px; }
  .detail-card { padding: 14px; }
}
</style>
