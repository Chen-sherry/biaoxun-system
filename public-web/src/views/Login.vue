<template>
  <div class="login-page">
    <div class="login-grid" aria-hidden="true"></div>
    <div class="login-glow" aria-hidden="true"></div>
    <div class="login-decor" aria-hidden="true">
      <span class="decor-ring r1"></span>
      <span class="decor-ring r2"></span>
      <span class="decor-dot d1"></span>
      <span class="decor-dot d2"></span>
    </div>

    <div class="login-card">
      <div class="card-top-glow" aria-hidden="true"></div>
      <div class="brand"><BrandLogo :size="48" :text-size="24" /></div>
      <p class="sub">会员登录 · 享受智能检索、订阅推送、专属会员权益</p>
      <el-tabs v-model="tab" centered>
        <el-tab-pane label="登录" name="login">
          <el-form :model="loginForm" :rules="rules" ref="loginRef" @submit.prevent="onLogin">
            <el-form-item prop="username">
              <el-input v-model="loginForm.username" placeholder="用户名" size="large" :prefix-icon="User" />
            </el-form-item>
            <el-form-item prop="password">
              <el-input v-model="loginForm.password" type="password" placeholder="密码" size="large" show-password :prefix-icon="Lock" />
            </el-form-item>
            <el-button type="primary" size="large" :loading="loading" class="submit" @click="onLogin">登 录</el-button>
            <div class="tips">管理员：admin / admin123</div>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="注册" name="register">
          <el-form :model="regForm" :rules="rules" ref="regRef" @submit.prevent="onRegister">
            <el-form-item prop="username"><el-input v-model="regForm.username" placeholder="用户名" size="large" :prefix-icon="User" /></el-form-item>
            <el-form-item prop="password"><el-input v-model="regForm.password" type="password" placeholder="密码（≥6位）" size="large" show-password :prefix-icon="Lock" /></el-form-item>
            <el-form-item><el-input v-model="regForm.nickname" placeholder="昵称（可选）" size="large" /></el-form-item>
            <el-form-item><el-input v-model="regForm.company" placeholder="公司（可选）" size="large" /></el-form-item>
            <el-button type="primary" size="large" :loading="loading" class="submit" @click="onRegister">注 册</el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import BrandLogo from '@/components/BrandLogo.vue'
import { login, register } from '@/api'

const router = useRouter()
const tab = ref<'login' | 'register'>('login')
const loading = ref(false)
const loginRef = ref<FormInstance>()
const regRef = ref<FormInstance>()
const loginForm = reactive({ username: '', password: '' })
const regForm = reactive({ username: '', password: '', nickname: '', company: '' })
const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, min: 6, message: '密码至少 6 位', trigger: 'blur' }],
}

async function onLogin() {
  await loginRef.value?.validate()
  loading.value = true
  try {
    const data: any = await login(loginForm)
    localStorage.setItem('token', data.access_token)
    ElMessage.success('登录成功')
    router.push('/')
  } finally { loading.value = false }
}
async function onRegister() {
  await regRef.value?.validate()
  loading.value = true
  try {
    await register(regForm)
    ElMessage.success('注册成功，请登录')
    tab.value = 'login'
    loginForm.username = regForm.username
    regForm.username = ''; regForm.password = ''
  } finally { loading.value = false }
}
</script>

<style scoped>
.login-page {
  position: relative; min-height: calc(100vh - 66px); display: flex;
  align-items: center; justify-content: center; padding: 40px 24px; overflow: hidden;
  background: linear-gradient(125deg, var(--brand-950) 0%, var(--brand-850) 50%, #0c2947 100%);
}
.login-grid {
  position: absolute; inset: 0; pointer-events: none; opacity: 0.8;
  background-image: url('@/assets/brand/bg-grid.svg'); background-size: 48px 48px;
  mask-image: radial-gradient(ellipse at 50% 50%, #000 20%, transparent 80%);
}
.login-glow {
  position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%);
  width: 900px; height: 760px; pointer-events: none;
  background-image: url('@/assets/brand/bg-glow.svg'); background-size: cover; opacity: 0.75;
}
.login-decor { position: absolute; inset: 0; pointer-events: none; }
.decor-ring { position: absolute; border-radius: 50%; border: 1px solid rgba(56, 189, 248, 0.14); }
.decor-ring.r1 { width: 420px; height: 420px; top: -120px; right: -80px; }
.decor-ring.r2 { width: 300px; height: 300px; bottom: -100px; left: -60px; border-color: rgba(129, 140, 248, 0.16); }
.decor-dot { position: absolute; width: 6px; height: 6px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 12px var(--accent-glow); }
.decor-dot.d1 { top: 22%; left: 18%; }
.decor-dot.d2 { bottom: 24%; right: 20%; background: var(--accent-violet); }

.login-card {
  position: relative; z-index: 2; width: 440px; max-width: 100%;
  background: rgba(255, 255, 255, 0.97);
  border: 1px solid rgba(56, 189, 248, 0.22);
  border-radius: var(--r-lg); padding: 38px 40px 32px;
  box-shadow: 0 28px 70px rgba(2, 8, 20, 0.5), 0 0 0 1px rgba(255,255,255,0.4) inset;
  animation: fade-up 0.5s var(--ease) both;
}
.card-top-glow {
  position: absolute; top: 0; left: 50%; transform: translateX(-50%);
  width: 160px; height: 3px; border-radius: 0 0 4px 4px;
  background: linear-gradient(90deg, transparent, var(--accent), transparent);
  box-shadow: 0 0 16px var(--accent-glow);
}
.brand { display: flex; justify-content: center; margin-bottom: 10px; }
.sub { text-align: center; color: var(--ink-500); margin: 0 0 22px; font-size: 13px; }
.submit { width: 100%; height: 46px; font-weight: 600; letter-spacing: 4px; }
.tips { text-align: center; margin-top: 14px; font-size: 12px; color: var(--ink-400); }

/* ===== 移动端（≤480px）===== */
@media (max-width: 480px) {
  .login-page { padding: 20px 12px; }
  .login-card { padding: 28px 18px; border-radius: var(--r-md); }
}
</style>
