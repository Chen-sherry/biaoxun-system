/**
 * PM2 配置 —— 标讯系统后端（FastAPI + Celery）
 * 启动方式：
 *   cd backend
 *   pm2 start ecosystem.config.js
 *
 * 常用命令：
 *   pm2 status          # 查看状态
 *   pm2 logs            # 查看全部日志
 *   pm2 logs bid-api    # 只看 API 日志
 *   pm2 reload all      # 平滑重启
 *   pm2 delete all      # 停止并删除所有进程
 *
 * Windows 注意：
 *   Celery 不支持 Windows 默认 prefork pool，worker 必须显式加 --pool=solo
 *   若要用多并发，先 pip install eventlet 再用 --pool=eventlet --concurrency=4
 */

module.exports = {
  apps: [
    // ===== FastAPI（必选）=====
    {
      name: 'bid-api',
      script: 'python',
      args: '-m uvicorn app.main:app --host 0.0.0.0 --port 8000',
      cwd: __dirname,
      interpreter: 'none',        // 直接用系统 PATH 里的 python
      exec_mode: 'fork',
      instances: 1,
      autorestart: true,
      watch: false,               // 生产环境关闭 reload
      max_memory_restart: '500M',
      env: {
        APP_ENV: 'prod',
        DB_PORT: process.env.DB_PORT || 3306,   // 便携 MySQL 端口覆盖（如本机测试 3307）
        PYTHONUNBUFFERED: '1',
      },
      error_file: './logs/pm2_api_error.log',
      out_file: './logs/pm2_api_out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
    },

    // ===== Celery Worker（可选，需要 Redis 先启动）=====
    // 如果不需要 Celery，把下面整个对象注释掉即可。
    {
      name: 'bid-celery-worker',
      script: 'python',
      args: '-m celery -A app.tasks.celery_app worker --pool=solo -l info',
      //                若用 eventlet: -m celery -A app.tasks.celery_app worker --pool=eventlet --concurrency=4 -l info
      cwd: __dirname,
      interpreter: 'none',
      exec_mode: 'fork',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '400M',
      env: {
        DB_PORT: process.env.DB_PORT || 3306,   // 便携 MySQL 端口覆盖（如本机测试 3307）
        PYTHONUNBUFFERED: '1',
      },
      error_file: './logs/pm2_worker_error.log',
      out_file: './logs/pm2_worker_out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
    },

    // ===== Celery Beat（可选，同 Celery Worker 二选一或都开）=====
    {
      name: 'bid-celery-beat',
      script: 'python',
      args: '-m celery -A app.tasks.celery_app beat -l info',
      cwd: __dirname,
      interpreter: 'none',
      exec_mode: 'fork',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '200M',
      env: {
        DB_PORT: process.env.DB_PORT || 3306,   // 便携 MySQL 端口覆盖（如本机测试 3307）
        PYTHONUNBUFFERED: '1',
      },
      error_file: './logs/pm2_beat_error.log',
      out_file: './logs/pm2_beat_out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
    },
  ],
}
