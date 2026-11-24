<template>
  <el-container class="basic-layout">
    <el-aside width="220px" class="aside">
      <div class="logo">
        <el-icon><Document /></el-icon>
        <span>标讯管理后台</span>
      </div>
      <el-menu
        :default-active="route.path"
        router
        class="menu"
        background-color="#1f2d3d"
        text-color="#b0bec5"
        active-text-color="#fff"
      >
        <template v-for="item in menuList" :key="item.path">
          <el-menu-item :index="'/' + item.path">
            <el-icon v-if="item.meta?.icon"><component :is="item.meta.icon" /></el-icon>
            <template #title>{{ item.meta?.title }}</template>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <el-breadcrumb separator="/">
          <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
          <el-breadcrumb-item>{{ route.meta?.title }}</el-breadcrumb-item>
        </el-breadcrumb>
        <el-dropdown @command="handleCommand">
          <span class="user-info">
            <el-avatar :size="32" :src="userStore.info?.avatar">
              {{ userStore.info?.nickname?.[0] || userStore.info?.username?.[0] }}
            </el-avatar>
            <span class="username">{{ userStore.info?.nickname || userStore.info?.username }}</span>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
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
  background: #1f2d3d;
  display: flex;
  flex-direction: column;
}
.logo {
  height: 60px;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  border-bottom: 1px solid #2d3d50;
}
.menu { flex: 1; border-right: none; }
.header {
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #ebeef5;
}
.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}
.main { background: var(--app-bg); padding: 16px; }
</style>
