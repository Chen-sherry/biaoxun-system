import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'home', component: () => import('@/views/Home.vue') },
    { path: '/search', name: 'search', component: () => import('@/views/Search.vue') },
    { path: '/bid/:id', name: 'bid-detail', component: () => import('@/views/BidDetail.vue') },
    { path: '/login', name: 'login', component: () => import('@/views/Login.vue') },
    { path: '/member', name: 'member', component: () => import('@/views/Member.vue') },
    { path: '/ai-match', name: 'ai-match', component: () => import('@/views/AIMatch.vue') },
    { path: '/404', component: () => import('@/views/NotFound.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/404' },
  ],
  scrollBehavior() { return { top: 0 } },
})

export default router
