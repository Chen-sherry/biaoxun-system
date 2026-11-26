<template>
  <div class="nf-page">
    <div class="nf-glow" aria-hidden="true"></div>
    <div class="nf-inner">
      <img :src="emptyArt" alt="" class="nf-art" />
      <div class="nf-code">404</div>
      <h2>页面走丢了</h2>
      <p>请检查地址，或返回首页继续探索</p>
      <el-button type="primary" @click="$router.push('/')"><el-icon><HomeFilled /></el-icon> 返回首页</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import emptyArt from '@/assets/brand/empty-state.svg'
</script>

<style scoped>
.nf-page { position: relative; min-height: 66vh; display: flex; align-items: center; justify-content: center; overflow: hidden; }
.nf-glow {
  position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
  width: 700px; height: 600px; pointer-events: none;
  background-image: url('@/assets/brand/bg-glow.svg'); background-size: cover; opacity: 0.5;
}
.nf-inner { position: relative; z-index: 1; text-align: center; }
.nf-art { width: 240px; max-width: 70vw; animation: float-slow 6s ease-in-out infinite; }
.nf-code {
  font-size: 64px; font-weight: 800; line-height: 1; margin-top: -10px;
  background: linear-gradient(135deg, #0369a1, var(--accent-deep));
  -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
  font-variant-numeric: tabular-nums;
}
.nf-inner h2 { font-size: 22px; color: var(--ink-900); margin: 6px 0 6px; }
.nf-inner p { color: var(--ink-500); font-size: 14px; margin-bottom: 22px; }
</style>
