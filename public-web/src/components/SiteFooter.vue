<template>
  <footer class="site-footer">
    <div class="footer-inner">
      <div class="footer-section">
        <div class="brand">📢 标讯速递</div>
        <p>聚合全国公共资源交易平台、政府采购网、招投标公告的一站式智能门户。</p>
      </div>
      <div class="footer-section">
        <h4>快捷入口</h4>
        <router-link to="/">首页</router-link>
        <router-link to="/search">传统搜索</router-link>
        <router-link to="/ai-match">AI 智能匹配</router-link>
      </div>
      <div class="footer-section">
        <h4>帮助</h4>
        <router-link to="/login">会员登录</router-link>
        <router-link to="/member">会员套餐</router-link>
      </div>
      <div class="footer-section">
        <h4>系统</h4>
        <a :href="adminLink" target="_blank">管理后台</a>
      </div>
    </div>
    <div class="copyright">© 2024 标讯速递 All Rights Reserved</div>
  </footer>
</template>

<script setup lang="ts">
// 管理后台入口：本地开发指向 5173，服务器构建用 VITE_ADMIN_BASE=/biaoxun-admin/
const adminLink = import.meta.env.VITE_ADMIN_BASE || 'http://127.0.0.1:5173/admin/'
</script>

<style scoped>
.site-footer { background: #1f2d3d; color: #98a6ad; padding: 40px 24px 20px; margin-top: 48px; }
.footer-inner { max-width: 1200px; margin: 0 auto; display: grid; grid-template-columns: 2fr 1fr 1fr 1fr; gap: 32px; }
.footer-section h4 { color: #fff; font-size: 14px; margin: 0 0 12px; }
.footer-section a, .footer-section p { display: block; color: #98a6ad; font-size: 13px; line-height: 2; }
.footer-section .brand { font-size: 20px; font-weight: 700; color: #fff; margin-bottom: 8px; }
.copyright { max-width: 1200px; margin: 24px auto 0; padding-top: 16px; border-top: 1px solid #3a4a5c; text-align: center; font-size: 12px; }

/* ===== 移动端 ===== */
@media (max-width: 768px) {
  .site-footer { padding: 28px 16px 16px; margin-top: 32px; }
  .footer-inner { grid-template-columns: 1fr 1fr; gap: 20px; }
}
@media (max-width: 480px) {
  .footer-inner { grid-template-columns: 1fr; }
}
</style>
