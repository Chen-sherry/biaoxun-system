import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [vue()],
    resolve: {
      alias: { '@': resolve(__dirname, 'src') },
    },
    base: env.VITE_BASE || '/',  // 本地 '/'，服务器部署用 VITE_BASE=/biaoxun/
    server: {
      host: '0.0.0.0',
      port: 5174,  // 用 5174 避开 admin-web 的 5173
      proxy: {
        '/api': {
          target: env.VITE_API_BASE || 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
      },
    },
  }
})
