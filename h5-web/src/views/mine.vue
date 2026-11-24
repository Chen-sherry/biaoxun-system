<template>
  <div class="mine">
    <van-nav-bar title="我的" fixed placeholder />

    <van-cell-group inset>
      <van-cell v-if="!user" title="点击登录" is-link @click="$router.push('/login')" />
      <van-cell v-else :title="user.nickname || user.username" :value="user.company || ''">
        <template #icon>
          <van-image round width="48" height="48" :src="user.avatar || defaultAvatar" />
        </template>
      </van-cell>
    </van-cell-group>

    <van-cell-group inset style="margin-top: 12px">
      <van-cell title="我的订阅" is-link @click="$router.push('/subscribe')" />
      <van-cell title="我的订单" is-link />
      <van-cell title="会员中心" is-link @click="$router.push('/member')" />
      <van-cell title="浏览记录" is-link />
    </van-cell-group>

    <van-cell-group inset style="margin-top: 12px">
      <van-cell title="用户协议" is-link />
      <van-cell title="隐私政策" is-link />
      <van-cell title="关于我们" is-link />
    </van-cell-group>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
const defaultAvatar = 'https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg'
const user = ref<any>(null) // TODO: 从 store / token 获取
</script>
