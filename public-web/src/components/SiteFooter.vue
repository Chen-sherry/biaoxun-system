<template>
  <footer class="site-footer">
    <div class="footer-grid" aria-hidden="true"></div>
    <div class="footer-glow" aria-hidden="true"></div>
    <div class="footer-inner">
      <div class="footer-section brand-section">
        <BrandLogo :size="40" :text-size="21" light />
        <p>聚合全国公共资源交易平台、政府采购网、招投标公告的一站式智能门户。以数据驱动决策，让每一条商机都被看见。</p>
        <div class="footer-tags">
          <span>AI 语义匹配</span><span>实时聚合</span><span>精准筛选</span>
        </div>
      </div>
      <div class="footer-section">
        <h4>快捷入口</h4>
        <router-link to="/">首页</router-link>
        <router-link to="/search">高级搜索</router-link>
        <router-link to="/ai-match">智能检索</router-link>
      </div>
      <div class="footer-section">
        <h4>帮助</h4>
        <router-link to="/login">会员登录</router-link>
        <router-link to="/member">会员套餐</router-link>
      </div>
      <div class="footer-section">
        <h4>系统</h4>
        <a :href="adminLink" target="_blank">管理后台 <span class="ext">↗</span></a>
      </div>
    </div>
    <div class="copyright">
      <span>© 2026 标讯速递 · 数据赋能招投标</span>
      <span class="copyright-dot"></span>
      <span>All Rights Reserved</span>
    </div>
  </footer>
</template>

<script setup lang="ts">
import BrandLogo from './BrandLogo.vue'
// 管理后台入口：本地开发指向 5173，服务器构建用 VITE_ADMIN_BASE=/biaoxun-admin/
const adminLink = import.meta.env.VITE_ADMIN_BASE || 'http://127.0.0.1:5173/admin/'
</script>

<style scoped>
.site-footer {
  position: relative;
  background: linear-gradient(180deg, var(--brand-900), var(--brand-950));
  color: var(--on-dark-mute);
  padding: 48px 24px 20px;
  margin-top: 56px;
  overflow: hidden;
  border-top: 1px solid rgba(56, 189, 248, 0.14);
}
.footer-grid {
  position: absolute; inset: 0; pointer-events: none; opacity: 0.6;
  background-image: url('@/assets/brand/bg-grid.svg');
  background-size: 48px 48px;
  mask-image: linear-gradient(180deg, #000, transparent 90%);
}
.footer-glow {
  position: absolute; bottom: -160px; left: 8%; width: 460px; height: 260px; pointer-events: none;
  background: radial-gradient(ellipse, rgba(56, 189, 248, 0.16), transparent 70%);
  filter: blur(12px);
}
.footer-inner {
  position: relative; z-index: 1;
  max-width: 1200px; margin: 0 auto;
  display: grid; grid-template-columns: 2.2fr 1fr 1fr 1fr; gap: 40px;
}
.footer-section h4 {
  color: var(--on-dark); font-size: 14px; font-weight: 600; margin: 4px 0 16px;
  display: flex; align-items: center; gap: 8px;
}
.footer-section h4::before {
  content: ''; width: 3px; height: 13px; border-radius: 2px;
  background: var(--accent); box-shadow: 0 0 8px var(--accent-glow);
}
.footer-section a, .footer-section p {
  display: block; color: var(--on-dark-mute); font-size: 13px; line-height: 2.1;
  transition: color 0.25s, transform 0.25s var(--ease);
}
.footer-section a:hover { color: var(--accent); transform: translateX(3px); }
.brand-section p { max-width: 360px; margin: 16px 0 0; }
.footer-tags { display: flex; gap: 8px; margin-top: 18px; flex-wrap: wrap; }
.footer-tags span {
  font-size: 11px; color: var(--accent);
  padding: 4px 10px; border-radius: 999px;
  border: 1px solid rgba(56, 189, 248, 0.28);
  background: rgba(56, 189, 248, 0.08);
}
.ext { font-size: 11px; opacity: 0.7; }
.copyright {
  position: relative; z-index: 1;
  max-width: 1200px; margin: 32px auto 0; padding-top: 18px;
  border-top: 1px solid rgba(148, 197, 232, 0.12);
  display: flex; align-items: center; justify-content: center; gap: 14px;
  font-size: 12px; color: var(--on-dark-mute);
}
.copyright-dot { width: 3px; height: 3px; border-radius: 50%; background: var(--accent); }

/* ===== 移动端 ===== */
@media (max-width: 768px) {
  .site-footer { padding: 32px 16px 18px; margin-top: 36px; }
  .footer-inner { grid-template-columns: 1fr 1fr; gap: 24px; }
  .brand-section { grid-column: 1 / -1; }
  .copyright { flex-wrap: wrap; gap: 8px; text-align: center; }
}
@media (max-width: 480px) {
  .footer-inner { grid-template-columns: 1fr 1fr; }
}
</style>
