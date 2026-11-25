-- ============================================================
-- 推送模块：push_template 建表 + 种子、push_record 扩列、push 权限码
-- 对应设计文档：docs/06-推送模块设计-关系书与功能书.md
-- 执行：mysql -uroot -p bid_info < 08-push_module.sql
-- ============================================================

USE bid_info;

-- ============================================================
-- 1. push_template 推送模板表
-- ============================================================
CREATE TABLE IF NOT EXISTS push_template (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    code        VARCHAR(32)  NOT NULL UNIQUE COMMENT '模板编码 daily_summary/expiring_alert/archive_notice',
    title       VARCHAR(255) NOT NULL COMMENT '消息标题（企微 markdown ## 标题）',
    content     TEXT         NOT NULL COMMENT '模板正文，{var} 占位符',
    variables   VARCHAR(500) NOT NULL DEFAULT '' COMMENT '可用变量清单（逗号分隔）',
    enabled     TINYINT      NOT NULL DEFAULT 1 COMMENT '1 启用 0 停用（停用到点跳过）',
    updated_by  INT          NULL COMMENT '最后修改后台用户 id',
    updated_at  DATETIME     NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
    created_at  DATETIME     NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_tpl_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='推送模板';

-- ============================================================
-- 2. push_record 扩列
-- ============================================================
ALTER TABLE push_record
    ADD COLUMN push_type   VARCHAR(16) NOT NULL DEFAULT 'scheduled'
        COMMENT 'scheduled定时/manual临时/test测试/subscribe订阅/ai生成' AFTER subscribe_id,
    ADD COLUMN template_id INT NULL COMMENT '关联 push_template.id' AFTER push_type,
    ADD COLUMN operator_id INT NULL COMMENT '操作人（定时任务为 NULL）' AFTER template_id,
    ADD COLUMN preview     TINYINT NOT NULL DEFAULT 0 COMMENT '1=预览记录' AFTER operator_id,
    MODIFY user_id INT NULL COMMENT '接收用户（临时/测试推送可为空）';

-- ============================================================
-- 3. 三个默认模板种子（文案来自现有代码，改模板无需改代码）
-- ============================================================
INSERT INTO push_template (code, title, content, variables, enabled, updated_by) VALUES
(
  'daily_summary',
  '📢 {date} 新增标讯汇总',
  '**新增数量**：{count} 条\n\n**Top 关键词**：\n{top_keywords}\n{top_regions}',
  'date,count,top_keywords,top_regions,bid_list',
  1, NULL
),
(
  'expiring_alert',
  '⏰ {date} 截止时间临近预警',
  '**{count} 条标讯在 24 小时内截止报名**\n\n**样例**：\n{bid_list}',
  'date,count,bid_list',
  1, NULL
),
(
  'archive_notice',
  '📦 {date} 归档汇总',
  '**昨日归档标讯**：{count} 条\n\n{bid_list}',
  'date,count,bid_list',
  1, NULL
)
ON DUPLICATE KEY UPDATE code = code;  -- 已存在则不覆盖（保留后台已改的模板）

-- ============================================================
-- 4. push 权限码（菜单 + 按钮），挂 admin / ops 角色
-- ============================================================
INSERT INTO sys_permission (parent_id, name, code, type, path, icon, sort) VALUES
(NULL, '推送管理', 'push', 1, '/push', 'Promotion', 35);

SET @push_menu = LAST_INSERT_ID();

INSERT INTO sys_permission (parent_id, name, code, type, path, sort) VALUES
(@push_menu, '定时推送', 'push:scheduled', 1, '/push/scheduled', 1),
(@push_menu, '临时推送', 'push:manual',     1, '/push/manual',    2),
(@push_menu, '订阅用户', 'push:subscribers',1, '/push/subscribers',3),
(@push_menu, '推送记录', 'push:records',    1, '/push/records',   4),
(@push_menu, '模板编辑按钮', 'push:template:edit', 2, NULL, 1),
(@push_menu, '临时发送按钮', 'push:manual:send',   2, NULL, 2),
(@push_menu, '订阅查看按钮', 'push:subscribe:view',2, NULL, 3),
(@push_menu, '订阅推送按钮', 'push:subscribe:push',2, NULL, 4);

-- 挂到 admin / ops 角色（按角色 code 关联，角色 id 自动查）
INSERT INTO sys_role_permission (role_id, permission_id)
SELECT r.id, p.id FROM sys_role r
JOIN sys_permission p ON p.code LIKE 'push%'
WHERE r.code IN ('admin', 'ops')
  AND NOT EXISTS (
    SELECT 1 FROM sys_role_permission rp
    WHERE rp.role_id = r.id AND rp.permission_id = p.id
  );
