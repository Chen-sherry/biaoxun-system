<template>
  <div class="member-page">
    <h1>👤 会员中心</h1>
    <el-alert type="info" :closable="false" title="会员套餐 / 订阅管理 / 收藏标讯 —— 后续完善。当前可登录使用 AI 智能匹配高级功能。" />
    <div class="placeholder-card">
      <el-empty description="更多会员功能正在开发中" />
      <el-button type="primary" @click="$router.push('/ai-match')">体验 AI 智能匹配 →</el-button>
    </div>
  </div>
</template>

<style scoped>
.member-page { max-width: 900px; margin: 32px auto; padding: 0 24px; }
.member-page h1 { font-size: 24px; margin-bottom: 16px; }
.placeholder-card { background: #fff; border-radius: 12px; padding: 40px; margin-top: 20px; text-align: center; }
</style>
