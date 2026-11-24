/**
 * PM2 配置 —— 标讯系统前端（admin-web + public-web）
 *
 * 使用前先构建前端（一次性）：
 *   cd admin-web && npm run build
 *   cd public-web && npm run build
 *
 * 启动：
 *   pm2 start ecosystem.config.js
 *
 * 也可以用根目录的 start_all.bat 一键 build + 启动全部。
 */

const path = require('path')

module.exports = {
  apps: [
    // ===== admin-web（管理后台，Vite Preview 端口 5173）=====
    {
      name: 'bid-admin-web',
      script: path.join(__dirname, 'admin-web', 'node_modules', 'vite', 'bin', 'vite.js'),
      args: 'preview --host 0.0.0.0 --port 5173',
      cwd: path.join(__dirname, 'admin-web'),
      interpreter: 'node',
      exec_mode: 'fork',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '300M',
      error_file: path.join(__dirname, 'admin-web', 'logs', 'pm2_error.log'),
      out_file: path.join(__dirname, 'admin-web', 'logs', 'pm2_out.log'),
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
    },

    // ===== public-web（门户，Vite Preview 端口 5174）=====
    {
      name: 'bid-public-web',
      script: path.join(__dirname, 'public-web', 'node_modules', 'vite', 'bin', 'vite.js'),
      args: 'preview --host 0.0.0.0 --port 5174',
      cwd: path.join(__dirname, 'public-web'),
      interpreter: 'node',
      exec_mode: 'fork',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '300M',
      error_file: path.join(__dirname, 'public-web', 'logs', 'pm2_error.log'),
      out_file: path.join(__dirname, 'public-web', 'logs', 'pm2_out.log'),
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
    },
  ],
}
