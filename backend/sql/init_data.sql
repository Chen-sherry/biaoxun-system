-- ============================================================
-- 标讯系统 - 数据库初始化脚本
-- 数据库版本：MySQL 8.0+
-- 字符集：utf8mb4
-- 执行方式：mysql -uroot -p -e "source init_data.sql" 或 Navicat 直接运行
-- ============================================================

CREATE DATABASE IF NOT EXISTS `bid_info`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE `bid_info`;

SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================
-- 1. 用户、角色、权限 (RBAC)
-- ============================================================

DROP TABLE IF EXISTS `sys_role_permission`;
DROP TABLE IF EXISTS `sys_user_role`;
DROP TABLE IF EXISTS `sys_permission`;
DROP TABLE IF EXISTS `sys_role`;
DROP TABLE IF EXISTS `sys_user`;

CREATE TABLE `sys_user` (
    `id`             INT UNSIGNED    NOT NULL AUTO_INCREMENT COMMENT '主键',
    `username`       VARCHAR(64)     NOT NULL                 COMMENT '登录账号',
    `password_hash`  VARCHAR(255)    NOT NULL                 COMMENT 'bcrypt 哈希密码',
    `nickname`       VARCHAR(64)     DEFAULT NULL             COMMENT '昵称',
    `real_name`      VARCHAR(64)     DEFAULT NULL             COMMENT '真实姓名',
    `phone`          VARCHAR(20)     DEFAULT NULL             COMMENT '手机号',
    `email`          VARCHAR(128)    DEFAULT NULL             COMMENT '邮箱',
    `avatar`         VARCHAR(255)    DEFAULT NULL             COMMENT '头像 URL',
    `company`        VARCHAR(128)    DEFAULT NULL             COMMENT '所属企业',
    `is_admin`       TINYINT(1)      NOT NULL DEFAULT 0       COMMENT '1 超级管理员 0 否',
    `status`         TINYINT(1)      NOT NULL DEFAULT 1       COMMENT '1 启用 0 禁用',
    `last_login_at`  DATETIME        DEFAULT NULL             COMMENT '最后登录时间',
    `remark`         TEXT            DEFAULT NULL             COMMENT '备注',
    `created_at`     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_username` (`username`),
    KEY `idx_phone` (`phone`),
    KEY `idx_email` (`email`)
) ENGINE=InnoDB COMMENT='系统用户表';

CREATE TABLE `sys_role` (
    `id`          INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    `name`        VARCHAR(64)     NOT NULL                 COMMENT '角色名称',
    `code`        VARCHAR(64)     NOT NULL                 COMMENT '角色编码',
    `description` VARCHAR(255)    DEFAULT NULL,
    `status`      TINYINT(1)      NOT NULL DEFAULT 1,
    `created_at`  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_code` (`code`),
    UNIQUE KEY `uk_name` (`name`)
) ENGINE=InnoDB COMMENT='角色表';

CREATE TABLE `sys_permission` (
    `id`         INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    `parent_id`  INT UNSIGNED    DEFAULT NULL,
    `name`       VARCHAR(64)     NOT NULL                 COMMENT '权限名称',
    `code`       VARCHAR(128)    NOT NULL                 COMMENT '权限编码',
    `type`       TINYINT(1)      NOT NULL DEFAULT 1       COMMENT '1 菜单 2 按钮 3 接口',
    `path`       VARCHAR(255)    DEFAULT NULL             COMMENT '前端路由 / 接口路径',
    `icon`       VARCHAR(64)     DEFAULT NULL,
    `sort`       INT             NOT NULL DEFAULT 0,
    `status`     TINYINT(1)      NOT NULL DEFAULT 1,
    `created_at` DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_code` (`code`),
    KEY `idx_parent` (`parent_id`)
) ENGINE=InnoDB COMMENT='权限节点表';

CREATE TABLE `sys_user_role` (
    `id`         INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_id`    INT UNSIGNED NOT NULL,
    `role_id`    INT UNSIGNED NOT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_user_role` (`user_id`, `role_id`),
    KEY `idx_role` (`role_id`)
) ENGINE=InnoDB COMMENT='用户-角色关联';

CREATE TABLE `sys_role_permission` (
    `id`            INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `role_id`       INT UNSIGNED NOT NULL,
    `permission_id` INT UNSIGNED NOT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_role_perm` (`role_id`, `permission_id`)
) ENGINE=InnoDB COMMENT='角色-权限关联';

