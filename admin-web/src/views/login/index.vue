<template>
  <div class="login-page">
    <div class="login-box">
      <div class="title">
        <el-icon size="28"><Document /></el-icon>
        <h2>标讯管理后台</h2>
        <p>欢迎回来，请先登录</p>
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
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
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
  } finally {
    loading.value = false
  }
}
</script>

<style lang="scss" scoped>
.login-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}
.login-box {
  width: 420px;
  background: #fff;
  border-radius: 8px;
  padding: 40px 36px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
}
.title {
  text-align: center;
  margin-bottom: 30px;
  h2 { margin: 8px 0 4px; color: #303133; }
  p { color: #909399; font-size: 13px; margin: 0; }
}
.submit { width: 100%; }
.tips { text-align: center; margin-top: 16px; font-size: 12px; color: #c0c4cc; }
</style>
