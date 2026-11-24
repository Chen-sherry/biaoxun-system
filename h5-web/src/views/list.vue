<template>
  <div class="bid-list">
    <van-nav-bar title="标讯列表" left-text="返回" left-arrow @click-left="$router.back()" fixed placeholder />

    <van-tabs v-model:active="tab" sticky>
      <van-tab title="招标公告" />
      <van-tab title="中标公告" />
      <van-tab title="更正公告" />
      <van-tab title="流标公告" />
    </van-tabs>

    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <van-list
        v-model:loading="loading"
        :finished="finished"
        finished-text="没有更多了"
        @load="onLoad"
      >
        <van-cell
          v-for="bid in list"
          :key="bid.id"
          :title="bid.title"
          :label="`${bid.publish_time} · ${bid.region_name || ''} · 预算 ${bid.budget || '-'}`"
          is-link
          @click="$router.push(`/detail/${bid.id}`)"
        >
          <template #icon>
            <van-tag plain type="primary">{{ bid.notice_type || '公告' }}</van-tag>
          </template>
        </van-cell>
      </van-list>
    </van-pull-refresh>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const tab = ref(0)
const list = ref<any[]>([])
const loading = ref(false)
const finished = ref(false)
const refreshing = ref(false)

async function onLoad() {
  // TODO: 调分页接口
  list.value.push(
    { id: list.value.length + 1, title: `样例公告 ${list.value.length + 1}`, notice_type: '招标公告', publish_time: '2026-11-20', region_name: '江苏', budget: '100万' }
  )
  loading.value = false
  if (list.value.length > 10) finished.value = true
}
async function onRefresh() {
  list.value = []
  finished.value = false
  refreshing.value = false
}
</script>