-- ============================================================
-- 2. 字典表（地区 / 行业 / 公告类型）
-- ============================================================

DROP TABLE IF EXISTS `dict_notice_type`;
DROP TABLE IF EXISTS `dict_industry`;
DROP TABLE IF EXISTS `dict_region`;

CREATE TABLE `dict_region` (
    `id`         INT UNSIGNED   NOT NULL AUTO_INCREMENT,
    `parent_id`  INT UNSIGNED   NOT NULL DEFAULT 0      COMMENT '父级，0 为省级',
    `code`       VARCHAR(16)    NOT NULL                COMMENT '区划代码',
    `name`       VARCHAR(64)    NOT NULL,
    `level`      TINYINT(1)     NOT NULL DEFAULT 1      COMMENT '1 省 2 市 3 区',
    `lng`        DECIMAL(10,7) DEFAULT NULL,
    `lat`        DECIMAL(10,7) DEFAULT NULL,
    `sort`       INT            NOT NULL DEFAULT 0,
    `status`     TINYINT(1)     NOT NULL DEFAULT 1,
    `created_at` DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_code` (`code`),
    KEY `idx_parent` (`parent_id`)
) ENGINE=InnoDB COMMENT='行政区划';

CREATE TABLE `dict_industry` (
    `id`         INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `parent_id`  INT UNSIGNED NOT NULL DEFAULT 0,
    `code`       VARCHAR(32)  NOT NULL,
    `name`       VARCHAR(64)  NOT NULL,
    `sort`       INT          NOT NULL DEFAULT 0,
    `status`     TINYINT(1)   NOT NULL DEFAULT 1,
    `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_code` (`code`)
) ENGINE=InnoDB COMMENT='行业分类';

CREATE TABLE `dict_notice_type` (
    `id`         INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `code`       VARCHAR(32)  NOT NULL                 COMMENT 'notice_code',
    `name`       VARCHAR(64)  NOT NULL,
    `category`   VARCHAR(32)  DEFAULT NULL             COMMENT '大类：工程/货物/服务/政府采购',
    `sort`       INT          NOT NULL DEFAULT 0,
    `status`     TINYINT(1)   NOT NULL DEFAULT 1,
    `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_code` (`code`)
) ENGINE=InnoDB COMMENT='公告类型';

-- ============================================================
-- 3. 标讯主表 & 附件 & 采集源
-- ============================================================

DROP TABLE IF EXISTS `bid_attachment`;
DROP TABLE IF EXISTS `bid_info`;
DROP TABLE IF EXISTS `bid_source`;

CREATE TABLE `bid_info` (
    `id`              INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    `title`           VARCHAR(512)    NOT NULL                 COMMENT '公告标题',
    `project_code`    VARCHAR(128)    DEFAULT NULL             COMMENT '项目编号',
    `tenderee`        VARCHAR(255)    DEFAULT NULL             COMMENT '招标人/采购人',
    `agency`          VARCHAR(255)    DEFAULT NULL             COMMENT '招标代理机构',
    `notice_type_id`  INT UNSIGNED    DEFAULT NULL             COMMENT '公告类型',
    `industry_id`     INT UNSIGNED    DEFAULT NULL             COMMENT '行业分类',
    `region_code`     VARCHAR(16)     DEFAULT NULL             COMMENT '地区代码',
    `publish_time`    DATETIME        DEFAULT NULL             COMMENT '公告原文发布时间',
    `deadline`        DATETIME        DEFAULT NULL             COMMENT '报名/投标截止时间',
    `budget`          VARCHAR(64)     DEFAULT NULL             COMMENT '预算金额（保留币种字符串）',
    `content`         MEDIUMTEXT      DEFAULT NULL             COMMENT '公告正文 HTML',
    `content_text`    MEDIUMTEXT      DEFAULT NULL             COMMENT '正文纯文本（用于全文检索）',
    `source_id`       INT UNSIGNED    DEFAULT NULL             COMMENT '采集源',
    `source_url`      VARCHAR(512)    DEFAULT NULL             COMMENT '原文地址',
    `dedup_key`       VARCHAR(128)    DEFAULT NULL             COMMENT '去重指纹 sha1(title+region+pub_time)',
    `view_count`      INT             NOT NULL DEFAULT 0,
    `status`          TINYINT(1)      NOT NULL DEFAULT 1       COMMENT '0 待审核 1 已发布 2 已下架 3 已归档',
    `is_top`          TINYINT(1)      NOT NULL DEFAULT 0,
    `winner_unit`     VARCHAR(255)    DEFAULT NULL             COMMENT '中标单位',
    `win_amount`      DECIMAL(18,2)   DEFAULT NULL             COMMENT '中标金额',
    `procure_type`    VARCHAR(32)     DEFAULT NULL             COMMENT '招采类型（中标/招采/询价等）',
    `winner_publish_time` DATETIME    DEFAULT NULL             COMMENT '中标/成交时间',
    `customer_group`  VARCHAR(64)     DEFAULT NULL             COMMENT '客群（政务/国企/民企）',
    `winner_unit_type` VARCHAR(64)    DEFAULT NULL             COMMENT '中标单位类型',
    `remark`          TEXT            DEFAULT NULL,
    `created_at`      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_bid_region_pub` (`region_code`, `publish_time`),
    KEY `idx_bid_deadline` (`deadline`),
    KEY `idx_bid_notice_type` (`notice_type_id`),
    KEY `idx_bid_industry` (`industry_id`),
    KEY `idx_bid_status` (`status`),
    KEY `idx_bid_winner_publish` (`winner_publish_time`),
    KEY `idx_bid_customer_group` (`customer_group`),
    KEY `idx_project_code` (`project_code`),
    KEY `idx_dedup` (`dedup_key`)
) ENGINE=InnoDB COMMENT='标讯主表';

