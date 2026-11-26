<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ref, computed, onMounted } from 'vue'
import BrandLogo from './BrandLogo.vue'

const router = useRouter()
const keyword = ref('')
const token = ref(localStorage.getItem('token') || '')

// 路由切换时重读登录态：登录/退出是写 localStorage 后跳转，不刷新页面，
// 否则先挂载的头部会一直停留在旧状态（登录后仍显示"登录/注册"）
const menuOpen = ref(false)
function syncToken() { token.value = localStorage.getItem('token') || '' }
onMounted(syncToken)
// 路由切换：重读登录态 + 收起移动端菜单
router.afterEach(() => { syncToken(); menuOpen.value = false })

function onSearch() {
  router.push({ name: 'search', query: { kw: keyword.value.trim() } })
}
function onAi() {
  router.push({ name: 'ai-match', query: { kw: keyword.value.trim() } })
}
function goLogin() { router.push({ name: 'login' }) }
function goLogout() { localStorage.removeItem('token'); token.value = ''; router.push('/') }
const isLoggedIn = computed(() => !!token.value)
</script>

<script lang="ts">
import { Search, User, ArrowDown } from '@element-plus/icons-vue'
export default { components: { Search, User, ArrowDown } }
</script>

<template>
  <header class="site-header">
    <div class="header-grid" aria-hidden="true"></div>
    <div class="header-glow" aria-hidden="true"></div>
    <div class="header-inner">
      <div class="logo" @click="router.push('/')">
        <BrandLogo :size="36" :text-size="21" light />
      </div>
      <nav class="nav">
        <router-link to="/" exact-active-class="active">首页</router-link>
        <router-link to="/search" active-class="active">传统搜索</router-link>
        <router-link to="/ai-match" active-class="active">智能检索</router-link>
        <router-link to="/member" active-class="active">会员中心</router-link>
      </nav>
      <div class="header-right">
        <div class="mini-search">
          <el-input
            v-model="keyword"
            placeholder="搜索标讯..."
            @keyup.enter="onSearch"
            clearable
            size="default"
            style="width: 220px"
          >
            <template #append>
              <el-button :icon="Search" @click="onSearch" />
            </template>
          </el-input>
        </div>
        <div v-if="isLoggedIn" class="user-area">
          <el-dropdown>
            <span class="user-link">
              <el-icon><User /></el-icon>
              <span>我的</span>
              <el-icon class="user-caret"><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="router.push('/member')">个人中心</el-dropdown-item>
                <el-dropdown-item @click="goLogout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
        <el-button v-else class="login-btn" type="primary" size="small" @click="goLogin">
          <el-icon><User /></el-icon><span>登录 / 注册</span>
        </el-button>
        <button class="menu-toggle" type="button" aria-label="菜单" @click="menuOpen = !menuOpen">
          <span :class="['burger', { open: menuOpen }]"><i></i><i></i><i></i></span>
        </button>
      </div>
    </div>

    <!-- 移动端下拉面板（≤768px 显示） -->
    <transition name="panel">
      <div v-if="menuOpen" class="mobile-panel">
        <div class="mobile-search">
          <el-input v-model="keyword" placeholder="搜索标讯..." clearable @keyup.enter="onSearch">
            <template #append><el-button :icon="Search" @click="onSearch" /></template>
          </el-input>
        </div>
        <nav class="mobile-links">
          <router-link to="/" exact-active-class="active">首页</router-link>
          <router-link to="/search" active-class="active">传统搜索</router-link>
          <router-link to="/ai-match" active-class="active">智能检索</router-link>
          <router-link to="/member" active-class="active">会员中心</router-link>
        </nav>
        <div class="mobile-user">
          <template v-if="isLoggedIn">
            <button class="mobile-btn" @click="router.push('/member')">
              <el-icon><User /></el-icon> 我的（个人中心）
            </button>
            <button class="mobile-btn" @click="goLogout">退出登录</button>
          </template>
          <el-button v-else type="primary" style="width:100%" @click="goLogin">登录 / 注册</el-button>
        </div>
      </div>
    </transition>
  </header>
</template>

