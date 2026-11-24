# 标讯系统 - 接口 API 设计文档

> 版本：v0.1 · 基础路径：`/api/v1` · 协议：HTTPS + JSON · 2026-11-20

---

## 1. 约定

### 1.1 统一响应体

```jsonc
// 成功
{ "code": 0, "msg": "ok", "data": { ... } }

// 业务失败（如参数校验失败、业务逻辑不允许）
{ "code": 40001, "msg": "关键词不能为空", "data": null }

// 未登录
{ "code": 401, "msg": "未登录", "data": null }

// 权限不足
{ "code": 403, "msg": "权限不足", "data": null }

// 服务器内部错误
{ "code": -999, "msg": "服务器内部错误", "data": null }
```

### 1.2 分页参数

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| page | int | 1 | 页码，从 1 起 |
| page_size | int | 20 | 每页大小，最大 100 |

分页响应 `data` 结构：

```json
{
  "total": 1234,
  "page": 1,
  "page_size": 20,
  "items": [ ... ]
}
```

### 1.3 认证

- Header：`Authorization: Bearer <JWT>`
- 令牌由 `/api/v1/auth/login` 返回
- 未登录访问受保护资源返回 401

### 1.4 HTTP 方法语义

| 方法 | 用途 |
| --- | --- |
| GET | 查询 |
| POST | 创建 |
| PUT | 全量更新（已有 ID） |
| DELETE | 删除 |
| POST /{id}/action | 非 CRUD 动作（audit / offline / pay） |

---

## 2. 认证 Auth

### 2.1 登录

```
POST /api/v1/auth/login
Body: { "username": "admin", "password": "admin123" }
Resp: { "access_token": "...", "token_type": "bearer", "expire_minutes": 1440 }
```

### 2.2 注册

```
POST /api/v1/auth/register
Body: { "username": "u001", "password": "P@ssw0rd", "email": "a@b.com", "company": "XX 公司" }
Resp: { "id": 101, "username": "u001", "nickname": "u001" }
```

### 2.3 当前用户

```
GET /api/v1/auth/me
Auth: ✅
Resp: { "id": 1, "username": "admin", "nickname": "超级管理员", "company": "标讯系统", "roles": ["admin"] }
```

---

## 3. 标讯 Bids

### 3.1 列表（前台）

```
GET /api/v1/bids?keyword=&region_code=&industry_id=&notice_type_id=&date_from=&date_to=&status=1&page=1&page_size=20
Auth: 可选（会员登录可看更多权益）
Resp: ApiResponse<PageData<BidListItem>>
```

`BidListItem` 字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int | |
| title | string | 标题 |
| notice_type | string | 公告类型名称 |
| region_name | string | 地区名 |
| publish_time | datetime | |
| deadline | datetime | |
| tenderee | string | 招标人 |
| budget | string | 预算 |
| status | int | |

### 3.2 详情

```
GET /api/v1/bids/{bid_id}
Resp: BidDetail (含 content HTML、attachments)
```

> 访问详情时后端 `view_count + 1`。

### 3.3 新增（后台）

```
POST /api/v1/bids
Auth: admin / editor
Body:
{
  "title": "...",
  "project_code": "ZC-2026-001",
  "tenderee": "XX 单位",
  "agency": "YY 代理",
  "notice_type_id": 1,
  "industry_id": 3,
  "region_code": "110000",
  "publish_time": "2026-11-20T10:00:00",
  "deadline": "2026-12-10T17:00:00",
  "budget": "480.00 万元",
  "content": "<p>HTML 正文</p>",
  "source_url": "http://...",
  "source_id": null
}
```

> 手动录入的标讯默认 `status=1`（直接发布）；爬虫采集的默认 `status=0`。

### 3.4 编辑

```
PUT /api/v1/bids
Auth: admin / editor
Body: 同上 + id 字段
```

### 3.5 审核通过

```
POST /api/v1/bids/{bid_id}/audit
Auth: admin / auditor
```

### 3.6 下架

```
POST /api/v1/bids/{bid_id}/offline
Auth: admin / editor
```

### 3.7 置顶

```
POST /api/v1/bids/{bid_id}/top?is_top=true
Auth: admin
```

---

## 4. 采集源 Sources

### 4.1 列表

```
GET /api/v1/sources
Auth: admin / ops
Resp: 全量 source 配置
```

### 4.2 新增 / 更新 / 删除

```
POST   /api/v1/sources        创建
PUT    /api/v1/sources/{id}   更新
DELETE /api/v1/sources/{id}   删除
```

Source 关键字段：

| 字段 | 说明 |
| --- | --- |
| source_type | 1 爬虫 / 2 API / 3 手动 / 4 Excel |
| list_url_rule | 列表页模板，可用 `{page}` 占位 |
| field_rules | JSON，如 `{"title": "//h1/text()", "publish_time": "//span[@class='time']/text()"}` |
| interval_minutes | 调度间隔 |
| status | 启停 |

---

## 5. 爬虫任务 Crawl

```
POST /api/v1/crawl/run/{source_id}   # 手动触发单个源
POST /api/v1/crawl/run-all           # 手动触发全部启用源
GET  /api/v1/crawl/tasks             # 任务执行历史
```

---

## 6. 订阅 Subscribes

### 6.1 我的订阅列表

```
GET /api/v1/subscribes
Auth: ✅
```

### 6.2 新增订阅

```
POST /api/v1/subscribes
Auth: ✅
Body: {
  "keyword": "智慧城市",
  "region_code": "110000",
  "notice_type_id": 1,
  "push_email": true,
  "frequency": "daily"
}
```

> 后端校验会员订阅数不超过 `member_package.max_subscribe`。

### 6.3 更新 / 删除

