import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    base: env.VITE_BASE || '/admin/',  // 服务器部署用 VITE_BASE=/biaoxun-admin/
    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src'),
      },
    },
    plugins: [
      vue(),
      AutoImport({
        imports: ['vue', 'vue-router', 'pinia'],
        resolvers: [ElementPlusResolver()],
        dts: 'src/auto-imports.d.ts',
      }),
      Components({
        resolvers: [ElementPlusResolver()],
        dts: 'src/components.d.ts',
      }),
    ],
    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: {
        // 前端 vite base='/admin/'，浏览器请求是 /admin/api/v1/...
        // 需要把 /admin/api 转发到后端 /api
        '/admin/api': {
          target: env.VITE_API_BASE || 'http://127.0.0.1:8000',
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/admin/, ''),  // /admin/api/v1/... → /api/v1/...
        },
        // 同时也兼容直接 /api 的情况（比如 h5-web 不走 admin base）
        '/api': {
          target: env.VITE_API_BASE || 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
      },
    },
  }
})
