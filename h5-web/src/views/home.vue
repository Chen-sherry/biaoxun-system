<template>
  <div class="home">
    <van-nav-bar title="标讯系统" fixed placeholder />
    <van-search v-model="keyword" placeholder="搜索标讯、项目编号..." @search="onSearch" />

    <van-cell-group inset title="热门分类">
      <van-grid :column-num="4" :border="false">
        <van-grid-item icon="search" text="招标公告" @click="$router.push('/list?type=招标公告')" />
        <van-grid-item icon="gold-coin-o" text="中标公告" @click="$router.push('/list?type=中标公告')" />
        <van-grid-item icon="edit" text="更正公告" @click="$router.push('/list?type=更正公告')" />
        <van-grid-item icon="warning-o" text="流标公告" @click="$router.push('/list?type=流标公告')" />
      </van-grid>
    </van-cell-group>

    <van-cell-group inset title="最新发布">
      <van-cell
        v-for="bid in list"
        :key="bid.id"
        :title="bid.title"
        :label="`${bid.publish_time} · ${bid.region_name || '全国'}`"
        is-link
        @click="$router.push(`/detail/${bid.id}`)"
      />
      <van-empty v-if="!list.length" description="暂无数据" />
    </van-cell-group>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import request from '@/utils/request'

const keyword = ref('')
const list = ref<any[]>([])

// TODO: 调用 /api/v1/bids?page=1&page_size=20&status=1
list.value = [
  { id: 1, title: '某智慧城市建设项目招标公告', publish_time: '2026-11-20', region_name: '北京' },
  { id: 2, title: 'XX 单位办公设备采购询价', publish_time: '2026-11-20', region_name: '上海' },
  { id: 3, title: '公路工程施工总承包中标结果', publish_time: '2026-11-19', region_name: '广东' },
]

function onSearch(k: string) {
  if (!k.trim()) return
  location.hash = `#/list?keyword=${encodeURIComponent(k.trim())}`
}
</script>
