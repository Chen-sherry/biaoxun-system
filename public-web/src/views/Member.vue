<template>
  <div class="member-page">
    <div class="member-glow" aria-hidden="true"></div>
    <div class="member-head">
      <span class="section-kicker">MEMBER CENTER</span>
      <h1><el-icon><User /></el-icon> 会员中心</h1>
      <p>会员套餐 / 订阅管理 / 收藏标讯 —— 更多专属能力持续上线中</p>
    </div>

    <!-- A. 会员状态横幅 -->
    <div v-if="isLoggedIn" class="status-banner tech-card" :class="{ 'is-member': memberStatus.is_member }">
      <template v-if="memberStatus.is_member">
        <div class="status-left">
          <el-tag type="warning" effect="dark" size="large">
            <el-icon><Medal /></el-icon> {{ memberStatus.package_name }}
          </el-tag>
          <span class="status-text">有效期至 {{ formatDate(memberStatus.end_date) }}，剩余 <strong>{{ memberStatus.remaining_days }}</strong> 天</span>
        </div>
        <div class="status-right">
          <el-button type="primary" plain size="small" @click="scrollToPackages">续费 / 升级</el-button>
        </div>
      </template>
      <template v-else>
        <div class="status-left">
          <el-icon :size="20" color="var(--accent)"><InfoFilled /></el-icon>
          <span class="status-text">当前非会员，开通会员享受智能检索、订阅推送等专属权益</span>
        </div>
        <div class="status-right">
          <el-button type="primary" size="small" @click="scrollToPackages">查看套餐</el-button>
        </div>
      </template>
    </div>

    <!-- B. 套餐卡片区 -->
    <div ref="packagesRef">
      <h2 class="section-title">选择套餐</h2>
      <div class="package-grid">
        <div
          v-for="pkg in packages"
          :key="pkg.id"
          class="package-card tech-card"
          :class="{ recommended: pkg.code === 'year' }"
        >
          <div v-if="pkg.code === 'year'" class="rec-badge">推荐</div>
          <h3 class="pkg-name">{{ pkg.name }}</h3>
          <div class="pkg-price">
            <span class="price-symbol">¥</span>
            <span class="price-value">{{ pkg.sale_price }}</span>
            <span v-if="pkg.price > pkg.sale_price" class="price-original">¥{{ pkg.price }}</span>
          </div>
          <div class="pkg-duration">{{ pkg.duration_days }} 天</div>
          <ul class="pkg-features">
            <li><el-icon color="var(--success)"><Check /></el-icon> 最多 {{ pkg.max_subscribe }} 个订阅</li>
            <li><el-icon :color="pkg.allow_export ? 'var(--success)' : 'var(--ink-400)'"><Check /></el-icon> {{ pkg.allow_export ? '允许导出' : '不可导出' }}</li>
            <li><el-icon :color="pkg.allow_contact ? 'var(--success)' : 'var(--ink-400)'"><Check /></el-icon> {{ pkg.allow_contact ? '可见联系方式' : '不可见联系方式' }}</li>
            <li><el-icon color="var(--success)"><Check /></el-icon> AI 智能检索</li>
          </ul>
          <p v-if="pkg.description" class="pkg-desc">{{ pkg.description }}</p>
          <el-button
            :type="pkg.code === 'year' ? 'primary' : 'default'"
            class="pkg-btn"
            :loading="purchasingId === pkg.id"
            @click="handlePurchase(pkg)"
          >
            {{ pkg.sale_price === 0 ? '免费注册' : '立即开通' }}
          </el-button>
        </div>
      </div>
    </div>

    <!-- C. 我的订单 -->
    <div v-if="isLoggedIn" class="orders-section">
      <h2 class="section-title">我的订单</h2>
      <div class="tech-card" style="padding: 0; overflow: hidden;">
        <el-table :data="orders" v-loading="ordersLoading" stripe :header-cell-style="{ background: '#f4f8fd' }">
          <el-table-column prop="order_no" label="订单号" min-width="200" show-overflow-tooltip />
          <el-table-column prop="package_name" label="套餐" width="120" />
          <el-table-column prop="amount" label="金额" width="100">
            <template #default="{ row }">¥{{ row.amount.toFixed(2) }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="orderStatusType(row.status)" size="small">{{ orderStatusText(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="时间" width="160">
            <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
          </el-table-column>
        </el-table>
        <div v-if="orders.length === 0 && !ordersLoading" style="padding: 30px; text-align: center;">
          <el-empty description="暂无订单" :image-size="100" />
        </div>
      </div>
    </div>

    <!-- 未登录提示 -->
    <div v-else class="login-hint tech-card">
      <el-icon :size="24" color="var(--ink-400)"><Lock /></el-icon>
      <p>登录后查看您的订单记录</p>
      <el-button type="primary" plain @click="$router.push('/login?redirect=/member')">立即登录</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { User, Medal, InfoFilled, Check, Lock } from '@element-plus/icons-vue'
import { fetchMemberPackages, fetchMyMemberStatus, fetchMyOrders, createOrder, payOrder } from '@/api'

const isLoggedIn = computed(() => !!localStorage.getItem('token'))
const packages = ref<any[]>([])
const memberStatus = ref<any>({ is_member: false })
const orders = ref<any[]>([])
const ordersLoading = ref(false)
const purchasingId = ref<number | null>(null)
const packagesRef = ref<HTMLElement>()

