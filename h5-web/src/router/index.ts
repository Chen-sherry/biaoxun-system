import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/home' },
    { path: '/home', name: 'Home', component: () => import('@/views/home.vue'), meta: { title: '标讯首页' } },
    { path: '/list', name: 'List', component: () => import('@/views/list.vue'), meta: { title: '标讯列表' } },
    { path: '/detail/:id', name: 'Detail', component: () => import('@/views/detail.vue'), meta: { title: '标讯详情', hideTabbar: true } },
    { path: '/subscribe', name: 'Subscribe', component: () => import('@/views/subscribe.vue'), meta: { title: '我的订阅' } },
    { path: '/mine', name: 'Mine', component: () => import('@/views/mine.vue'), meta: { title: '我的' } },
    { path: '/login', name: 'Login', component: () => import('@/views/login.vue'), meta: { title: '登录', hideTabbar: true } },
    { path: '/member', name: 'Member', component: () => import('@/views/member.vue'), meta: { title: '开通会员', hideTabbar: true } },
  ],
})

export default router
