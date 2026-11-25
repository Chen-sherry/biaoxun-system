-- ============================================================
-- 推送模块补充：执行时间可配置 + 自定义定时推送
-- 对应 docs/06 设计文档 M5（执行时间调整）与「添加定时推送」需求
-- 执行：mysql -uroot -p bid_info < 09-push_schedule.sql
-- ============================================================

USE bid_info;

ALTER TABLE push_template
    ADD COLUMN name         VARCHAR(64)  NOT NULL DEFAULT '' COMMENT '显示名' AFTER code,
    ADD COLUMN kind         VARCHAR(16)  NOT NULL DEFAULT 'fixed'
        COMMENT 'fixed 内置定时任务 / custom 自定义定时推送' AFTER name,
    ADD COLUMN schedule_time VARCHAR(5)  NOT NULL DEFAULT ''
        COMMENT '每日执行时间 HH:MM（内置默认 08:00/09:00/02:00）' AFTER kind,
    ADD COLUMN frequency    VARCHAR(8)   NOT NULL DEFAULT 'daily'
        COMMENT 'daily 每天 / weekly 每周（custom 用）' AFTER schedule_time,
    ADD COLUMN weekday      TINYINT      NULL COMMENT 'weekly 时 0=周一..6=周日' AFTER frequency;

-- 内置三模板：显示名 + 默认执行时间（后台可改，改完无需重启）
UPDATE push_template SET name = '每日推送',   schedule_time = '08:00' WHERE code = 'daily_summary';
UPDATE push_template SET name = '到期预警',   schedule_time = '09:00' WHERE code = 'expiring_alert';
UPDATE push_template SET name = '归档通知',   schedule_time = '02:00' WHERE code = 'archive_notice';

-- 自定义模板的种子（kind=custom，由后台「新增定时推送」创建，此处仅示例不插入）