function formatDate(t: any) {
  if (!t) return ''
  if (typeof t === 'string') return t.replace('T', ' ').slice(0, 10)
  return new Date(t).toLocaleDateString()
}
function orderStatusText(s: number) {
  return { 0: '待支付', 1: '已支付', 2: '已取消', 3: '已退款' }[s] || '未知'
}
function orderStatusType(s: number) {
  return { 0: 'warning', 1: 'success', 2: 'info', 3: 'danger' }[s] as any || 'info'
}
function scrollToPackages() {
  packagesRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function loadPackages() {
  try { packages.value = await fetchMemberPackages() } catch { /* ignore */ }
}
async function loadStatus() {
  if (!isLoggedIn.value) return
  try { memberStatus.value = await fetchMyMemberStatus() } catch { /* ignore */ }
}
async function loadOrders() {
  if (!isLoggedIn.value) return
  ordersLoading.value = true
  try {
    const res = await fetchMyOrders({ page: 1, page_size: 10 })
    orders.value = res.items || []
  } catch { /* ignore */ } finally { ordersLoading.value = false }
}

async function handlePurchase(pkg: any) {
  if (!isLoggedIn.value) {
    ElMessageBox.confirm('请先登录后再购买套餐', '需要登录', {
      confirmButtonText: '去登录',
      cancelButtonText: '取消',
    }).then(() => {
      window.location.href = '/login?redirect=/member'
    }).catch(() => {})
    return
  }
  purchasingId.value = pkg.id
  try {
    // 创建订单
    const orderRes = await createOrder({ package_id: pkg.id })
    const orderNo = orderRes.order_no
    // 模拟支付
    await payOrder(orderNo)
    ElMessage.success('开通成功！会员权益已生效')
    // 刷新状态和订单
    await loadStatus()
    await loadOrders()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '购买失败')
  } finally { purchasingId.value = null }
}

onMounted(() => {
  loadPackages()
  loadStatus()
  loadOrders()
})
</script>

<style scoped>
.member-page { position: relative; max-width: 1000px; margin: 28px auto; padding: 0 24px 30px; overflow: hidden; }
.member-glow {
  position: absolute; top: -160px; right: -160px; width: 560px; height: 480px; pointer-events: none;
  background-image: url('@/assets/brand/bg-glow.svg'); background-size: cover; opacity: 0.55;
}
.member-head { position: relative; z-index: 1; margin-bottom: 24px; }
.member-head h1 { font-size: 27px; font-weight: 800; color: var(--ink-900); margin: 8px 0 6px; display: flex; align-items: center; gap: 10px; }
.member-head h1 :deep(.el-icon) { color: var(--accent-strong); }
.member-head p { color: var(--ink-500); font-size: 14px; }

/* 状态横幅 */
.status-banner { position: relative; z-index: 1; padding: 16px 20px; margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between; }
.status-banner.is-member { background: linear-gradient(135deg, color-mix(in srgb, var(--accent) 8%, #fff), color-mix(in srgb, var(--accent-violet) 6%, #fff)); border-color: color-mix(in srgb, var(--accent) 30%, transparent); }
.status-left { display: flex; align-items: center; gap: 12px; }
.status-text { color: var(--ink-700); font-size: 14px; }

/* 段落标题 */
.section-title { position: relative; z-index: 1; font-size: 18px; font-weight: 700; color: var(--ink-900); margin: 20px 0 14px; padding-left: 14px; }
.section-title::before { content: ''; position: absolute; left: 0; top: 50%; transform: translateY(-50%); width: 4px; height: 18px; border-radius: 2px; background: var(--accent); box-shadow: 0 0 8px var(--accent-glow); }

/* 套餐卡片 */
.package-grid { position: relative; z-index: 1; display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.package-card { position: relative; padding: 24px 18px 20px; text-align: center; display: flex; flex-direction: column; transition: transform 0.25s var(--ease), box-shadow 0.25s var(--ease); }
.package-card:hover { transform: translateY(-4px); box-shadow: var(--shadow-hover); }
.package-card.recommended { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent), var(--shadow-card); }
.rec-badge { position: absolute; top: -1px; right: 16px; background: linear-gradient(135deg, var(--accent), var(--accent-violet)); color: #fff; font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 0 0 8px 8px; }
.pkg-name { margin: 0 0 12px; font-size: 16px; font-weight: 700; color: var(--ink-900); }
.pkg-price { margin-bottom: 4px; }
.price-symbol { font-size: 16px; font-weight: 600; color: var(--accent-strong); vertical-align: top; margin-right: 2px; }
.price-value { font-size: 36px; font-weight: 800; color: var(--accent-strong); line-height: 1; }
.price-original { font-size: 14px; color: var(--ink-400); text-decoration: line-through; margin-left: 6px; }
.pkg-duration { font-size: 13px; color: var(--ink-500); margin-bottom: 14px; }
.pkg-features { list-style: none; padding: 0; margin: 0 0 14px; text-align: left; }
.pkg-features li { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--ink-600); padding: 3px 0; }
.pkg-desc { font-size: 12px; color: var(--ink-400); margin: 0 0 14px; line-height: 1.5; }
.pkg-btn { width: 100%; margin-top: auto; }

/* 订单区 */
.orders-section { position: relative; z-index: 1; }

/* 登录提示 */
.login-hint { position: relative; z-index: 1; padding: 30px; text-align: center; }
.login-hint p { color: var(--ink-500); margin: 10px 0 16px; }

@media (max-width: 768px) {
  .member-page { margin: 16px auto; padding: 0 12px; }
  .member-head h1 { font-size: 21px; }
  .package-grid { grid-template-columns: repeat(2, 1fr); gap: 12px; }
  .status-banner { flex-direction: column; gap: 10px; align-items: flex-start; }
}
@media (max-width: 480px) {
  .package-grid { grid-template-columns: 1fr; }
}
</style>
