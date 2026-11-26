<template>
  <div class="member-page">
    <div class="member-glow" aria-hidden="true"></div>
    <div class="member-head">
      <span class="section-kicker">MEMBER CENTER</span>
      <h1><el-icon><User /></el-icon> 会员中心</h1>
      <p>会员套餐 / 订阅管理 / 收藏标讯 —— 更多专属能力持续上线中</p>
    </div>

    <div class="feature-row">
      <div class="feature-card tech-card" v-for="f in features" :key="f.title">
        <span class="feature-icon" :style="{ '--fc': f.color }"><el-icon><component :is="f.icon" /></el-icon></span>
        <h4>{{ f.title }}</h4>
        <p>{{ f.desc }}</p>
      </div>
    </div>

    <el-alert type="info" :closable="false" show-icon title="当前可登录使用智能检索高级功能，会员套餐与订阅管理即将上线。" class="member-alert" />
    <div class="placeholder-card tech-card">
      <el-empty description="更多会员功能正在开发中" :image="emptyArt" :image-size="200" />
      <el-button type="primary" @click="$router.push('/ai-match')"><el-icon><MagicStick /></el-icon> 体验智能检索</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { User, MagicStick, Search, Bell, Star, Connection } from '@element-plus/icons-vue'
import emptyArt from '@/assets/brand/empty-state.svg'

const features = [
  { title: '智能检索', desc: 'AI 语义理解，精准匹配高相关标讯', icon: MagicStick, color: '#38bdf8' },
  { title: '订阅推送', desc: '按条件订阅，最新商机实时送达', icon: Bell, color: '#22d3ee' },
  { title: '收藏管理', desc: '一键收藏关注项目，随时回顾', icon: Star, color: '#818cf8' },
  { title: '高级筛选', desc: '多维度精确筛选，快速定位目标', icon: Search, color: '#10b981' },
]
</script>

<style scoped>
.member-page { position: relative; max-width: 1000px; margin: 28px auto; padding: 0 24px 30px; overflow: hidden; }
.member-glow {
  position: absolute; top: -160px; right: -160px; width: 560px; height: 480px; pointer-events: none;
  background-image: url('@/assets/brand/bg-glow.svg'); background-size: cover; opacity: 0.55;
}
.member-head { position: relative; z-index: 1; margin-bottom: 24px; }
.member-head h1 { font-size: 27px; font-weight: 800; color: var(--ink-900); margin: 8px 0 6px; display: flex; align-items: center; gap: 10px; }
.member-head h1 :deep(.el-icon) { color: var(--accent-strong); }
.member-head p { color: var(--ink-500); font-size: 14px; }
.feature-row { position: relative; z-index: 1; display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 20px; }
.feature-card { padding: 20px 18px; text-align: center; }
.feature-icon {
  width: 48px; height: 48px; margin: 0 auto 12px; border-radius: 13px; display: grid; place-items: center; font-size: 22px;
  color: var(--fc); background: color-mix(in srgb, var(--fc) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--fc) 26%, transparent);
  box-shadow: 0 5px 16px color-mix(in srgb, var(--fc) 18%, transparent);
}
.feature-card h4 { margin: 0 0 6px; font-size: 15px; color: var(--ink-900); }
.feature-card p { margin: 0; font-size: 12px; color: var(--ink-500); line-height: 1.6; }
.member-alert { position: relative; z-index: 1; margin-bottom: 18px; border-radius: var(--r-sm); }
.placeholder-card { position: relative; z-index: 1; padding: 30px; text-align: center; }

@media (max-width: 768px) {
  .member-page { margin: 16px auto; padding: 0 12px; }
  .member-head h1 { font-size: 21px; }
  .feature-row { grid-template-columns: repeat(2, 1fr); }
  .placeholder-card { padding: 20px 14px; }
}
</style>
