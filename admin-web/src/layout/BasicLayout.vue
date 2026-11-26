<template>
  <el-container class="basic-layout">
    <el-aside width="224px" class="aside">
      <div class="logo">
        <BrandLogo :size="32" :text-size="17" text="标讯管理中台" light />
      </div>
      <div class="aside-glow" aria-hidden="true"></div>
      <div class="aside-label">工作台 / WORKSPACE</div>
      <el-menu
        :default-active="route.path"
        router
        class="menu"
        background-color="transparent"
        text-color="#93a9c4"
        active-text-color="#38bdf8"
      >
        <template v-for="item in menuList" :key="item.path">
          <el-menu-item :index="'/' + item.path">
            <el-icon v-if="item.meta?.icon"><component :is="item.meta.icon" /></el-icon>
            <template #title>{{ item.meta?.title }}</template>
          </el-menu-item>
        </template>
      </el-menu>
      <div class="aside-footer">
        <span class="status-dot"></span> 系统运行正常
      </div>
    </el-aside>

    <el-container class="content-wrap">
      <el-header class="header">
        <el-breadcrumb separator="/">
          <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
          <el-breadcrumb-item>{{ route.meta?.title }}</el-breadcrumb-item>
        </el-breadcrumb>
        <div class="header-right">
          <span class="header-badge"><span class="status-dot"></span> 实时数据</span>
          <el-dropdown @command="handleCommand">
            <span class="user-info">
              <el-avatar :size="34" :src="userStore.info?.avatar" class="user-avatar">
                {{ userStore.info?.nickname?.[0] || userStore.info?.username?.[0] }}
              </el-avatar>
              <span class="username">{{ userStore.info?.nickname || userStore.info?.username }}</span>
              <el-icon class="user-caret"><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowDown } from '@element-plus/icons-vue'
import BrandLogo from '@/components/BrandLogo.vue'
import { constantRoutes } from '@/router/routes'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const menuList = computed(() => {
  const root = constantRoutes.find((r) => r.path === '/' && r.children)
  return (root?.children || []).filter((c) => !c.meta?.hidden)
})

function handleCommand(cmd: string) {
  if (cmd === 'logout') {
    userStore.logout()
    router.replace('/login')
  }
}
</script>

<style lang="scss" scoped>
.basic-layout { height: 100vh; }
.aside {
  position: relative;
  background: linear-gradient(165deg, var(--brand-950) 0%, var(--brand-850) 60%, var(--brand-800) 100%);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-right: 1px solid rgba(56, 189, 248, 0.12);
}
.aside::before {
  content: ''; position: absolute; inset: 0; pointer-events: none;
  background-image: url('@/assets/brand/bg-grid.svg');
  background-size: 48px 48px; opacity: 0.6;
  mask-image: linear-gradient(180deg, #000, transparent 75%);
}
.aside-glow {
  position: absolute; top: 40px; left: -120px; width: 320px; height: 320px; pointer-events: none;
  background-image: url('@/assets/brand/bg-glow.svg'); background-size: cover; opacity: 0.5;
}
.logo {
  position: relative; z-index: 1;
  height: 64px; flex: none;
  display: flex; align-items: center; justify-content: center;
  border-bottom: 1px solid rgba(148, 197, 232, 0.12);
}
.aside-label {
  position: relative; z-index: 1;
  font-size: 10px; font-weight: 700; letter-spacing: 2px;
  color: var(--on-dark-mute); padding: 18px 22px 8px;
}
.menu {
  position: relative; z-index: 1; flex: 1; border-right: none;
  --el-menu-bg-color: transparent;
  --el-menu-hover-bg-color: rgba(56, 189, 248, 0.10);
}
.menu :deep(.el-menu-item) { height: 46px; line-height: 46px; margin: 2px 10px; border-radius: 8px; }
.menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.22), rgba(34, 211, 238, 0.06)) !important;
  box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.22) inset;
  font-weight: 600;
}
.menu :deep(.el-menu-item.is-active)::before {
  content: ''; position: absolute; left: 0; top: 12px; bottom: 12px; width: 3px;
  border-radius: 0 3px 3px 0; background: var(--accent); box-shadow: 0 0 10px var(--accent-glow);
}
.aside-footer {
  position: relative; z-index: 1; flex: none;
  padding: 16px 22px; font-size: 12px; color: var(--on-dark-mute);
  border-top: 1px solid rgba(148, 197, 232, 0.1);
  display: flex; align-items: center; gap: 8px;
}
.status-dot {
  width: 7px; height: 7px; border-radius: 50%; background: #34d399; flex: none;
  box-shadow: 0 0 8px rgba(52, 211, 153, 0.7);
}
.content-wrap { background: var(--surface-soft); }
.header {
  background: var(--surface);
  display: flex; align-items: center; justify-content: space-between;
  border-bottom: 1px solid var(--line);
  box-shadow: 0 1px 8px rgba(15, 40, 70, 0.04);
}
.header-right { display: flex; align-items: center; gap: 18px; }
.header-badge {
  display: inline-flex; align-items: center; gap: 7px; font-size: 12px; color: var(--ink-500);
  padding: 5px 12px; border-radius: 999px; background: var(--surface-soft); border: 1px solid var(--line);
}
.user-info { display: flex; align-items: center; gap: 9px; cursor: pointer; padding: 6px 8px; border-radius: 8px; transition: background 0.25s; }
.user-info:hover { background: var(--surface-soft); }
.user-avatar { background: linear-gradient(135deg, var(--accent-strong), var(--accent-deep)) !important; font-weight: 600; }
.username { font-size: 14px; color: var(--ink-800); font-weight: 500; }
.user-caret { font-size: 12px; color: var(--ink-400); }
.main { background: var(--surface-soft); padding: 16px; }
</style>
