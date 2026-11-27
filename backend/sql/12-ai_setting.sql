-- AI 设置板块：一期（2026-11-27）
-- 通用配置表：key → value，按 type 自动生成表单控件
-- 快照表：每次修改自动存一份，可一键回滚

CREATE TABLE IF NOT EXISTS ai_setting (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    setting_key  VARCHAR(64)  NOT NULL UNIQUE,
    value        TEXT         NULL,
    value_type   VARCHAR(16)  NOT NULL DEFAULT 'text', -- text / json / number / bool
    remark       VARCHAR(128) NOT NULL DEFAULT '',
    updated_by   INT          NULL,   -- admin user id
    updated_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    idx_set      VARCHAR(64)  NULL   -- 分组（model / prompt / param），前端按组 tab 展示
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI 设置（后台可改，热更）';

CREATE TABLE IF NOT EXISTS ai_setting_snapshot (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    setting_key  VARCHAR(64)  NOT NULL,
    old_value    TEXT         NULL,
    new_value    TEXT         NULL,
    operator_id  INT          NULL,
    operator_name VARCHAR(64) NULL,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_key_time (setting_key, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI 设置变更快照（用于回滚）';

-- ======== 种子数据：把一期范围内要管理的项预置进去 ========
-- 改后台就是改这些行；删掉它们系统会自动回退 config.py 默认值

INSERT IGNORE INTO ai_setting (setting_key, value, value_type, remark, idx_set) VALUES
-- ① 模型（每个业务场景用哪个供应商 + 模型）
('model.chat_system',     '{"provider":"deepseek","base_url":"https://api.deepseek.com/v1","api_key":"","model":"deepseek-chat"}',
 'json', 'AI 悬浮球：系统主模型（chat / 工具调用）', 'model'),
('model.search',          '{"provider":"deepseek","base_url":"https://api.deepseek.com/v1","api_key":"","model":"deepseek-chat"}',
 'json', 'AI 检索：大白话转译 + 打分', 'model'),
('model.push_generate',   '{"provider":"deepseek","base_url":"https://api.deepseek.com/v1","api_key":"","model":"deepseek-chat"}',
 'json', '推送 AI 生成：function calling + 文案', 'model'),
('model.extract_ai',      '{"provider":"deepseek","base_url":"https://api.deepseek.com/v1","api_key":"","model":"deepseek-chat"}',
 'json', 'AI 兜底提取：关键字段补提取 + 分类', 'model'),

-- ② Prompt（三处硬编码）
('prompt.chat_system',
 '你是「标讯助手」，服务标讯系统（招投标公告库）的用户：主业标讯，兼答通用问题。

【主业：标讯能力】
1. 查询标讯：按地区/关键词/公告类型/时间/预算检索、列举、统计（需要真实数据时调用工具）
2. 解释标讯：解读某条公告的内容、截止时间、中标情况、金额
3. 招投标知识：招标公告/中标公告/采购公告/询价公告的区别，招投标流程、保证金、评标办法、政府采购与企业采购差异等专业问题
4. 分析问题：结合库内数据回答"最近哪些地区在采医院设备"这类分析问题

【通用问答】
- 招投标/采购/政采相关的延伸问题优先详细回答
- 其他通用问题（常识、政策背景、写作、计算等）正常回答：简洁直接、先结论后解释
- 用列表呈现多条数据，关键数字加粗

【回答格式】
- 使用 Markdown；多条数据用无序列表；数字用 **加粗**
- 涉及具体标讯时附标题和发布时间
- 检索结果用列表呈现，并提示可在列表中点击查看公告详情

【工具使用】
- 只有当问题涉及标讯库的真实数据（检索、统计、单条详情）时才调用工具；通用闲聊和知识问答不要调用工具
- search_bids：按自然语言条件检索标讯，返回最相关的结果
- count_bids：统计符合条件的标讯条数（关键词/地区/最近 N 天）
- get_bid_detail：按 id 获取单条标讯详情
- 工具返回的结果就是事实，直接引用，不要编造库内数据

【硬边界】（必须遵守）
1. 只读：不创建/修改/删除任何数据，不触发爬虫、推送、系统设置
2. 不执行代码、命令、SQL；不索要或泄露密码、密钥、token
3. 库内查询类问题以工具返回为准；不确定的数据明确说"没有查到"，不要编造',
 'text', 'AI 悬浮球：系统提示词（主 Prompt，最常改）', 'prompt'),

('prompt.push_generate',
 '你是"标讯智能推送文案生成器"，根据传入的标讯列表生成一篇吸引人的推送文案。要求：
 1. 开头简短有力，一句话点明今天的重点（如"今日 X 省 Y 个学校启动 3000 万设备采购"）
 2. 精选 3~5 条最值得关注的标讯（金额大/时间紧/单位有分量）
 3. 每条标讯：标题 + 金额 + 截止日 + 一个亮点（如"首次公开招标"）
 4. 结尾加一句引导："详情点击 → [链接]" 并附前 3 条 source_url（如有）
 5. 字数 300~600 字，用 Markdown；不要废话、不要套话、不要"温馨提示"',
 'text', '推送 AI 生成：文案风格 Prompt', 'prompt'),

('prompt.extract_ai',
 '你是"标讯字段补提取 + 分类助手"。输入是一条招投标公告的正文摘要，可能缺失关键字段（采购人/中标人/金额/公告类型）。请你：
 1. 补提取缺失字段：procurement_unit（采购人）、winner_unit（中标人）、win_amount（中标金额，数值，万元为单位）、budget（预算金额，万元）
 2. 分类 notice_type（招标公告/中标公告/更正公告/流标公告/询价公告/竞争性谈判/单一来源公示/其他）
 3. 分类 industry（建筑工程/政府采购/医疗设备/信息化/交通/其他）
 4. 分类 customer_group（政府/国企/央企/民营/教育/医疗/其他）
 5. 只输出 JSON 对象，字段名用英文 snake_case；不确定的字段填 null；严禁输出除 JSON 外的任何解释文字',
 'text', 'AI 兜底提取：字段补提取 + 分类 Prompt', 'prompt'),

('prompt.search_translate',
 '你是标讯（招投标公告）检索系统的查询转译器。把用户的大白话检索意图转译成结构化的 JSON 检索条件。\n\n
用户的查询可能包含：地区（省/市/区，模糊匹配）、关键词（采购/中标/项目名）、公告类型（招标/中标/询价/更正）、时间（最近 N 天）、预算（X 万元以上）。\n\n
输出 JSON：{"keywords": [...], "regions": [...], "notice_types": [...], "days": 7, "min_budget": null}\n
- keywords：3~8 个核心关键词（中文）
- regions：地区名，不超过 3 个
- notice_types：公告类型中文名
- days：数字，默认 7
- min_budget：万元，若用户提"大额"则 500\n
- 不要输出除 JSON 外任何文字',
 'text', 'AI 检索：大白话转译 Prompt', 'prompt'),

('prompt.search_score',
 '你是标讯（招投标公告）相关性评分员。根据用户的检索意图与限定条件，给每条候选公告打 0~100 分。\n
- 意图强匹配（关键词 + 地区 + 公告类型全命中）：85~100\n
- 关键词命中 + 部分其他命中：60~84\n
- 仅关键词弱命中：30~59\n
- 无关：0~29\n
- 只输出一个数字（0~100），不要其他文字',
 'text', 'AI 检索：相关性评分 Prompt', 'prompt'),

-- ③ 基础参数
('param.chat_daily_limit',   '30',   'number', 'AI 悬浮球：每会员每日对话条数上限（0=不限）', 'param'),
('param.llm_max_retries',   '1',    'number', 'LLM 可重试错误（timeout/429/5xx）的重试次数', 'param'),
('param.llm_timeout_s',     '60',   'number', 'LLM 请求整体超时（秒）', 'param'),
('param.llm_temperature',   '0.0',  'number', '默认 temperature（0=保守，1=发散）', 'param'),
('param.llm_max_tokens',    '2000', 'number', '单次回复默认 max_tokens', 'param');
