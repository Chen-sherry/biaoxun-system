<template>
  <div class="subscribe">
    <van-nav-bar title="我的订阅" fixed placeholder />

    <van-button round icon="plus" type="primary" block style="margin: 12px" @click="openAdd = true">
      新建订阅关键词
    </van-button>

    <van-cell-group inset v-if="list.length">
      <van-cell
        v-for="item in list"
        :key="item.id"
        :title="item.keyword"
        :label="`地区: ${item.region_code || '不限'} · 频率: ${item.frequency}`"
        is-link
      />
    </van-cell-group>
    <van-empty v-else description="还没有订阅任何关键词哦" />

    <van-popup v-model:show="openAdd" position="bottom" round>
      <div style="padding: 16px">
        <h3>新建订阅</h3>
        <van-field v-model="form.keyword" label="关键词" placeholder="多个关键词用空格或逗号分隔" />
        <van-field v-model="form.region_code" label="地区代码" placeholder="可选" />
        <van-field v-model="form.frequency" label="推送频率" placeholder="daily / hourly" />
        <van-button type="primary" block style="margin-top: 12px" @click="save">保存</van-button>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { showToast } from 'vant'
import request from '@/utils/request'

const list = ref<any[]>([])
const openAdd = ref(false)
const form = reactive({ keyword: '', region_code: '', frequency: 'daily' })

async function save() {
  if (!form.keyword.trim()) { showToast('请输入关键词'); return }
  // await request.post('/api/v1/subscribes', form)
  showToast('保存成功（占位）')
  openAdd.value = false
}
</script>
