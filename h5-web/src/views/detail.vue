<template>
  <div class="bid-detail">
    <van-nav-bar :title="detail?.title?.slice(0, 15) || '标讯详情'" left-arrow @click-left="$router.back()" fixed placeholder />
    <div v-if="detail">
      <div class="card">
        <h2>{{ detail.title }}</h2>
        <div class="meta">
          <span>{{ detail.notice_type }}</span>
          <span>{{ detail.publish_time }}</span>
          <span>{{ detail.region_name }}</span>
        </div>
        <div class="info-row" v-if="detail.project_code"><label>项目编号</label><span>{{ detail.project_code }}</span></div>
        <div class="info-row" v-if="detail.tenderee"><label>招标人</label><span>{{ detail.tenderee }}</span></div>
        <div class="info-row" v-if="detail.deadline"><label>截止时间</label><span>{{ detail.deadline }}</span></div>
        <div class="info-row" v-if="detail.budget"><label>预算金额</label><span class="price">{{ detail.budget }}</span></div>
      </div>

      <div class="card content" v-html="detail.content || '<p>正文暂未提供</p>'"></div>
    </div>
    <van-empty v-else description="加载中..." />

    <div class="bottom-bar">
      <van-button block type="primary" icon="share-o">分享标讯</van-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const detail = ref<any>(null)

onMounted(async () => {
  const id = route.params.id
  // TODO: const data = await request.get(`/api/v1/bids/${id}`); detail.value = data
  detail.value = {
    id,
    title: '某智慧城市综合信息管理平台建设项目招标公告',
    notice_type: '招标公告',
    publish_time: '2026-11-20 10:00',
    region_name: '北京市',
    project_code: 'ZC-2026-00128',
    tenderee: '北京市信息中心',
    deadline: '2026-12-10 17:00',
    budget: '480.00 万元',
    content: '<p>本项目招标范围包括 ...（HTML 正文）</p>',
  }
})
</script>

<style scoped>
.card {
  background: #fff;
  margin: 12px;
  border-radius: 8px;
  padding: 16px;
  h2 { margin: 0 0 12px; font-size: 18px; color: #303133; }
  .meta { display: flex; gap: 12px; color: #909399; font-size: 12px; margin-bottom: 12px; }
  .info-row {
    display: flex; padding: 6px 0; border-top: 1px solid #f0f0f0;
    label { width: 80px; color: #909399; }
    .price { color: #f56c6c; font-weight: 600; }
  }
  &.content { line-height: 1.8; color: #303133; font-size: 15px; }
}
.bottom-bar {
  position: fixed; left: 0; right: 0; bottom: 0; padding: 12px; background: #fff; box-shadow: 0 -2px 8px rgba(0,0,0,0.05);
}
</style>
