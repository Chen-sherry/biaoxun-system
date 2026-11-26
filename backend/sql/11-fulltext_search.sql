-- ============================================================
-- 11-fulltext_search.sql
-- 标讯全文检索索引（MySQL FULLTEXT + ngram 中文分词）
-- 适用：MySQL 8.0+（服务器）/ 本地开发 MySQL 9.x
-- 说明：
--   1. ngram_token_size 保持默认 2，不可修改（已建索引会失效）
--   2. content_text 为 MEDIUMTEXT（约 155MB），大表 ALTER 可能耗时数分钟，
--      请在业务低峰执行；磁盘紧张时可只建 (title) 单列索引（见文件末尾备选）
--   3. 执行方式：mysql -uroot -p bid_info < 11-fulltext_search.sql
-- ============================================================

ALTER TABLE `bid_info`
    ADD FULLTEXT KEY `ft_bid_title_content` (`title`, `content_text`)
    WITH PARSER ngram;

-- ---------- 备选：磁盘不足时只建标题索引（先注释上方语句再执行） ----------
-- ALTER TABLE `bid_info`
--     ADD FULLTEXT KEY `ft_bid_title` (`title`)
--     WITH PARSER ngram;
