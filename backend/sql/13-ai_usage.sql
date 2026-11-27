-- AI 用量日志（2026-11-27）
-- 每次 LLM 调用落一条，用于后台日/周/月成本统计

CREATE TABLE IF NOT EXISTS ai_usage_log (
    id                BIGINT AUTO_INCREMENT PRIMARY KEY,
    tag               VARCHAR(32)  NOT NULL DEFAULT '',  -- 业务标签：chat/translate/score/push/extract/stream
    model             VARCHAR(64)  NOT NULL DEFAULT '',
    prompt_tokens     INT          NOT NULL DEFAULT 0,
    completion_tokens INT          NOT NULL DEFAULT 0,
    total_tokens      INT          NOT NULL DEFAULT 0,
    latency_ms        INT          NOT NULL DEFAULT 0,
    created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_created (created_at),
    INDEX idx_tag_time (tag, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI 调用用量日志（成本统计）';
