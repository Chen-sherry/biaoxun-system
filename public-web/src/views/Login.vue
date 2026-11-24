<template>
  <div class="login-page">
    <div class="login-card">
      <h1>🏛️ 标讯速递</h1>
      <p class="sub">会员登录 · 享受智能检索、订阅推送、专属会员权益</p>
      <el-tabs v-model="tab" centered>
        <el-tab-pane label="登录" name="login">
          <el-form :model="loginForm" :rules="rules" ref="loginRef" @submit.prevent="onLogin">
            <el-form-item prop="username">
              <el-input v-model="loginForm.username" placeholder="用户名" size="large" />
            </el-form-item>
            <el-form-item prop="password">
              <el-input v-model="loginForm.password" type="password" placeholder="密码" size="large" show-password />
            </el-form-item>
            <el-button type="primary" size="large" :loading="loading" style="width:100%" @click="onLogin">登 录</el-button>
            <div class="tips">管理员：admin / admin123</div>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="注册" name="register">
          <el-form :model="regForm" :rules="rules" ref="regRef" @submit.prevent="onRegister">
            <el-form-item prop="username"><el-input v-model="regForm.username" placeholder="用户名" size="large" /></el-form-item>
            <el-form-item prop="password"><el-input v-model="regForm.password" type="password" placeholder="密码（≥6位）" size="large" show-password /></el-form-item>
            <el-form-item><el-input v-model="regForm.nickname" placeholder="昵称（可选）" size="large" /></el-form-item>
            <el-form-item><el-input v-model="regForm.company" placeholder="公司（可选）" size="large" /></el-form-item>
            <el-button type="primary" size="large" :loading="loading" style="width:100%" @click="onRegister">注 册</el-button>
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
.login-page { min-height: calc(100vh - 64px); display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 24px; }
.login-card { background: #fff; border-radius: 16px; padding: 40px; width: 420px; box-shadow: 0 20px 60px rgba(0,0,0,0.15); }
.login-card h1 { text-align: center; margin: 0 0 8px; font-size: 22px; }
.sub { text-align: center; color: #909399; margin: 0 0 24px; font-size: 13px; }
.tips { text-align: center; margin-top: 12px; font-size: 12px; color: #c0c4cc; }

/* ===== 移动端（≤480px）===== */
@media (max-width: 480px) {
  .login-page { padding: 12px; }
  .login-card { width: 100%; max-width: 420px; padding: 28px 18px; border-radius: 12px; }
  .login-card h1 { font-size: 19px; }
}
</style>
