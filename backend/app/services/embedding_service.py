# -*- coding: utf-8 -*-
"""
向量语义召回服务
=================
- 用阿里云 DashScope 兼容模式 text-embedding-v3（1024 维）把文本向量化
- 向量存 MySQL `bid_embedding` 表（float32 二进制），进程内 numpy 矩阵缓存（TTL 600s）
- 6900+ 条全量余弦用 numpy 暴力算，毫秒级，无需额外向量库
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

_EMB_MODEL = "text-embedding-v3"
_DIM = 1024
_EMB_URL = (settings.alibaba_base_url
            or "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/") + "/embeddings"

_CACHE: Dict[str, object] = {"t": 0.0, "ids": None, "mat": None, "pos": {}}
_TTL = 600
_LOCK = threading.Lock()


def _norm(arr) -> np.ndarray:
    a = np.asarray(arr, dtype=np.float32)
    n = np.linalg.norm(a, axis=-1, keepdims=True)
    n[n == 0] = 1.0
    return a / n


def encode_texts(texts: List[str], batch: int = 10) -> List[List[float]]:
    """调用 embedding 接口，返回与输入同序的向量列表。失败抛异常。"""
    import httpx
    key = settings.alibaba_api_key
    if not key:
        raise RuntimeError("未配置 ALIBABA_API_KEY，无法做语义召回")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    out: List[List[float]] = []
    with httpx.Client(timeout=30) as cli:
        for i in range(0, len(texts), batch):
            chunk = texts[i:i + batch]
            body = {"model": _EMB_MODEL, "input": chunk, "encoding_format": "float"}
            r = cli.post(_EMB_URL, headers=headers, json=body)
            r.raise_for_status()
            data = sorted(r.json()["data"], key=lambda d: d.get("index", 0))
            out.extend(d["embedding"] for d in data)
    return out


def encode_query(text: str) -> np.ndarray:
    """把查询串编码成归一化向量（float32, dim）。"""
    return _norm(encode_texts([text])[0])


def _load_matrix() -> None:
    """把 bid_embedding 全量载入内存矩阵（带 TTL 缓存）。"""
    now = time.time()
    with _LOCK:
        if _CACHE["mat"] is not None and now - float(_CACHE["t"]) < _TTL:
            return
        try:
            from app.database import SessionLocal
            from sqlalchemy import text
            db = SessionLocal()
            try:
                rows = db.execute(
                    text("SELECT bid_id, vec FROM bid_embedding WHERE model = :m"),
                    {"m": _EMB_MODEL},
                ).fetchall()
            finally:
                db.close()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[embedding] 载入向量矩阵失败（表可能未建）: {e}")
            _CACHE.update(t=now, ids=np.array([], dtype=np.int64), mat=None, pos={})
            return
        if not rows:
            _CACHE.update(t=now, ids=np.array([], dtype=np.int64), mat=None, pos={})
            return
        ids = np.array([int(r[0]) for r in rows], dtype=np.int64)
        mat = np.vstack([np.frombuffer(r[1], dtype=np.float32) for r in rows])
        mat = _norm(mat)  # 防御：确保每行归一化
        _CACHE.update(t=now, ids=ids, mat=mat, pos={int(v): k for k, v in enumerate(ids)})
        logger.info(f"[embedding] 向量矩阵载入完成: {len(ids)} 条, dim={mat.shape[1]}")


def semantic_recall(query: str, top_n: int = 60,
                    extra_ids: Optional[Iterable[int]] = None
                    ) -> Tuple[List[int], Dict[int, float]]:
    """语义召回。返回 (按相似度降序的 topN bid_id, {bid_id: 相似度})。
    extra_ids：额外需要计算相似度的候选 id（用于给关键词候选补 _sim）。"""
    _load_matrix()
    mat = _CACHE["mat"]
    ids = _CACHE["ids"]
    if mat is None or ids is None or len(ids) == 0:
        return [], {}
    qv = encode_query(query)
    sims = mat @ qv  # 已归一化 → 点积即余弦
    n = len(ids)
    k = min(top_n, n)
    idx = np.argpartition(-sims, k - 1)[:k]
    idx = idx[np.argsort(-sims[idx])]
    ordered = [int(ids[i]) for i in idx]
    result: Dict[int, float] = {int(ids[i]): float(sims[i]) for i in idx}
    if extra_ids:
        pos = _CACHE["pos"]  # type: ignore[assignment]
        for b in extra_ids:
            p = pos.get(int(b))
            if p is not None:
                result[int(b)] = float(sims[p])
    return ordered, result


def invalidate_cache() -> None:
    """建立/更新向量后调用，让新数据立即生效。"""
    with _LOCK:
        _CACHE.update(t=0.0, ids=None, mat=None, pos={})
