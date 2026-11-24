<template>
  <div class="login">
    <van-nav-bar title="登录" left-arrow @click-left="$router.back()" fixed placeholder />
    <van-form @submit="onSubmit">
      <van-cell-group inset>
        <van-field v-model="form.username" name="username" label="账号" placeholder="请输入账号" />
        <van-field v-model="form.password" type="password" name="password" label="密码" placeholder="请输入密码" />
      </van-cell-group>
      <div style="margin: 24px 16px 16px">
        <van-button round block type="primary" native-type="submit">登录</van-button>
      </div>
    </van-form>
  </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import request, { TOKEN_KEY } from '@/utils/request'

const form = reactive({ username: '', password: '' })
const router = useRouter()

async function onSubmit() {
  try {
    const data: any = await request.post('/api/v1/auth/login', form)
    localStorage.setItem(TOKEN_KEY, data.access_token)
    showToast('登录成功')
    router.replace('/home')
  } catch {}
}
</script>
