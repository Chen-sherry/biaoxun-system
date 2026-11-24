-- =====================================================
-- 05-notice_type_expand.sql
-- 公告类型字典扩充
-- 背景：NOTICE_TYPE_RULES 匹配到「成交公告 / 废标 / 竞争性磋商」等名称后，
--       若 dict_notice_type 中不存在同名记录，infer_notice_type_id 返回 NULL，
--       导致 98.8% 的标讯拿不到公告类型标签。
-- 说明：本脚本幂等，可重复执行；本地与服务器各执行一次。
-- =====================================================

INSERT INTO dict_notice_type (code, name, category, sort, status)
SELECT 'cj', '成交公告', '政府采购', 9, 1
WHERE NOT EXISTS (SELECT 1 FROM dict_notice_type WHERE code = 'cj');

INSERT INTO dict_notice_type (code, name, category, sort, status)
SELECT 'zz', '终止公告', '政府采购', 10, 1
WHERE NOT EXISTS (SELECT 1 FROM dict_notice_type WHERE code = 'zz');

INSERT INTO dict_notice_type (code, name, category, sort, status)
SELECT 'zy', '资格预审公告', '政府采购', 11, 1
WHERE NOT EXISTS (SELECT 1 FROM dict_notice_type WHERE code = 'zy');

INSERT INTO dict_notice_type (code, name, category, sort, status)
SELECT 'yq', '邀请招标', '政府采购', 12, 1
WHERE NOT EXISTS (SELECT 1 FROM dict_notice_type WHERE code = 'yq');

INSERT INTO dict_notice_type (code, name, category, sort, status)
SELECT 'dy', '答疑澄清', '政府采购', 13, 1
WHERE NOT EXISTS (SELECT 1 FROM dict_notice_type WHERE code = 'dy');

INSERT INTO dict_notice_type (code, name, category, sort, status)
SELECT 'cq', '采购意向', '政府采购', 14, 1
WHERE NOT EXISTS (SELECT 1 FROM dict_notice_type WHERE code = 'cq');

INSERT INTO dict_notice_type (code, name, category, sort, status)
SELECT 'ht', '合同公告', '政府采购', 15, 1
WHERE NOT EXISTS (SELECT 1 FROM dict_notice_type WHERE code = 'ht');

INSERT INTO dict_notice_type (code, name, category, sort, status)
SELECT 'cg', '采购公告', '政府采购', 16, 1
WHERE NOT EXISTS (SELECT 1 FROM dict_notice_type WHERE code = 'cg');

INSERT INTO dict_notice_type (code, name, category, sort, status)
SELECT 'qt', '其他', '政府采购', 17, 1
WHERE NOT EXISTS (SELECT 1 FROM dict_notice_type WHERE code = 'qt');
