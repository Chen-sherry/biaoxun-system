<template>
  <router-view v-slot="{ Component }">
    <keep-alive>
      <component :is="Component" />
    </keep-alive>
  </router-view>

  <van-tabbar v-if="showTabbar" v-model="active" route>
    <van-tabbar-item to="/home" icon="home-o">首页</van-tabbar-item>
    <van-tabbar-item to="/list" icon="search">标讯</van-tabbar-item>
    <van-tabbar-item to="/subscribe" icon="notification-o">订阅</van-tabbar-item>
    <van-tabbar-item to="/mine" icon="user-o">我的</van-tabbar-item>
  </van-tabbar>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const active = ref(0)
const showTabbar = computed(() => !route.meta?.hideTabbar)
</script>
