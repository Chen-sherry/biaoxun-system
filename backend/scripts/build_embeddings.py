# -*- coding: utf-8 -*-
"""
构建/更新标讯向量库
====================
用法（backend 目录、激活 venv 后）：
    python scripts/build_embeddings.py            # 只补新增（增量）
    python scripts/build_embeddings.py --rebuild  # 全量重建

文本 = 标题 + 正文前 600 字；用 text-embedding-v3 编码，归一化后存 bid_embedding。
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.services import embedding_service as emb  # noqa: E402

_CREATE = """
CREATE TABLE IF NOT EXISTS bid_embedding (
    bid_id     BIGINT       NOT NULL,
    model      VARCHAR(64)  NOT NULL DEFAULT 'text-embedding-v3',
    dim        INT          NOT NULL DEFAULT 1024,
    vec        LONGBLOB     NOT NULL,
    updated_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (bid_id),
    KEY idx_model (model)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


def main(rebuild: bool = False, limit: int = 0) -> None:
    db = SessionLocal()
    try:
        db.execute(text(_CREATE))
        db.commit()

        if rebuild:
            sql = ("SELECT id, title, LEFT(COALESCE(content_text,''),600) AS body "
                   "FROM bid_info WHERE status=1")
        else:
            sql = ("SELECT b.id, b.title, LEFT(COALESCE(b.content_text,''),600) AS body "
                   "FROM bid_info b LEFT JOIN bid_embedding e ON e.bid_id=b.id "
                   "WHERE b.status=1 AND e.bid_id IS NULL")
        if limit:
            sql += f" LIMIT {int(limit)}"
        rows = db.execute(text(sql)).fetchall()
        print(f"待处理 {len(rows)} 条（rebuild={rebuild}）")
        if not rows:
            print("无需更新。")
            return

        total = 0
        for i in range(0, len(rows), 10):
            chunk = rows[i:i + 10]
            texts = [(r[1] or "") + "\n" + (r[2] or "") for r in chunk]
            vecs = emb.encode_texts(texts)          # 原始向量
            normed = emb._norm(vecs)                # 归一化
            for r, v in zip(chunk, normed):
                db.execute(
                    text("INSERT INTO bid_embedding (bid_id, model, dim, vec) "
                         "VALUES (:id, :m, :d, :v) "
                         "ON DUPLICATE KEY UPDATE model=VALUES(model), dim=VALUES(dim), "
                         "vec=VALUES(vec), updated_at=CURRENT_TIMESTAMP"),
                    {"id": int(r[0]), "m": emb._EMB_MODEL, "d": emb._DIM,
                     "v": np.asarray(v, dtype=np.float32).tobytes()},
                )
            db.commit()
            total += len(chunk)
            print(f"  已处理 {total}/{len(rows)}")
        emb.invalidate_cache()
        print(f"完成，写入 {total} 条向量。")
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true", help="全量重建（默认增量补新增）")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 条（调试用）")
    args = ap.parse_args()
    main(rebuild=args.rebuild, limit=args.limit)