CREATE TABLE `bid_attachment` (
    `id`               INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `bid_id`           INT UNSIGNED NOT NULL,
    `file_name`        VARCHAR(255) NOT NULL,
    `oss_key`          VARCHAR(512) NOT NULL,
    `file_size`        INT          DEFAULT NULL,
    `mime_type`        VARCHAR(128) DEFAULT NULL,
    `is_require_member` TINYINT(1)  NOT NULL DEFAULT 1      COMMENT '1 会员才能下载',
    `download_count`   INT          NOT NULL DEFAULT 0,
    `created_at`       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_bid` (`bid_id`)
) ENGINE=InnoDB COMMENT='标讯附件表';

CREATE TABLE `bid_source` (
    `id`               INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `name`             VARCHAR(128) NOT NULL,
    `code`             VARCHAR(64)  NOT NULL                COMMENT '唯一编码',
    `source_type`      TINYINT      NOT NULL DEFAULT 1      COMMENT '1 爬虫 2 开放接口 3 手动 4 Excel',
    `base_url`         VARCHAR(512) DEFAULT NULL,
    `list_url_rule`    TEXT         DEFAULT NULL,
    `detail_url_rule`  TEXT         DEFAULT NULL,
    `list_selector`    VARCHAR(255) DEFAULT NULL,
    `field_rules`      TEXT         DEFAULT NULL            COMMENT '字段提取规则 JSON',
    `request_headers`  TEXT         DEFAULT NULL            COMMENT '自定义 Header JSON',
    `request_params`   TEXT         DEFAULT NULL,
    `http_method`      VARCHAR(16)  NOT NULL DEFAULT 'GET',
    `interval_minutes` INT          NOT NULL DEFAULT 60,
    `last_crawl_at`    DATETIME     DEFAULT NULL,
    `status`           TINYINT(1)   NOT NULL DEFAULT 1,
    `description`      VARCHAR(255) DEFAULT NULL,
    `created_at`       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_code` (`code`)
) ENGINE=InnoDB COMMENT='采集源配置';

-- ============================================================
-- 4. 订阅
-- ============================================================

DROP TABLE IF EXISTS `bid_subscribe`;

