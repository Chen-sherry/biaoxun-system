# Redis Windows 一键安装脚本
# 下载 Redis 7.x 官方二进制包（Microsoft 维护版本）→ 解压 → 注册 Windows 服务
# 执行：powershell -ExecutionPolicy Bypass -File install_redis_windows.ps1
#       或直接 PowerShell 里执行，按提示输入

param(
    [string]$InstallDir = "C:\Redis",          # 安装目录
    [int]$Port = 6379,                          # 端口
    [string]$Password = "",                     # 密码（留空=不设）
    [ValidateSet("7.2.5", "7.4.1")]
    [string]$Version = "7.2.5"                 # Redis 版本
)

$ErrorActionPreference = "Stop"

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  Redis $Version Windows 一键安装" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# 1. 检查管理员
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[错误] 请以管理员身份运行 PowerShell（右键→以管理员身份运行）" -ForegroundColor Red
    exit 1
}

# 2. 下载
$zipUrl = "https://github.com/tporadowski/redis/releases/download/v$Version/Redis-x64-$Version.zip"
$zipPath = "$env:TEMP\redis-$Version.zip"

Write-Host "[下载] $zipUrl" -ForegroundColor Yellow
try {
    Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing
} catch {
    Write-Host "[错误] 下载失败：$_" -ForegroundColor Red
    Write-Host "        手动下载地址：$zipUrl" -ForegroundColor Yellow
    Write-Host "        下载后解压到 $InstallDir 然后手动执行：redis-server.exe --service-install redis.windows.conf" -ForegroundColor Yellow
    exit 1
}

# 3. 解压
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

Write-Host "[解压] → $InstallDir" -ForegroundColor Yellow
Expand-Archive -Path $zipPath -DestinationPath $InstallDir -Force
Remove-Item $zipPath -Force

# 4. 生成 redis.windows.conf
$confPath = "$InstallDir\redis.windows.conf"
Write-Host "[配置] 生成 $confPath" -ForegroundColor Yellow

$confContent = @"
bind 127.0.0.1
port $Port
protected-mode yes
tcp-backlog 511
timeout 0
tcp-keepalive 300
daemonize no
supervised no
pidfile $InstallDir\redis.pid
loglevel notice
logfile "$InstallDir\redis.log"
databases 16
always-show-logo no
set-proc-title yes
proc-title-template "{title} | listening on {bind}:{port}"
save 900 1
save 300 10
save 60 10000
stop-writes-on-bgsave-error yes
rdbcompression yes
rdbchecksum yes
dbfilename dump.rdb
dir "$InstallDir"
replica-serve-stale-data yes
replica-read-only yes
repl-diskless-sync no
repl-diskless-sync-delay 5
repl-disable-tcp-nodelay no
replica-priority 100
lazyfree-lazy-eviction no
lazyfree-lazy-expire no
lazyfree-lazy-server-del no
replica-lazy-flush no
appendonly yes
appendfilename "appendonly.aof"
appendfsync everysec
no-appendfsync-on-rewrite no
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
aof-load-truncated yes
aof-use-rdb-preamble yes
lua-time-limit 5000
slowlog-log-slower-than 10000
slowlog-max-len 128
latency-monitor-threshold 0
notify-keyspace-events ""
hash-max-listpack-entries 512
hash-max-listpack-value 64
list-max-listpack-size -2
list-compress-depth 0
set-max-intset-entries 512
zset-max-listpack-entries 128
zset-max-listpack-value 64
hll-sparse-max-bytes 3000
stream-node-max-bytes 4096
stream-node-max-entries 100
activerehashing yes
client-output-buffer-limit normal 0 0 0
client-output-buffer-limit replica 256mb 64mb 60
client-output-buffer-limit pubsub 32mb 8mb 60
hz 10
dynamic-hz yes
aof-rewrite-incremental-fsync yes
rdb-save-incremental-fsync yes
jemalloc-bg-thread yes
"@

if ($Password) {
    $confContent += "`nrequirepass $Password"
}

Set-Content -Path $confPath -Value $confContent -Encoding UTF8

# 5. 注册 Windows 服务
Write-Host "[注册] 安装 Redis 服务" -ForegroundColor Yellow
Push-Location $InstallDir
try {
    .\redis-server.exe --service-install redis.windows.conf --service-name RedisService --loglevel notice
    .\redis-server.exe --service-start --service-name RedisService
    Write-Host "[完成] Redis 服务已启动" -ForegroundColor Green
} catch {
    Write-Host "[错误] 服务注册失败：$_" -ForegroundColor Red
    Write-Host "        手动启动：cd $InstallDir && .\redis-server.exe redis.windows.conf" -ForegroundColor Yellow
}
Pop-Location

# 6. 验证
Write-Host "[验证] 尝试连接..." -ForegroundColor Yellow
& "$InstallDir\redis-cli.exe" -p $Port ping 2>&1 | Out-Host

Write-Host ""
Write-Host "==============================================" -ForegroundColor Green
Write-Host "  ✅ Redis 安装完成" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Green
Write-Host "安装目录: $InstallDir"
Write-Host "端口:     $Port"
Write-Host "密码:     $(if ($Password) { $Password } else { '(未设置)' })"
Write-Host "启动命令: $InstallDir\redis-server.exe $InstallDir\redis.windows.conf"
Write-Host "停止服务: sc stop RedisService"
Write-Host "卸载服务: cd $InstallDir; .\redis-server.exe --service-uninstall --service-name RedisService"
Write-Host "==============================================" -ForegroundColor Green
