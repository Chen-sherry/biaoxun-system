<template>
  <div class="login-page">
    <div class="login-grid" aria-hidden="true"></div>
    <div class="login-glow" aria-hidden="true"></div>
    <div class="decor-ring" aria-hidden="true"></div>
    <div class="decor-ring r2" aria-hidden="true"></div>

    <div class="login-shell">
      <div class="login-intro">
        <BrandLogo :size="58" :text-size="30" light />
        <h2>数据驱动的招投标智能平台</h2>
        <p>汇聚全国公共资源交易数据，以 AI 语义匹配与精准筛选，让每一条商机都被看见。</p>
        <div class="intro-features">
          <span><el-icon><DataLine /></el-icon> 实时聚合</span>
          <span><el-icon><MagicStick /></el-icon> AI 智能检索</span>
          <span><el-icon><Bell /></el-icon> 订阅推送</span>
        </div>
      </div>

      <div class="login-box">
        <div class="card-top-glow" aria-hidden="true"></div>
        <div class="box-head">
          <h3>管理员登录</h3>
          <p>欢迎回来，请输入账号与密码</p>
        </div>
        <el-form ref="formRef" :model="form" :rules="rules" label-width="0" size="large">
          <el-form-item prop="username">
            <el-input v-model="form.username" placeholder="用户名" :prefix-icon="User" />
          </el-form-item>
          <el-form-item prop="password">
            <el-input v-model="form.password" type="password" show-password placeholder="密码" :prefix-icon="Lock" />
          </el-form-item>
          <el-button type="primary" :loading="loading" class="submit" @click="handleLogin">登 录</el-button>
        </el-form>
        <div class="tips">默认账号 admin / admin123</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { User, Lock, DataLine, MagicStick, Bell } from '@element-plus/icons-vue'
import BrandLogo from '@/components/BrandLogo.vue'
import { useUserStore } from '@/stores/user'

const formRef = ref<FormInstance>()
const loading = ref(false)
const form = reactive({ username: 'admin', password: 'admin123' })
const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}
const userStore = useUserStore()
const router = useRouter()
const route = useRoute()

async function handleLogin() {
  await formRef.value?.validate()
  loading.value = true
  try {
    await userStore.login(form.username, form.password)
    ElMessage.success('登录成功')
    const redirect = (route.query.redirect as string) || '/'
    router.replace(redirect)
  } finally { loading.value = false }
}
</script>

<style lang="scss" scoped>
.login-page {
  position: relative; min-height: 100vh; display: flex; align-items: center; justify-content: center;
  padding: 40px 24px; overflow: hidden;
  background: linear-gradient(125deg, var(--brand-950) 0%, var(--brand-850) 52%, #0c2947 100%);
}
.login-grid {
  position: absolute; inset: 0; pointer-events: none; opacity: 0.8;
  background-image: url('@/assets/brand/bg-grid.svg'); background-size: 48px 48px;
  mask-image: radial-gradient(ellipse at 50% 45%, #000 15%, transparent 80%);
}
.login-glow {
  position: absolute; left: 40%; top: 50%; transform: translate(-50%, -50%);
  width: 1000px; height: 800px; pointer-events: none;
  background-image: url('@/assets/brand/bg-glow.svg'); background-size: cover; opacity: 0.7;
}
.decor-ring { position: absolute; width: 520px; height: 520px; border-radius: 50%; border: 1px solid rgba(56,189,248,0.13); top: -180px; right: -120px; pointer-events: none; }
.decor-ring.r2 { width: 380px; height: 380px; top: auto; right: auto; bottom: -140px; left: -80px; border-color: rgba(129,140,248,0.14); }

.login-shell {
  position: relative; z-index: 2; width: 900px; max-width: 100%;
  display: grid; grid-template-columns: 1fr 400px; align-items: center; gap: 60px;
}
.login-intro { color: var(--on-dark); }
.login-intro h2 { font-size: 30px; font-weight: 800; margin: 24px 0 14px; line-height: 1.3; }
.login-intro p { color: var(--on-dark-soft); font-size: 15px; line-height: 1.8; max-width: 420px; }
.intro-features { display: flex; gap: 12px; margin-top: 26px; flex-wrap: wrap; }
.intro-features span {
  display: inline-flex; align-items: center; gap: 6px; font-size: 13px; color: var(--accent);
  padding: 7px 14px; border-radius: 999px;
  background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.28);
}

.login-box {
  position: relative; width: 100%;
  background: rgba(255, 255, 255, 0.97);
  border: 1px solid rgba(56, 189, 248, 0.22);
  border-radius: var(--r-lg); padding: 38px 36px 28px;
  box-shadow: 0 28px 70px rgba(2, 8, 20, 0.5);
  animation: fade-up 0.5s var(--ease) both;
}
.card-top-glow {
  position: absolute; top: 0; left: 50%; transform: translateX(-50%);
  width: 160px; height: 3px; border-radius: 0 0 4px 4px;
  background: linear-gradient(90deg, transparent, var(--accent), transparent);
  box-shadow: 0 0 16px var(--accent-glow);
}
.box-head { margin-bottom: 26px; }
.box-head h3 { margin: 0 0 6px; font-size: 21px; font-weight: 800; color: var(--ink-900); }
.box-head p { margin: 0; color: var(--ink-500); font-size: 13px; }
.submit { width: 100%; height: 46px; font-weight: 600; letter-spacing: 4px; }
.tips { text-align: center; margin-top: 16px; font-size: 12px; color: var(--ink-400); }

@media (max-width: 900px) {
  .login-shell { grid-template-columns: 1fr; max-width: 440px; gap: 32px; }
  .login-intro { text-align: center; }
  .login-intro h2 { font-size: 22px; margin: 18px 0 10px; }
  .login-intro p { font-size: 13px; }
  .intro-features { justify-content: center; }
}
@media (max-width: 480px) {
  .login-page { padding: 24px 12px; }
  .login-box { padding: 28px 20px; border-radius: var(--r-md); }
}
</style>
