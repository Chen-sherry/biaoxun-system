<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ref, computed, onMounted } from 'vue'

const router = useRouter()
const keyword = ref('')
const token = ref(localStorage.getItem('token') || '')

// 路由切换时重读登录态：登录/退出是写 localStorage 后跳转，不刷新页面，
// 否则先挂载的头部会一直停留在旧状态（登录后仍显示"登录/注册"）
function syncToken() { token.value = localStorage.getItem('token') || '' }
onMounted(syncToken)
router.afterEach(syncToken)

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
        <router-link to="/ai-match" active-class="active">AI 智能匹配</router-link>
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
</style>
