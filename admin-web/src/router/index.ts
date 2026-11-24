import { createRouter, createWebHashHistory } from 'vue-router'
import { ElMessage } from 'element-plus'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'
import { constantRoutes } from './routes'
import { useUserStore } from '@/stores/user'

NProgress.configure({ showSpinner: false })

const router = createRouter({
  history: createWebHashHistory(),
  routes: constantRoutes,
})

const WHITE_LIST = ['/login', '/404']

// 监听 axios 拦截器派发的统一鉴权失败事件
window.addEventListener('auth:unauthorized', () => {
  const currentPath = router.currentRoute.value.fullPath
  const userStore = useUserStore()
  userStore.logout()
  // 避免死循环：如果当前已经在 login 页就不要再跳了
  if (router.currentRoute.value.path !== '/login') {
    router.replace(`/login?redirect=${encodeURIComponent(currentPath)}`)
  }
})

router.beforeEach(async (to, _from, next) => {
  NProgress.start()
  const token = localStorage.getItem('BID_ADMIN_TOKEN')

  if (token) {
    // 已登录用户访问 login → 回首页
    if (to.path === '/login') {
      next({ path: '/' })
      return
    }
    const userStore = useUserStore()
    // 确保拿到 user info（防并发锁已在 store 内部实现）
    if (!userStore.info) {
      try {
        await userStore.fetchInfo()
      } catch {
        // fetchInfo 失败（token 无效/过期）→ 清理并跳登录
        userStore.logout()
        next(`/login?redirect=${encodeURIComponent(to.path)}`)
        return
      }
    }
    next()
    return
  }

  // 无 token：白名单直接放行，否则跳登录
  if (WHITE_LIST.includes(to.path)) {
    next()
    return
  }
  ElMessage.warning('请先登录')
  next(`/login?redirect=${encodeURIComponent(to.path)}`)
})

router.afterEach(() => {
  NProgress.done()
})

export default router