CREATE TABLE `bid_subscribe` (
    `id`            INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_id`       INT UNSIGNED NOT NULL,
    `keyword`       VARCHAR(255) NOT NULL,
    `region_code`   VARCHAR(16)  DEFAULT NULL,
    `industry_id`   INT UNSIGNED DEFAULT NULL,
    `notice_type_id` INT UNSIGNED DEFAULT NULL,
    `push_email`    TINYINT(1)   NOT NULL DEFAULT 1,
    `push_wechat`   TINYINT(1)   NOT NULL DEFAULT 0,
    `frequency`     VARCHAR(16)  NOT NULL DEFAULT 'daily' COMMENT 'daily / hourly / realtime',
    `last_push_at`  DATETIME     DEFAULT NULL,
    `status`        TINYINT(1)   NOT NULL DEFAULT 1,
    `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_user` (`user_id`)
) ENGINE=InnoDB COMMENT='用户订阅';

-- ============================================================
-- 5. 会员套餐 & 订单
-- ============================================================

DROP TABLE IF EXISTS `member_order`;
DROP TABLE IF EXISTS `member_package`;

CREATE TABLE `member_package` (
    `id`              INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `name`            VARCHAR(64)  NOT NULL,
    `code`            VARCHAR(32)  NOT NULL,
    `price`           DECIMAL(10,2) NOT NULL DEFAULT 0,
    `sale_price`      DECIMAL(10,2) NOT NULL DEFAULT 0,
    `duration_days`   INT          NOT NULL DEFAULT 365,
    `level`           INT          NOT NULL DEFAULT 1,
    `max_subscribe`   INT          NOT NULL DEFAULT 20,
    `allow_export`    TINYINT(1)   NOT NULL DEFAULT 1,
    `allow_contact`   TINYINT(1)   NOT NULL DEFAULT 1,
    `description`     VARCHAR(500) DEFAULT NULL,
    `sort`            INT          NOT NULL DEFAULT 0,
    `status`          TINYINT(1)   NOT NULL DEFAULT 1,
    `created_at`      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_code` (`code`)
) ENGINE=InnoDB COMMENT='会员套餐';

CREATE TABLE `member_order` (
    `id`          INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    `order_no`    VARCHAR(64)   NOT NULL                COMMENT '订单号',
    `user_id`     INT UNSIGNED  NOT NULL,
    `package_id`  INT UNSIGNED  NOT NULL,
    `amount`      DECIMAL(10,2) NOT NULL,
    `pay_type`    VARCHAR(16)   DEFAULT NULL            COMMENT 'wechat/alipay/manual',
    `pay_time`    DATETIME      DEFAULT NULL,
    `start_date`  DATETIME      DEFAULT NULL,
    `end_date`    DATETIME      DEFAULT NULL,
    `status`      TINYINT       NOT NULL DEFAULT 0      COMMENT '0 待支付 1 已支付 2 已取消 3 已退款',
    `trade_no`    VARCHAR(128)  DEFAULT NULL,
    `remark`      VARCHAR(255)  DEFAULT NULL,
    `created_at`  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_order_no` (`order_no`),
    KEY `idx_user` (`user_id`)
) ENGINE=InnoDB COMMENT='会员订单';

-- ============================================================
-- 6. 推送日志
-- ============================================================

DROP TABLE IF EXISTS `push_record`;

CREATE TABLE `push_record` (
    `id`           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_id`      INT UNSIGNED    NOT NULL,
    `subscribe_id` INT UNSIGNED    DEFAULT NULL,
    `bid_ids`      VARCHAR(2000)   DEFAULT NULL,
    `channel`      VARCHAR(16)     NOT NULL,
    `recipient`    VARCHAR(255)    NOT NULL,
    `subject`      VARCHAR(255)    DEFAULT NULL,
    `status`       TINYINT(1)      NOT NULL DEFAULT 0   COMMENT '0 成功 1 失败',
    `error_msg`    VARCHAR(500)    DEFAULT NULL,
    `push_time`    DATETIME        NOT NULL,
    PRIMARY KEY (`id`),
    KEY `idx_user` (`user_id`),
    KEY `idx_push_time` (`push_time`)
) ENGINE=InnoDB COMMENT='推送日志';

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- 基础初始化数据
-- ============================================================

-- --- 角色 ---
INSERT INTO `sys_role` (`name`, `code`, `description`) VALUES
    ('超级管理员', 'admin', '拥有系统全部权限'),
    ('内容编辑', 'editor', '负责标讯录入/编辑/下架'),
    ('审核员',    'auditor','负责标讯审核'),
    ('运营员',    'ops',    '负责采集源、订阅、会员等运营管理'),
    ('普通会员',  'member', '前台已注册用户'),
    ('普通访客',  'guest',  '未登录用户');

-- --- 超级管理员账号 ---
-- 密码：admin123  （bcrypt cost=12，已通过 Python bcrypt.hashpw 生成）
INSERT INTO `sys_user` (`username`, `password_hash`, `nickname`, `real_name`, `is_admin`, `status`, `company`) VALUES
    ('admin', '$2b$12$7SuGZTmaC6Gyqvwnn9IK3eVxwqtrthTApFKVVtar39UGiG9S0Hhse', '超级管理员', '系统管理员', 1, 1, '标讯系统');

