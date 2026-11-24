<template>
  <div class="member">
    <van-nav-bar title="开通会员" left-arrow @click-left="$router.back()" fixed placeholder />
    <div class="banner">
      <h2>高级会员权益</h2>
      <p>不限量标讯订阅 · 全文联系方式 · 批量导出</p>
    </div>

    <van-cell-group inset style="margin-top: 12px">
      <van-price
        v-for="pkg in packages"
        :key="pkg.id"
        :price="pkg.sale_price * 100"
        :desc="pkg.description"
        :title="pkg.name"
        :tags="[`有效期 ${pkg.duration_days} 天`]"
        currency="¥"
        @click="buy(pkg)"
      >
        <template #right>
          <van-button round type="primary" :price="pkg.sale_price">购买</van-button>
        </template>
      </van-price>
    </van-cell-group>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { showToast } from 'vant'
import request from '@/utils/request'

const packages = ref<any[]>([])
onMounted(async () => {
  // packages.value = await request.get('/api/v1/member-packages')
  packages.value = [
    { id: 2, name: '月度会员', sale_price: 79, duration_days: 30, description: '30 天高级功能' },
    { id: 3, name: '年度会员', sale_price: 699, duration_days: 365, description: '最受欢迎的年度套餐' },
    { id: 4, name: '企业会员', sale_price: 3999, duration_days: 365, description: '适合企业团队使用' },
  ]
})
async function buy(pkg: any) {
  showToast(`正在创建订单 ${pkg.name}`)
  // 1) POST /api/v1/member-orders  2) 调用微信/支付宝支付  3) 支付成功后端回调
}
</script>

<style scoped>
.banner {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  margin: 12px; border-radius: 12px; padding: 24px;
  h2 { margin: 0 0 6px; font-size: 22px; }
  p { margin: 0; opacity: 0.85; font-size: 14px; }
}
</style>
