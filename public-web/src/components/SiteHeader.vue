<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ref, computed, onMounted } from 'vue'

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

<template>
  <header class="site-header">
    <div class="header-inner">
      <div class="logo" @click="router.push('/')">
        <span class="logo-icon">📢</span>
        <span class="logo-text">标讯速递</span>
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
            <span class="user-link">👤 我的</span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="router.push('/member')">个人中心</el-dropdown-item>
                <el-dropdown-item @click="goLogout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
        <el-button v-else type="primary" size="small" @click="goLogin">登录 / 注册</el-button>
        <button class="menu-toggle" type="button" aria-label="菜单" @click="menuOpen = !menuOpen">☰</button>
      </div>
    </div>

    <!-- 移动端下拉面板（≤768px 显示） -->
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
          <button class="mobile-btn" @click="router.push('/member')">👤 我的（个人中心）</button>
          <button class="mobile-btn" @click="goLogout">退出登录</button>
        </template>
        <el-button v-else type="primary" style="width:100%" @click="goLogin">登录 / 注册</el-button>
      </div>
    </div>
  </header>
</template>

<script lang="ts">
import { Search } from '@element-plus/icons-vue'
export default { components: { Search } }
</script>

<style scoped>
.site-header { background: linear-gradient(135deg, #1e5799 0%, #2989d8 100%); box-shadow: 0 2px 8px rgba(0,0,0,0.08); position: sticky; top: 0; z-index: 100; }
.header-inner { max-width: 1200px; margin: 0 auto; padding: 0 24px; height: 64px; display: flex; align-items: center; gap: 32px; }
.logo { display: flex; align-items: center; gap: 8px; color: #fff; cursor: pointer; font-size: 22px; font-weight: 700; }
.logo-icon { font-size: 28px; }
.nav { display: flex; gap: 24px; flex: 1; }
.nav a { color: rgba(255,255,255,0.85); font-size: 15px; padding: 4px 8px; border-radius: 4px; transition: all .2s; }
.nav a:hover { color: #fff; background: rgba(255,255,255,0.1); }
.nav a.active { color: #fff; background: rgba(255,255,255,0.15); }
.header-right { display: flex; align-items: center; gap: 12px; }
.user-link { color: #fff; cursor: pointer; font-size: 14px; }
.menu-toggle { display: none; background: none; border: none; color: #fff; font-size: 22px; cursor: pointer; padding: 2px 6px; line-height: 1; }
.mobile-panel { display: none; }

/* ===== 移动端（≤768px）：导航折叠成汉堡菜单 ===== */
@media (max-width: 768px) {
  .header-inner { gap: 8px; padding: 0 12px; }
  .logo { font-size: 18px; }
  .logo-icon { font-size: 22px; }
  .nav { display: none; }
  .header-right > *:not(.menu-toggle) { display: none; }
  .menu-toggle { display: block; }
  .mobile-panel {
    display: block; position: absolute; left: 0; right: 0; top: 64px;
    background: linear-gradient(135deg, #1e5799 0%, #2989d8 100%);
    padding: 12px 14px 16px; box-shadow: 0 10px 18px rgba(0,0,0,0.18);
    border-top: 1px solid rgba(255,255,255,0.15);
  }
  .mobile-search { margin-bottom: 8px; }
  .mobile-links { display: flex; flex-direction: column; }
  .mobile-links a { color: rgba(255,255,255,0.9); padding: 11px 8px; font-size: 15px; border-radius: 6px; }
  .mobile-links a.active { background: rgba(255,255,255,0.15); color: #fff; }
  .mobile-user { margin-top: 10px; display: flex; flex-direction: column; gap: 8px; }
  .mobile-btn {
    background: rgba(255,255,255,0.12); border: none; color: #fff;
    padding: 10px 8px; border-radius: 6px; font-size: 14px; text-align: left; cursor: pointer;
  }
}
</style>
