-- ============================================================
-- 全量权限节点 + 角色权限分配
-- 三级结构：菜单(type=1) → 按钮(type=2) → 接口(type=3)
-- 角色：admin / editor / auditor / ops
-- ============================================================

USE bid_info;

-- 清旧权限节点和关联（init_data.sql 里有少量节点，这里覆盖重配）
DELETE FROM sys_role_permission;
DELETE FROM sys_permission;

SET @menu = 1, @btn = 2, @api = 3;

-- ============================================================
-- 一级菜单
-- ============================================================
INSERT INTO sys_permission (id, parent_id, name, code, type, path, icon, sort) VALUES
(1,  NULL, '控制台',   'dashboard',     1, '/dashboard',  'Odometer',   10),
(2,  NULL, '标讯管理', 'bid',           1, '/bid',        'Document',   20),
(3,  NULL, '采集中心', 'crawl',         1, '/crawl',      'Connection', 30),
(4,  NULL, '订阅中心', 'subscribe',     1, '/subscribe',  'Notification',35),
(5,  NULL, '会员管理', 'member',        1, '/member',     'Medal',      40),
(6,  NULL, '用户中心', 'user',          1, '/user',       'User',       50),
(7,  NULL, '系统设置', 'setting',       1, '/setting',    'Setting',    60),
(8,  NULL, '统计报表', 'stats',         1, '/stats',      'DataAnalysis',70);

-- ============================================================
-- 二级菜单（子路由）
-- ============================================================
INSERT INTO sys_permission (id, parent_id, name, code, type, path, sort) VALUES
-- 标讯管理
(101, 2, '标讯列表',    'bid:list',         1, '/bid/list',        1),
(102, 2, '待审核',      'bid:pending',      1, '/bid/pending',     2),
(103, 2, '已归档',      'bid:archived',     1, '/bid/archived',    3),
(104, 2, '附件管理',    'bid:attachment',   1, '/bid/attachment',  4),

-- 采集中心
(201, 3, '采集源管理',  'crawl:source',     1, '/crawl/source',    1),
(202, 3, '采集日志',    'crawl:log',        1, '/crawl/log',       2),

-- 订阅中心
(301, 4, '我的订阅',    'subscribe:mine',   1, '/subscribe/mine',  1),
(302, 4, '推送日志',    'subscribe:log',    1, '/subscribe/log',   2),

-- 会员管理
(401, 5, '套餐管理',    'member:package',   1, '/member/package',  1),
(402, 5, '订单管理',    'member:order',     1, '/member/order',    2),
(403, 5, '会员用户',    'member:user',      1, '/member/user',     3),

-- 用户中心
(501, 6, '用户列表',    'user:list',        1, '/user/list',       1),
(502, 6, '角色管理',    'user:role',        1, '/user/role',       2),

-- 系统设置
(601, 7, '公告类型字典','setting:notice-type',1,'/setting/notice-type',1),
(602, 7, '地区字典',    'setting:region',   1, '/setting/region',   2),
(603, 7, '行业字典',    'setting:industry', 1, '/setting/industry', 3),
(604, 7, '系统日志',    'setting:log',      1, '/setting/log',      4),
(605, 7, '合规声明',    'setting:compliance',1,'/setting/compliance',5);

-- ============================================================
-- 按钮权限 type=2
-- ============================================================
INSERT INTO sys_permission (id, parent_id, name, code, type, sort) VALUES
-- 标讯列表按钮
(1001, 101, '标讯新增',   'bid:info:add',        2, 1),
(1002, 101, '标讯编辑',   'bid:info:edit',       2, 2),
(1003, 101, '标讯删除',   'bid:info:delete',     2, 3),
(1004, 101, '标讯置顶',   'bid:info:top',        2, 4),
(1005, 101, '标讯下架',   'bid:info:offline',    2, 5),
-- 待审核按钮
(1010, 102, '标讯审核',   'bid:info:audit',      2, 1),
(1011, 102, '标讯驳回',   'bid:info:reject',     2, 2),
-- 附件
(1020, 104, '附件上传',   'bid:attachment:upload', 2, 1),
(1021, 104, '附件删除',   'bid:attachment:delete', 2, 2),
(1022, 104, '附件下载',   'bid:attachment:download',2, 3),
-- 采集源
(2001, 201, '采集源新增', 'crawl:source:add',    2, 1),
(2002, 201, '采集源编辑', 'crawl:source:edit',   2, 2),
(2003, 201, '采集源删除', 'crawl:source:delete', 2, 3),
(2004, 201, '立即采集',   'crawl:source:run',    2, 4),
(2005, 201, '全部采集',   'crawl:source:run-all',2, 5),
-- 会员套餐
(4001, 401, '套餐新增',   'member:package:add',  2, 1),
(4002, 401, '套餐编辑',   'member:package:edit', 2, 2),
(4003, 401, '套餐删除',   'member:package:delete',2, 3),
-- 用户管理
(5001, 501, '用户新增',   'user:admin:add',      2, 1),
(5002, 501, '用户编辑',   'user:admin:edit',     2, 2),
(5003, 501, '用户禁用',   'user:admin:disable',  2, 3),
(5004, 501, '密码重置',   'user:admin:reset-pwd',2, 4),
-- 角色
(5101, 502, '角色权限分配','user:role:assign',    2, 1);

