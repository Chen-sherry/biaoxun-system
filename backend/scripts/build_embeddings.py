# -*- coding: utf-8 -*-
"""
构建/更新标讯向量库（命令行入口）
==================================
日常无需手动执行——爬虫清洗提取后会自动增量生成。
仅在以下场景手动跑：
    python scripts/build_embeddings.py            # 补历史缺失（增量）
    python scripts/build_embeddings.py --rebuild  # 全量重建（换模型/清洗后）
    python scripts/build_embeddings.py --limit 50 # 调试只处理前 N 条
"""
from __future__ import annotations

import argparse
import os
import sys

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.services.embedding_service import build_embeddings  # noqa: E402


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true", help="全量重建（默认只补缺失）")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 条（调试用）")
    args = ap.parse_args()
    n = build_embeddings(rebuild=args.rebuild, limit=args.limit)
    print(f"完成，写入 {n} 条向量。")
