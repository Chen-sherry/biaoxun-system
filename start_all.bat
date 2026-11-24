@echo off
REM =================================================================
REM 标讯系统 —— 一键启动脚本（PM2 版本）
REM   1. 检查 pm2 / node / python 是否可用
REM   2. 构建 admin-web 和 public-web 前端（生产包）
REM   3. PM2 启动后端 FastAPI + Celery + 两个前端 vite preview
REM
REM 如果不想启动 Celery（worker + beat），编辑 backend\ecosystem.config.js
REM 把那两个 app 对象注释掉即可。
REM =================================================================

chcp 65001 >nul
cd /d %~dp0

echo.
echo ========================================================
echo   标讯系统 —— 一键启动（PM2）
echo   工作目录: %cd%
echo ========================================================
echo.

REM ---------- 环境检查 ----------
where node >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Node.js，请先安装 Node.js ^(https://nodejs.org^)
    pause & exit /b 1
)

where pm2 >nul 2>&1
if errorlevel 1 (
    echo [信息] 未找到 pm2，正在全局安装...
    call npm install -g pm2
    if errorlevel 1 (
        echo [错误] pm2 安装失败，请检查网络或手动执行: npm install -g pm2
        pause & exit /b 1
    )
)

where python >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 并加入 PATH
    pause & exit /b 1
)

echo [OK] Node:   & node -v
echo [OK] npm:    & npm -v
echo [OK] pm2:    & pm2 -v
echo [OK] Python: & python --version
echo.

REM ---------- 构建前端 ----------
echo ---------- 构建 admin-web ----------
cd /d "%~dp0admin-web"
if not exist node_modules (
    echo [信息] admin-web 无 node_modules，先执行 npm install ...
    call npm install
    if errorlevel 1 (
        echo [警告] admin-web npm install 失败，跳过构建
        goto :build_public
    )
)
call npm run build
if errorlevel 1 (
    echo [警告] admin-web 构建失败，但继续启动其他服务
) else (
    echo [OK] admin-web 构建完成
)

:build_public
echo.
echo ---------- 构建 public-web ----------
cd /d "%~dp0public-web"
if not exist node_modules (
    echo [信息] public-web 无 node_modules，先执行 npm install ...
    call npm install
    if errorlevel 1 (
        echo [警告] public-web npm install 失败，跳过构建
        goto :pm2_start
    )
)
call npm run build
if errorlevel 1 (
    echo [警告] public-web 构建失败，但继续启动其他服务
) else (
    echo [OK] public-web 构建完成
)

REM ---------- PM2 启动 ----------
:pm2_start
echo.
echo ---------- PM2 启动全部服务 ----------
cd /d "%~dp0"

echo [信息] 启动后端（FastAPI + Celery）...
call pm2 start backend\ecosystem.config.js
if errorlevel 1 (
    echo [警告] 后端启动异常，请检查 backend\ecosystem.config.js
)

echo [信息] 启动前端（admin-web + public-web）...
call pm2 start ecosystem.config.js
if errorlevel 1 (
    echo [警告] 前端启动异常，请检查 ecosystem.config.js
)

echo.
echo ---------- PM2 进程状态 ----------
call pm2 status

echo.
echo ========================================================
echo   启动完成！
echo   后端 API:   http://127.0.0.1:8000
echo   admin-web:  http://127.0.0.1:5173
echo   public-web: http://127.0.0.1:5174
echo
echo   常用命令:
echo     pm2 logs            查看实时日志
echo     pm2 logs bid-api    只看 API 日志
echo     pm2 reload all      平滑重启全部
echo     pm2 delete all      停止全部
echo     pm2 monit           监控面板
echo ========================================================
echo.
pause