<style scoped>
.site-header {
  position: sticky;
  top: 0;
  z-index: 100;
  background: linear-gradient(115deg, var(--brand-950) 0%, var(--brand-800) 55%, #0b2340 100%);
  box-shadow: 0 4px 24px rgba(4, 12, 24, 0.35), 0 1px 0 rgba(56, 189, 248, 0.12) inset;
  overflow: visible;
}
.header-grid {
  position: absolute; inset: 0; pointer-events: none; opacity: 0.9;
  background-image: url('@/assets/brand/bg-grid.svg');
  background-size: 48px 48px;
  mask-image: linear-gradient(90deg, transparent, #000 20%, #000 80%, transparent);
}
.header-glow {
  position: absolute; top: -60px; right: 12%; width: 360px; height: 180px; pointer-events: none;
  background: radial-gradient(ellipse, rgba(56, 189, 248, 0.22), transparent 70%);
  filter: blur(10px);
}
.header-inner {
  position: relative; z-index: 1;
  max-width: 1200px; margin: 0 auto; padding: 0 24px; height: 66px;
  display: flex; align-items: center; gap: 36px;
}
.logo { cursor: pointer; flex: none; }
.nav { display: flex; gap: 6px; flex: 1; }
.nav a {
  position: relative;
  color: var(--on-dark-soft); font-size: 15px; font-weight: 500;
  padding: 8px 16px; border-radius: 8px; transition: all 0.25s var(--ease);
}
.nav a:hover { color: var(--on-dark); background: rgba(56, 189, 248, 0.10); }
.nav a.active {
  color: #fff;
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.22), rgba(34, 211, 238, 0.08));
  box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.25) inset;
}
.nav a.active::after {
  content: ''; position: absolute; left: 50%; bottom: 4px; transform: translateX(-50%);
  width: 16px; height: 2px; border-radius: 2px;
  background: var(--accent-cyan); box-shadow: 0 0 8px var(--accent-glow);
}
.header-right { display: flex; align-items: center; gap: 14px; flex: none; }
.header-right :deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.08) !important;
  box-shadow: 0 0 0 1px rgba(148, 197, 232, 0.22) inset !important;
}
.header-right :deep(.el-input__inner) { color: var(--on-dark); }
.header-right :deep(.el-input__inner::placeholder) { color: var(--on-dark-mute); }
.header-right :deep(.el-input-group__append) {
  background: rgba(56, 189, 248, 0.16) !important;
  border-color: rgba(148, 197, 232, 0.22) !important;
}
.header-right :deep(.el-input-group__append .el-button) { color: var(--accent); }
.user-link {
  display: inline-flex; align-items: center; gap: 7px;
  color: var(--on-dark); cursor: pointer; font-size: 14px; font-weight: 500;
  padding: 8px 12px; border-radius: 8px; transition: background 0.25s;
}
.user-link:hover { background: rgba(56, 189, 248, 0.12); }
.user-caret { font-size: 12px; opacity: 0.7; margin-left: 2px; }
.login-btn { display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px !important; }
.menu-toggle {
  display: none; background: rgba(56, 189, 248, 0.12); border: 1px solid rgba(56, 189, 248, 0.25);
  border-radius: 8px; cursor: pointer; padding: 9px 10px;
}
.burger { display: flex; flex-direction: column; gap: 4px; width: 20px; }
.burger i { display: block; height: 2px; border-radius: 2px; background: var(--on-dark); transition: all 0.25s; }
.burger.open i:nth-child(1) { transform: translateY(6px) rotate(45deg); }
.burger.open i:nth-child(2) { opacity: 0; }
.burger.open i:nth-child(3) { transform: translateY(-6px) rotate(-45deg); }
.mobile-panel { display: none; }

.panel-enter-active, .panel-leave-active { transition: all 0.25s var(--ease); }
.panel-enter-from, .panel-leave-to { opacity: 0; transform: translateY(-8px); }

/* ===== 移动端（≤768px）：导航折叠成汉堡菜单，保留原有断点行为 ===== */
@media (max-width: 768px) {
  .header-inner { gap: 10px; padding: 0 12px; height: 60px; }
  .nav { display: none; }
  .header-right > .mini-search,
  .header-right > .user-area,
  .header-right > .login-btn { display: none; }
  .menu-toggle { display: block; }
  .mobile-panel {
    display: block; position: absolute; left: 0; right: 0; top: 60px; z-index: 2;
    background: linear-gradient(160deg, var(--brand-900), var(--brand-800));
    padding: 14px 14px 18px; box-shadow: 0 16px 28px rgba(0, 0, 0, 0.32);
    border-top: 1px solid rgba(56, 189, 248, 0.2);
  }
  .mobile-search { margin-bottom: 10px; }
  .mobile-links { display: flex; flex-direction: column; gap: 2px; }
  .mobile-links a {
    color: var(--on-dark-soft); padding: 12px 12px; font-size: 15px; border-radius: 8px;
  }
  .mobile-links a.active { background: rgba(56, 189, 248, 0.18); color: #fff; }
  .mobile-user { margin-top: 12px; display: flex; flex-direction: column; gap: 8px; }
  .mobile-btn {
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(255, 255, 255, 0.08); border: 1px solid rgba(148, 197, 232, 0.16);
    color: var(--on-dark); padding: 11px 12px; border-radius: 8px; font-size: 14px; text-align: left; cursor: pointer;
  }
}
</style>
