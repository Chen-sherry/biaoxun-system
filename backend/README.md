# 标讯系统 - 后端 API

基于 **FastAPI + SQLAlchemy + Celery + Redis + MySQL** 的标讯信息管理系统后端。

## 目录结构

```
backend/
├── app/
│   ├── api/            # 路由层（v1 已暴露的接口）
│   │   ├── deps.py     # 依赖注入（get_current_user 等）
│   │   └── v1/         # v1 API：auth / bid / source / subscribe / member ...
│   ├── models/         # SQLAlchemy ORM 模型
│   ├── schemas/        # Pydantic 入参/出参 Schema
│   ├── tasks/          # Celery 定时任务
│   ├── utils/          # 工具（security / response / logger）
│   ├── config.py       # Settings（读取 .env）
│   ├── database.py     # 数据库引擎 / Session
│   ├── redis_client.py # Redis 连接
│   └── main.py         # FastAPI 入口
├── .env.example        # 环境变量模板
├── requirements.txt
└── run_dev.bat         # Windows 开发启动脚本
```

## 快速开始

```bash
# 1. 创建虚拟环境
python -m venv venv
venv\Scripts\activate    # Windows
# source venv/bin/activate  # Linux / Mac

# 2. 安装依赖
pip install -r requirements.txt

# 3. 复制环境变量模板
copy .env.example .env     # Windows
# cp .env.example .env     # Linux / Mac

# 4. 确认 / 修改 .env
#    MySQL: root / 12345 / 127.0.0.1:3306 / bid_info（已预置）
#    Redis: 127.0.0.1:6379（默认无密码）
#    OSS / SMTP 生产部署时再填

# 5. 初始化数据库（已执行过可跳过）
#    mysql -uroot -p12345 -e "CREATE DATABASE IF NOT EXISTS bid_info DEFAULT CHARSET utf8mb4;"
#    Get-Content -Raw sql/init_data.sql | mysql -uroot -p12345 bid_info
#    # 可选：导入 25年4-6月 Excel 种子数据（8239 行，14 个关键词 sheet 合并）
#    python scripts/import_seed_excel.py

# 6. 启动（开发模式，自动热重载）
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# 或直接执行 run_dev.bat

# 7. 启动 Celery Worker（另一个终端）
celery -A app.tasks.celery_app worker -l info -P solo

# 8. 启动 Celery Beat（定时任务调度）
celery -A app.tasks.celery_app beat -l info
```

## 接口文档

启动后访问：

- Swagger UI: http://localhost:8000/docs
- ReDoc:     http://localhost:8000/redoc

## 已完成的核心模块

| 模块         | 状态 | 说明                                |
| ------------ | ---- | ----------------------------------- |
| 认证（JWT）   | ✅    | 登录 / 注册 / 获取当前用户           |
| 标讯 CRUD     | ✅    | 列表 / 详情 / 新增 / 编辑 / 审核 / 下架 |
| 采集源管理    | ✅    | 爬虫源 / 接口源配置                  |
| 订阅管理      | ✅    | 关键词 + 地区 + 推送方式             |
| 会员套餐/订单 | ✅    | 浏览套餐 / 创建订单 / 模拟支付       |
| 字典数据      | ✅    | 地区 / 行业 / 公告类型               |
| 爬虫任务      | 🚧    | 骨架 + Celery 调度，具体采集逻辑待实现 |
| 推送任务      | 🚧    | 骨架 + Celery 调度，SMTP 发送待实现    |
| 统计报表      | ❌    | 待实现                               |

## 设计原则

- **路由 - 服务 - 数据** 三层分离，API 层只做参数校验 & 鉴权，业务逻辑下沉到 `app/services/`
- **RBAC** 权限：`sys_user` ↔ `sys_role` ↔ `sys_permission`
- **去重指纹**：`bid_info.dedup_key = sha1(title + region_code + publish_time_text)`
- **统一响应**：`{"code": 0, "msg": "ok", "data": {...}}`
