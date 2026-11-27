-- 语义向量召回：标讯向量表
-- vec 存 float32 归一化向量（1024 维，text-embedding-v3）的二进制
CREATE TABLE IF NOT EXISTS bid_embedding (
    bid_id     BIGINT       NOT NULL COMMENT 'bid_info.id',
    model      VARCHAR(64)  NOT NULL DEFAULT 'text-embedding-v3',
    dim        INT          NOT NULL DEFAULT 1024,
    vec        LONGBLOB     NOT NULL COMMENT 'float32 归一化向量',
    updated_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (bid_id),
    KEY idx_model (model)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='标讯语义向量（AI检索混合召回用）';