```
PUT    /api/v1/subscribes/{id}
DELETE /api/v1/subscribes/{id}
```

---

## 7. 会员套餐 Member Packages

### 7.1 列表（公开，前台购买页）

```
GET /api/v1/member-packages
```

### 7.2 后台管理

```
POST /api/v1/member-packages   # 新增
PUT  /api/v1/member-packages/{id}  # 更新
```

---

## 8. 会员订单 Member Orders

### 8.1 我的订单

```
GET /api/v1/member-orders
Auth: ✅
```

### 8.2 创建订单

```
POST /api/v1/member-orders?package_id=3
Auth: ✅
Resp: { "order_no": "BID20261120...", "amount": 699.00 }
```

### 8.3 模拟支付（开发用）

```
POST /api/v1/member-orders/{order_no}/pay?pay_type=manual
```

### 8.4 支付回调（生产接入微信 / 支付宝时）

```
POST /api/v1/member-orders/callback/wechat     # 微信
POST /api/v1/member-orders/callback/alipay     # 支付宝
```

> 签名校验 → 更新订单状态 → 计算会员有效期。

---

## 9. 字典 Dicts（公开）

```
GET /api/v1/dicts/regions?parent_id=0         # 省
GET /api/v1/dicts/regions?parent_id=110000    # 某市下属区

GET /api/v1/dicts/industries?parent_id=0

GET /api/v1/dicts/notice-types?category=工程
```

---

## 10. 后台用户 Admin Users

```
GET    /api/v1/admin/users?keyword=&page=&page_size=   # 列表
POST   /api/v1/admin/users                             # 新增
PUT    /api/v1/admin/users/{id}/status?status=0/1      # 启用禁用
GET    /api/v1/admin/users/roles                        # 角色列表
POST   /api/v1/admin/users/roles                        # 新增角色
PUT    /api/v1/admin/users/roles/{id}/permissions       # 分配权限
```

> 权限：仅 admin 角色可访问。

---

## 11. 统计报表 Statistics（预留）

```
GET /api/v1/stats/overview          # 概览卡片
GET /api/v1/stats/bid-trend?days=7  # 标讯发布趋势
GET /api/v1/stats/notice-type-dist   # 公告类型分布
GET /api/v1/stats/member-revenue     # 会员收入
```

---

## 12. 错误码汇总

| code | 含义 |
| --- | --- |
| 0 | 成功 |
| 400 | 参数错误 |
| 401 | 未登录 / 令牌过期 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 40001 | 业务校验失败（自定义） |
| 40002 | 订阅数超过上限 |
| 40003 | 会员专属接口但用户非会员 |
| -999 | 服务器内部错误（需查日志） |

---

## 13. 接口文档在线地址

FastAPI 自动生成：

- Swagger UI: http://localhost:8000/docs
- ReDoc:     http://localhost:8000/redoc
- OpenAPI:   http://localhost:8000/openapi.json

## 14. 速率限制（建议）

| 接口类型 | 限流 |
| --- | --- |
| 登录 | 5 次 / 分钟 / IP |
| 标讯列表（公开） | 100 次 / 分钟 / IP |
| 详情 | 60 次 / 分钟 / IP |
| 后台写操作 | 30 次 / 分钟 / 账号 |
| 爬虫手动触发 | 3 次 / 分钟 / 账号 |

> 通过 FastAPI 中间件 + Redis 令牌桶实现。

## 15. 版本策略

- `/api/v1` 稳定版本
- 破坏性变更时升级 v2；v1 至少保留 6 个月
- 非破坏性变更（新增字段 / 新增接口）兼容追加

---

*接口实现见 `backend/app/api/v1/*.py`，入参 Schema 见 `backend/app/schemas/*.py`。*

---

## v0.2 变更记录（2026-11-20 用户评审拍板）

### bid_info 字段扩展导致的 API 响应变化

`/api/v1/bids` 列表和详情接口的 `BidListItem` / `BidDetail` 响应新增以下字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| winner_unit | string | 中标单位 |
| win_amount | decimal | 中标金额 |
| procure_type | string | 招采类型 |
| winner_publish_time | datetime | 中标/成交时间 |
| customer_group | string | 客群 |
| winner_unit_type | string | 中标单位类型 |

> 后端 Pydantic Schema（`backend/app/schemas/bid.py`）需同步扩展。

### 新增接口（AI 匹配 + 到期预警）

#### AI 智能匹配（接入 DeepSeek LLM）

```
GET /api/v1/ai/match?user_id=1&bids=最新50条&limit=10
Auth: 需要登录
Resp: ApiResponse[List[matched_bid_with_score]]
```

> 实现路径：`services/deepseek_match.py` 调 DeepSeek API，把企业订阅关键词 + 最新标讯送过去，让 LLM 做语义打分，返回 Top-N。

#### 到期预警每日汇总推送（企业微信群机器人）

```
POST /api/v1/stats/expiring/daily  # 手动触发（测试用）
# 定时触发：Celery Beat 每日 09:00
```

触发后：查询 `bid_info.deadline` 在 24h 内且状态=1 的标讯 → 聚合 → 调用 `wecom_push.send_expiring_soon_bids()` 推企业微信群。

### 推送通道切换

企业微信群机器人已经真实接入，**所有"推送"类事件**（订阅 / 预警 / 每日汇总）默认先走企业微信群机器人；SMTP 邮件先占位。切换实现：`app/services/push_channel.py` 的 `CombinedChannel`。

### 爬虫真实数据源

- **ggzy.gov.cn**：公共资源交易平台，采集路由在 `api/v1/crawl.py` + Celery 任务 `crawl_single_source(source_id)`
- **ccgp.gov.cn**：中国政府采购网，同上

种子数据源 source_id=4（bid_source 表里 seed_excel_25h1），转正脚本已关联。
