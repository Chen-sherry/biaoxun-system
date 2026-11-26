<script setup lang="ts">
import { RouterView } from 'vue-router'
import SiteHeader from '@/components/SiteHeader.vue'
import SiteFooter from '@/components/SiteFooter.vue'
import AIBall from '@/components/AIBall.vue'
</script>

<template>
  <div class="portal-layout">
    <SiteHeader />
    <main class="portal-main">
      <RouterView />
    </main>
    <SiteFooter />
    <AIBall />
  </div>
</template>

<style scoped>
.portal-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background:
    radial-gradient(1100px 520px at 50% -180px, rgba(14, 165, 233, 0.10), transparent 70%),
    var(--surface-soft);
}
.portal-main { flex: 1 0 auto; }
</style>
