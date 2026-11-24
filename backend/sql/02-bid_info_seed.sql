-- ============================================================
-- 合并种子表 bid_info_seed
-- 来源：25年4-6月关键词招中标数据8.8.xlsx（14 个 sheet 合并）
-- 每张 sheet 是一个关键词类别：培训/人才/党性/红色/团建/新员工/场地/拓展/赋能营销/战训/团队建设/趣味运动会/团队拓展/考试
-- 每行原始数据 31 列；合表后新增 source_keyword 字段标记来源 sheet
-- 唯一键：(source_keyword, news_id) —— 防止重复导入
-- ============================================================

DROP TABLE IF EXISTS `bid_info_seed`;

CREATE TABLE `bid_info_seed` (
    `id`                         INT UNSIGNED    NOT NULL AUTO_INCREMENT COMMENT '主键',
    -- ===== Excel 原始 31 列 =====
    `news_title`                 VARCHAR(512)    DEFAULT NULL COMMENT '新闻标题',
    `project_code`               VARCHAR(128)    DEFAULT NULL COMMENT '项目编号',
    `purchase_unit`              VARCHAR(255)    DEFAULT NULL COMMENT '采购单位（招标人）',
    `winner_unit`                VARCHAR(255)    DEFAULT NULL COMMENT '中标单位',
    `tender_amount`              DECIMAL(18,2)   DEFAULT NULL COMMENT '招标金额',
    `win_amount`                 DECIMAL(18,2)   DEFAULT NULL COMMENT '中标金额',
    `business_structure`         VARCHAR(255)    DEFAULT NULL COMMENT '业务结构',
    `tender_time`                DATETIME        DEFAULT NULL COMMENT '招标时间',
    `win_time`                   DATETIME        DEFAULT NULL COMMENT '中标时间',
    `agency_unit`                VARCHAR(255)    DEFAULT NULL COMMENT '代理单位',
    `original_link`              VARCHAR(512)    DEFAULT NULL COMMENT '原文链接',
    `region_full`                VARCHAR(128)    DEFAULT NULL COMMENT '完整地区',
    `province`                   VARCHAR(64)     DEFAULT NULL COMMENT '省',
    `city`                       VARCHAR(64)     DEFAULT NULL COMMENT '市',
    `procure_type`               VARCHAR(32)     DEFAULT NULL COMMENT '招采类型（招采/中标/竞争性谈判...）',
    `notice_type`                VARCHAR(32)     DEFAULT NULL COMMENT '公告类型（计划/成交/中标/废标...）',
    `major`                      VARCHAR(255)    DEFAULT NULL COMMENT '专业（多个逗号分隔）',
    `region_id`                  VARCHAR(16)     DEFAULT NULL COMMENT '地区ID',
    `news_id`                    VARCHAR(32)     DEFAULT NULL COMMENT '新闻ID（业务主键）',
    `create_time`                DATETIME        DEFAULT NULL COMMENT '录入/创建时间',
    `deadline`                   DATETIME        DEFAULT NULL COMMENT '截止时间',
    `expected_purchase_time`     DATETIME        DEFAULT NULL COMMENT '预计采购时间',
    `intention_link`             VARCHAR(512)    DEFAULT NULL COMMENT '意项链接',
    `long_id`                    VARCHAR(32)     DEFAULT NULL COMMENT '长ID',
    `market_perception_link`     VARCHAR(512)    DEFAULT NULL COMMENT '市场感知链接',
    `duplicate`                  VARCHAR(16)     DEFAULT NULL COMMENT '重复标记',
    `customer_group`             VARCHAR(64)     DEFAULT NULL COMMENT '客群（人社/政务/...）',
    `operator_customer_group`    VARCHAR(64)     DEFAULT NULL COMMENT '运营商客群',
    `winner_unit_type`           VARCHAR(64)     DEFAULT NULL COMMENT '中标单位类型',
    `city_level`                 VARCHAR(16)     DEFAULT NULL COMMENT '市属标记',
    `stage`                      VARCHAR(32)     DEFAULT NULL COMMENT '阶段（采购意向/成交/...）',
    -- ===== 合表后新增 =====
    `source_keyword`             VARCHAR(64)     NOT NULL COMMENT '来源关键词/sheet 名',
    `raw_row_hash`               CHAR(40)        DEFAULT NULL COMMENT 'sha1(news_title+source_keyword+news_id) 用于去重',
    -- ===== 系统字段 =====
    `created_at`                 DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`                 DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_seed_source_newsid` (`source_keyword`, `news_id`),
    KEY `idx_seed_keyword` (`source_keyword`),
    KEY `idx_seed_win_time` (`win_time`),
    KEY `idx_seed_tender_time` (`tender_time`),
    KEY `idx_seed_city` (`city`),
    KEY `idx_seed_procure_type` (`procure_type`),
    KEY `idx_seed_notice_type` (`notice_type`),
    KEY `idx_seed_major` (`major`(100)),
    KEY `idx_seed_purchase_unit` (`purchase_unit`(100)),
    KEY `idx_seed_winner_unit` (`winner_unit`(100)),
    KEY `idx_seed_stage` (`stage`),
    KEY `idx_seed_amount` (`tender_amount`, `win_amount`)
) ENGINE=InnoDB COMMENT='Excel 种子数据合表（14 个关键词 sheet 合并）';
