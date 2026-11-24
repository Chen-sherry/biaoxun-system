-- =====================================================
-- 角色体系调整：合并旧的 editor/auditor/ops → admin_role
-- 新增 bidder；member 补权限；guest 保持
-- admin (id=1) 保持超级用户
-- =====================================================

USE `bid_info`;

-- 1) editor → admin_role（普通管理员，合并 editor + auditor + ops 的权限）
UPDATE sys_role SET code='admin_role', name='管理员', description='负责标讯编辑/审核/运营管理' WHERE id=2;

-- 2) 把 auditor(6) + ops(18) 的权限全部合并给 admin_role
INSERT IGNORE INTO sys_role_permission (role_id, permission_id)
SELECT 2, permission_id FROM sys_role_permission WHERE role_id IN (3, 4);

-- 3) 删除旧的 auditor / ops 角色及其权限
DELETE FROM sys_role_permission WHERE role_id IN (3, 4);
DELETE FROM sys_role WHERE id IN (3, 4);

-- 4) 新增 bidder（投标用户）
INSERT INTO sys_role (code, name, description, created_at) VALUES
  ('bidder', '投标用户', '企业投标方，可订阅标讯、使用AI匹配、收藏', NOW());

-- 5) member 补基础权限（看标讯列表/详情/AI匹配/订阅）
INSERT IGNORE INTO sys_role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM sys_role r, sys_permission p
WHERE r.code IN ('member', 'bidder')
  AND p.code IN (
    'bid:list', 'bid:detail', 'bid:search',
    'subscribe:list', 'subscribe:create', 'subscribe:update', 'subscribe:delete',
    'ai:match', 'dict:list',
    'member:package:list', 'member:order:create'
  );

-- 6) 给 bidder 额外加：可看投标相关高级功能
INSERT IGNORE INTO sys_role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM sys_role r, sys_permission p
WHERE r.code = 'bidder'
  AND p.code IN ('bid:detail:full', 'bid:export');

-- 7) 给 member 加：可创建会员订单
-- (已在上面包含)

-- 8) 重新统计一下各角色权限数
SELECT r.code, r.name, COUNT(rp.permission_id) AS perm_count
FROM sys_role r LEFT JOIN sys_role_permission rp ON r.id=rp.role_id
GROUP BY r.id, r.code, r.name ORDER BY perm_count DESC;