-- 把 admin 绑定 admin 角色
INSERT INTO `sys_user_role` (`user_id`, `role_id`)
SELECT u.id, r.id FROM `sys_user` u JOIN `sys_role` r ON r.code = 'admin' AND u.username = 'admin';

-- --- 权限节点（菜单 + 常用按钮） ---
INSERT INTO `sys_permission` (`parent_id`, `name`, `code`, `type`, `path`, `icon`, `sort`) VALUES
    (NULL, '控制台',   'dashboard',         1, '/dashboard',       'Odometer', 10),
    (NULL, '标讯管理', 'bid',               1, '/bid',             'Document', 20),
    (NULL, '采集中心', 'crawl',             1, '/crawl',           'Connection', 30),
    (NULL, '用户中心', 'user',              1, '/user',            'User', 40),
    (NULL, '会员管理', 'member',            1, '/member',          'Medal', 50),
    (NULL, '系统设置', 'setting',           1, '/setting',         'Setting', 60),
    -- 标讯子菜单
    (2, '标讯列表',   'bid:list',          1, '/bid/list',        NULL, 21),
    (2, '待审核',     'bid:pending',       1, '/bid/pending',      NULL, 22),
    (2, '已归档',     'bid:archived',      1, '/bid/archived',     NULL, 23),
    -- 按钮权限
    (2, '标讯新增',   'bid:info:add',      2, NULL, NULL, 0),
    (2, '标讯编辑',   'bid:info:edit',     2, NULL, NULL, 0),
    (2, '标讯删除',   'bid:info:delete',   2, NULL, NULL, 0),
    (2, '标讯审核',   'bid:info:audit',    2, NULL, NULL, 0);

-- 给 admin 角色赋予全部权限
INSERT INTO `sys_role_permission` (`role_id`, `permission_id`)
SELECT r.id, p.id
FROM `sys_role` r JOIN `sys_permission` p
WHERE r.code = 'admin';

-- --- 公告类型字典 ---
INSERT INTO `dict_notice_type` (`code`, `name`, `category`, `sort`) VALUES
    ('招标公告',   '招标公告',   '工程',      1),
    ('中标公告',   '中标公告',   '工程',      2),
    ('更正公告',   '更正公告',   '工程',      3),
    ('流标公告',   '流标公告',   '工程',      4),
    ('询价公告',   '询价公告',   '货物',      5),
    ('单一来源公示', '单一来源公示', '政府采购', 6),
    ('竞争性谈判公告', '竞争性谈判公告', '政府采购', 7),
    ('竞争性磋商公告', '竞争性磋商公告', '政府采购', 8);

-- --- 会员套餐 ---
INSERT INTO `member_package` (`name`, `code`, `price`, `sale_price`, `duration_days`, `level`, `max_subscribe`, `allow_export`, `allow_contact`, `description`, `sort`, `status`) VALUES
    ('免费会员', 'free',  0.00,  0.00,  365, 1,  3,  0, 0, '注册即送，每天可订阅 3 个关键词', 1, 1),
    ('月度会员', 'month', 99.00, 79.00,  30,  2, 10,  1, 1, '30 天高级功能', 2, 1),
    ('年度会员', 'year',  999.00, 699.00, 365, 2, 50,  1, 1, '最受欢迎的年度套餐', 3, 1),
    ('企业会员', 'ent',   4999.00, 3999.00, 365, 3, 200, 1, 1, '适合企业团队使用', 4, 1);

-- --- 采集源示例 ---
INSERT INTO `bid_source` (`name`, `code`, `source_type`, `base_url`, `list_url_rule`, `status`, `description`) VALUES
    ('全国公共资源交易平台', 'ggzy', 1, 'http://www.ggzy.gov.cn', 'http://www.ggzy.gov.cn/...?page={page}', 1, '公共资源交易信息'),
    ('中国政府采购网',      'ccgp', 1, 'http://www.ccgp.gov.cn',  'http://www.ccgp.gov.cn/...?page={page}', 1, '政府采购公告'),
    ('测试手动录入',        'manual_test', 3, NULL, NULL, 1, '用于后台手动录入标讯');
