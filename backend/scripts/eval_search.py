# -*- coding: utf-8 -*-
"""
智能检索评测脚本（离线基准）
=============================
用法（在 backend 目录、激活 venv 后运行）：
    python scripts/eval_search.py                # 评估 eval_set.json 全部用例
    python scripts/eval_search.py --top 10       # 只看 Top10 的精确率
    python scripts/eval_search.py --save out.json

指标说明：
- P@K           : TopK 中「主题命中 且（若限定地区）地区正确」的占比
- hit           : TopK 是否至少命中 1 条相关（0/1）
- 高相关(>=70)  : 返回结果里达到高相关线的条数（看评分分布健不健康）
- 地区越界      : 主题命中但地区不对的条数（应为 0 或很低，检查大区过滤）

注意：相关性用「关键词命中」做代理，是快速可复现的基准；人工精标可后续替换 eval_set。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# 允许从 backend/scripts 直接运行
_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.services.ai_search import ai_search  # noqa: E402


def _topic_ok(item: dict, keywords) -> bool:
    if not keywords:
        return True
    blob = (item.get("title") or "") + " " + (item.get("snippet") or "")
    return any(k in blob for k in keywords)


def _region_ok(item: dict, prefixes) -> bool:
    """地区是否命中：有 region_prefixes 时用候选 region_code 前缀判定，否则视为不限地区。"""
    if not prefixes:
        return True
    code = str(item.get("region_code") or "").strip()
    if not code:
        return False  # 有地区约束但候选无码 → 无法确认，算未命中
    return any(code.startswith(p) for p in prefixes)


def run(top_k: int = 10, save: str | None = None) -> None:
    set_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_set.json")
    with open(set_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    cases = data.get("cases", [])

    rows = []
    sum_p = 0.0
    sum_hit = 0
    total_match = 0
    total_leak = 0

    print(f"\n智能检索评测 · Top{top_k} · 共 {len(cases)} 条用例\n" + "=" * 92)
    hdr = f"{'查询':<20}{'返回':>5}{'候选':>6}{'高70':>5}{'匹配@K':>7}{'P@K':>7}{'地区越界':>8}  地区/说明"
    print(hdr)
    print("-" * 92)

    for c in cases:
        q = c["query"]
        try:
            res = ai_search(q)
        except Exception as e:  # noqa: BLE001
            print(f"{q:<20}  ERROR: {e}")
            continue
        items = res.get("items", [])[:top_k]
        cand = res.get("candidate_count", 0)
        high = sum(1 for i in items if i.get("score", 0) >= 70)

        match = 0
        leak = 0
        for i in items:
            t_ok = _topic_ok(i, c.get("topic_keywords"))
            r_ok = _region_ok(i, c.get("region_prefixes"))
            if t_ok and r_ok:
                match += 1
            elif t_ok and not r_ok:
                leak += 1
        denom = max(1, len(items))
        p_at_k = match / denom
        hit = 1 if match > 0 else 0

        sum_p += p_at_k
        sum_hit += hit
        total_match += match
        total_leak += leak

        region = res.get("translated", {}).get("region_name") or "-"
        print(f"{q:<20}{len(items):>5}{cand:>6}{high:>5}{match:>7}{p_at_k:>7.2f}{leak:>8}  {region}")

        rows.append({"query": q, "candidate": cand, "high": high,
                     "match@k": match, "p@k": round(p_at_k, 3), "leak": leak,
                     "region": region, "items": items})

    n = max(1, len(cases))
    print("-" * 92)
    print(f"平均 P@{top_k} = {sum_p / n:.3f}   |   命中率(TopK含相关) = {sum_hit}/{len(cases)}"
          f"   |   总匹配 {total_match}   |   地区越界 {total_leak}")
    print("=" * 92)

    if save:
        with open(save, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2, default=str,
                      )
        print(f"明细已保存：{save}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=10, help="评估 TopK，默认 10")
    ap.add_argument("--save", type=str, default=None, help="把明细保存为 JSON")
    args = ap.parse_args()
    run(top_k=args.top, save=args.save)
