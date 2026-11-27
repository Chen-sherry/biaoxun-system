import request from '@/utils/request'
import type { RouteRecordRaw } from 'vue-router'

// 路由守卫
export default function setupRouter() {
  // 路由表由 router/index.ts 中定义，这里只做统一导出
}

export const constantRoutes: RouteRecordRaw[] = [
  { path: '/', redirect: '/dashboard' },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: { hidden: true, title: '登录' },
  },
  {
    path: '/',
    component: () => import('@/layout/BasicLayout.vue'),
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/index.vue'),
        meta: { title: '控制台', icon: 'Odometer' },
      },
      {
        path: 'bid/list',
        name: 'BidList',
        component: () => import('@/views/bid/list.vue'),
        meta: { title: '标讯列表', icon: 'Document' },
      },
      {
        path: 'bid/pending',
        name: 'BidPending',
        component: () => import('@/views/bid/pending.vue'),
        meta: { title: '待审核', icon: 'Warning' },
      },
      {
        path: 'bid/edit/:id?',
        name: 'BidEdit',
        component: () => import('@/views/bid/edit.vue'),
        meta: { title: '标讯编辑', hidden: true },
      },
      {
        path: 'crawl/source',
        name: 'CrawlSource',
        component: () => import('@/views/crawl/source.vue'),
        meta: { title: '采集源管理', icon: 'Connection' },
      },
      {
        path: 'subscribe/list',
        name: 'SubscribeList',
        component: () => import('@/views/subscribe/list.vue'),
        meta: { title: '订阅管理', icon: 'Bell', hidden: true },
      },
      {
        path: 'push/scheduled',
        name: 'PushScheduled',
        component: () => import('@/views/push/scheduled.vue'),
        meta: { title: '定时推送', icon: 'Timer' },
      },
      {
        path: 'push/manual',
        name: 'PushManual',
        component: () => import('@/views/push/manual.vue'),
        meta: { title: '临时推送', icon: 'Promotion' },
      },
      {
        path: 'push/subscribers',
        name: 'PushSubscribers',
        component: () => import('@/views/push/subscribers.vue'),
        meta: { title: '订阅用户', icon: 'User' },
      },
      {
        path: 'push/records',
        name: 'PushRecords',
        component: () => import('@/views/push/records.vue'),
        meta: { title: '推送记录', icon: 'List' },
      },
      {
        path: 'data/clean',
        name: 'DataClean',
        component: () => import('@/views/data/clean.vue'),
        meta: { title: '数据清洗', icon: 'MagicStick' },
      },
      {
        path: 'user/list',
        name: 'UserList',
        component: () => import('@/views/user/list.vue'),
        meta: { title: '用户管理', icon: 'User' },
      },
      {
        path: 'member/package',
        name: 'MemberPackage',
        component: () => import('@/views/member/package.vue'),
        meta: { title: '套餐管理', icon: 'Medal' },
      },
      {
        path: 'member/order',
        name: 'MemberOrder',
        component: () => import('@/views/member/order.vue'),
        meta: { title: '订单管理', icon: 'Tickets' },
      },
      {
        path: 'setting/notice-type',
        name: 'SettingNoticeType',
        component: () => import('@/views/setting/notice-type.vue'),
        meta: { title: '公告类型', icon: 'Setting' },
      },
      {
        path: 'ai/setting',
        name: 'AISetting',
        component: () => import('@/views/ai/setting.vue'),
        meta: { title: 'AI 设置', icon: 'MagicStick' },
      },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard', meta: { hidden: true } },
]
