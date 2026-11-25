-- ============================================================
-- 推送模板「默认文案快照」：配合后台「应用为默认模板」按钮
-- （用户点「应用为默认模板」→ 当前文案写入 default_* 列；
--   「恢复默认文案」→ 从 default_* 读回，而不是前端硬编码常量）
-- 执行：mysql -uroot -p bid_info < 10-push_default_snapshot.sql
-- ============================================================

USE bid_info;

ALTER TABLE push_template
    ADD COLUMN default_title   VARCHAR(255) NULL COMMENT '默认标题快照（应用为默认时写入）' AFTER content,
    ADD COLUMN default_content TEXT         NULL COMMENT '默认正文快照（应用为默认时写入）' AFTER default_title;