-- ============================================================
-- 接口权限 type=3（后端 API 路径，后续可做细粒度拦截）
-- ============================================================
INSERT INTO sys_permission (id, parent_id, name, code, type, path) VALUES
(9001, 101, '标讯新增接口', 'api:bid:create',    3, 'POST /api/v1/bids'),
(9002, 101, '标讯编辑接口', 'api:bid:update',    3, 'PUT /api/v1/bids'),
(9003, 101, '标讯删除接口', 'api:bid:delete',    3, 'DELETE /api/v1/bids/{id}'),
(9004, 101, '标讯下架接口', 'api:bid:offline',   3, 'POST /api/v1/bids/{id}/offline'),
(9005, 102, '标讯审核接口', 'api:bid:audit',     3, 'POST /api/v1/bids/{id}/audit'),
(9006, 201, '采集源 CRUD',  'api:source:crud',   3, '/api/v1/sources/*'),
(9007, 201, '触发采集接口', 'api:crawl:run',     3, 'POST /api/v1/crawl/*'),
(9008, 501, '后台用户 CRUD','api:admin-user:crud',3,'/api/v1/admin/users/*'),
(9009, 502, '角色管理接口', 'api:role:crud',     3, '/api/v1/admin/roles/*');

-- ============================================================
-- 角色权限分配
-- admin: 全部权限
-- editor: 标讯管理 + 附件 + 采集源（不能审核）
-- auditor: 待审核 + 审核通过/驳回 + 查看列表
-- ops: 采集中心 + 会员管理 + 订阅推送 + 系统设置字典
-- ============================================================

-- admin → 全部
INSERT INTO sys_role_permission (role_id, permission_id)
SELECT r.id, p.id FROM sys_role r JOIN sys_permission p
WHERE r.code = 'admin';

-- editor → 标讯相关（id 101~104, 1001~1005, 1020~1022）+ 采集源可编辑不可 run-all（2001~2003）
INSERT INTO sys_role_permission (role_id, permission_id)
SELECT r.id, p.id FROM sys_role r JOIN sys_permission p
WHERE r.code = 'editor'
  AND (
    p.code LIKE 'bid:%' AND p.code NOT LIKE 'bid:pending' AND p.code NOT LIKE 'bid:info:audit'
    OR p.code LIKE 'bid:attachment:%'
    OR p.code IN ('bid:list', 'bid:archived', 'bid')
  );

-- auditor → 标讯列表 + 待审核 + 审核按钮
INSERT INTO sys_role_permission (role_id, permission_id)
SELECT r.id, p.id FROM sys_role r JOIN sys_permission p
WHERE r.code = 'auditor'
  AND (
    p.code IN ('bid', 'bid:list', 'bid:pending')
    OR p.code IN ('bid:info:audit', 'bid:info:reject', 'bid:info:edit')
  );

-- ops → 采集中心 + 订阅 + 会员 + 系统字典
INSERT INTO sys_role_permission (role_id, permission_id)
SELECT r.id, p.id FROM sys_role r JOIN sys_permission p
WHERE r.code = 'ops'
  AND (
    p.code LIKE 'crawl:%'
    OR p.code LIKE 'subscribe:%'
    OR p.code LIKE 'member:%'
    OR p.code LIKE 'setting:notice-type'
    OR p.code LIKE 'setting:region'
    OR p.code LIKE 'setting:industry'
  );

-- 验证
SELECT '权限节点总数' AS label, COUNT(*) AS n FROM sys_permission
UNION ALL
SELECT CONCAT('admin 权限数'), COUNT(*) FROM sys_role_permission rp JOIN sys_role r ON rp.role_id=r.id WHERE r.code='admin'
UNION ALL
SELECT CONCAT('editor 权限数'), COUNT(*) FROM sys_role_permission rp JOIN sys_role r ON rp.role_id=r.id WHERE r.code='editor'
UNION ALL
SELECT CONCAT('auditor 权限数'), COUNT(*) FROM sys_role_permission rp JOIN sys_role r ON rp.role_id=r.id WHERE r.code='auditor'
UNION ALL
SELECT CONCAT('ops 权限数'), COUNT(*) FROM sys_role_permission rp JOIN sys_role r ON rp.role_id=r.id WHERE r.code='ops';
