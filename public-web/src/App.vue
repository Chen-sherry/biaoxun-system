<script setup lang="ts">
import { RouterView } from 'vue-router'
import SiteHeader from '@/components/SiteHeader.vue'
import SiteFooter from '@/components/SiteFooter.vue'
</script>

<template>
  <div class="portal-layout">
    <SiteHeader />
    <main class="portal-main">
      <RouterView />
    </main>
    <SiteFooter />
  </div>
</template>

<style>
html, body, #app { height: 100%; margin: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", Roboto, sans-serif; background: #f5f7fa; color: #303133; }
a { text-decoration: none; color: inherit; }
</style>
