<template>
  <el-container class="basic-layout">
    <el-aside width="224px" class="aside">
      <div class="logo">
        <BrandLogo :size="32" :text-size="17" text="标讯管理后台" light />
      </div>
      <div class="aside-glow" aria-hidden="true"></div>
      <el-menu
        :default-active="route.path"
        :default-openeds="defaultOpeneds"
        router
        class="menu"
        background-color="transparent"
        text-color="#93a9c4"
        active-text-color="#38bdf8"
      >
        <!-- 工作台：独立常驻，不折叠 -->
        <template v-for="item in menuList" :key="item.path">
          <el-menu-item :index="'/' + item.path">
            <el-icon v-if="item.meta?.icon"><component :is="item.meta.icon" /></el-icon>
            <template #title>{{ item.meta?.title }}</template>
          </el-menu-item>
        </template>
        <!-- 其余业务分组：可折叠 -->
        <el-sub-menu
          v-for="g in groupedMenus"
          :key="g.key"
          :index="g.key"
        >
          <template #title>
            <el-icon><component :is="g.icon" /></el-icon>
            <span>{{ g.title }}</span>
          </template>
          <el-menu-item
            v-for="item in g.children"
            :key="item.path"
            :index="'/' + item.path"
          >
            <template #title>{{ item.meta?.title }}</template>
          </el-menu-item>
        </el-sub-menu>
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
import type { RouteRecordRaw } from 'vue-router'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const allMenus = computed<RouteRecordRaw[]>(() => {
  const root = constantRoutes.find((r) => r.path === '/' && r.children)
  return (root?.children || []).filter((c) => !c.meta?.hidden)
})

// 工作台：控制台独立常驻
const menuList = computed(() =>
  allMenus.value.filter((c) => c.path === 'dashboard')
)

// 分组定义（key 同时是 el-sub-menu index）
const GROUP_DEFS = [
  { key: 'bid',     title: '标讯管理',   icon: 'Document',    match: ['bid/'] },
  { key: 'data',    title: '采集与数据', icon: 'MagicStick',  match: ['crawl/', 'data/'] },
  { key: 'push',    title: '推送中心',   icon: 'Promotion',   match: ['push/'] },
  { key: 'member',  title: '会员与用户', icon: 'Medal',       match: ['member/', 'user/'] },
  { key: 'setting', title: '系统设置',   icon: 'Setting',     match: ['setting/', 'ai/'] },
]

const groupedMenus = computed(() => {
  return GROUP_DEFS
    .map((g) => {
      const children = allMenus.value.filter(
        (c) => g.match.some((p) => String(c.path).startsWith(p))
      )
      return { ...g, children }
    })
    .filter((g) => g.children.length > 0)
})

// 根据当前路由自动展开所属分组
const defaultOpeneds = computed(() => {
  const cur = route.path.replace(/^\//, '')
  const g = GROUP_DEFS.find((g) => g.match.some((p) => cur.startsWith(p)))
  return g ? [g.key] : []
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
  position: relative; z-index: 1; flex: 1; min-height: 0;
  overflow-y: auto; border-right: none;
  --el-menu-bg-color: transparent;
  --el-menu-hover-bg-color: rgba(56, 189, 248, 0.10);
}
/* 侧边栏菜单滚动条：细窄、悬停显现，避免菜单多时点不到底部 */
.menu::-webkit-scrollbar { width: 4px; }
.menu::-webkit-scrollbar-thumb { background: rgba(56, 189, 248, 0.28); border-radius: 4px; }
.menu::-webkit-scrollbar-track { background: transparent; }
.menu { scrollbar-width: thin; scrollbar-color: rgba(56, 189, 248, 0.28) transparent; }
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
.menu :deep(.el-sub-menu__title) {
  height: 40px; line-height: 40px; margin: 2px 10px; border-radius: 8px;
  font-size: 13px; font-weight: 600; letter-spacing: 0.5px;
  color: rgba(148, 197, 232, 0.78);
}
.menu :deep(.el-sub-menu__title:hover) {
  background: rgba(56, 189, 248, 0.10); color: #fff;
}
.menu :deep(.el-sub-menu__title .el-sub-menu__icon-arrow) {
  right: 14px; color: rgba(148, 197, 232, 0.5); font-size: 12px;
}
.menu :deep(.el-sub-menu .el-menu-item) { height: 40px; line-height: 40px; margin: 0 10px 2px; padding-left: 48px; font-size: 13px; }
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
