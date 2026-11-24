# -*- coding: utf-8 -*-
"""
AI 检索（大白话搜索）
=====================
流程：
  1. LLM 转译：用户大白话 → 结构化检索条件（关键词/地区/日期/公告类型等）
  2. 知识库粗筛：按条件从 bid_info 捞候选（命中数优先，时间倒序，最多 50 条）
  3. LLM 语义打分：DeepSeek 按用户真实意图逐条打 0~100 分
  4. 只保留 > 75 分的结果，按分数降序返回

DeepSeek 不可用时降级：转译失败直接用原句分词，打分失败用本地关键词加权分。
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.config import settings

MIN_SCORE = 75          # 低于此分不展示
CANDIDATE_LIMIT = 50    # 送入 LLM 打分的候选上限
SCORING_CHUNK = 50      # 每次打分调用的候选批量（一次调用）


# ---------------------------------------------------------------- #
#  1. 大白话 → 结构化检索条件
# ---------------------------------------------------------------- #

TRANSLATE_PROMPT = """你是标讯（招投标公告）检索系统的查询转译器。把用户的大白话检索意图转译成结构化的 JSON 检索条件。

今天日期：{today}

可用字段与取值规则：
- keywords: string[]，3~6 个核心检索词（保留原意，名词短语，不要含"找/帮我/最近"等虚词）
- region_code: 6 位国标行政区划代码（如 合肥=340100、安徽=340000、北京=110000、朝阳区=110105）。用户提到市/区县用对应完整代码，提到省用省代码，没提则 null
- region_name: 与 region_code 对应的中文名（如 合肥、安徽），用于显示，没提则 null
- date_from / date_to: YYYY-MM-DD，按用户话里的相对时间换算成具体日期（如"最近一个月"→ date_from=一个月前），没提则 null
- notice_type: 公告类型（招标公告/中标公告/政府采购/询价公告等），用户没提则 null
- procure_type: 招采类型（公开招标/邀请招标/竞争性谈判/单一来源等），没提则 null
- customer_group: 客群（政务/国企/民企），没提则 null

硬性要求：
1. 用户话里提到的地区、时间范围、公告类型，必须逐一提取到对应字段，一个都不能漏
2. 提到"最近/近 N 天/本月"等相对时间必须换算成具体日期
3. keywords 必须覆盖检索主题核心名词（如"学校""医院"），不得用"项目""招标"这类泛词顶替

只输出 JSON，不要任何其他文字。示例输出：
{{"keywords":["学校","消防设施改造"],"region_code":"340100","region_name":"合肥","date_from":"2026-10-24","date_to":null,"notice_type":"中标公告","procure_type":null,"customer_group":null}}
"""


def _today() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")


def _fallback_keywords(query: str) -> List[str]:
    """LLM 不可用时的粗暴分词：按标点/空白拆 + 提取 2 字以上片段。"""
    parts = re.split(r"[,，、。.\s]+", query)
    kws = [p.strip() for p in parts if len(p.strip()) >= 2]
    return kws[:6] or ([query.strip()] if query.strip() else [])


def translate_query(query: str) -> Dict[str, Any]:
    """大白话 → 结构化条件。失败降级为纯关键词。"""
    default = dict(keywords=_fallback_keywords(query), region_code=None, region_name=None,
                   date_from=None, date_to=None, notice_type=None,
                   procure_type=None, customer_group=None)
    if not settings.deepseek_api_key:
        return default
    try:
        import httpx
        resp = httpx.post(
            f"{settings.deepseek_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
            json={
                "model": settings.deepseek_model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": TRANSLATE_PROMPT.format(today=_today())},
                    {"role": "user", "content": query},
                ],
            },
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        m = re.search(r"\{.*\}", content, re.S)
        data = json.loads(m.group(0)) if m else {}
        if not isinstance(data.get("keywords"), list) or not data["keywords"]:
            data["keywords"] = default["keywords"]
        for k in default:
            data.setdefault(k, default[k])
        return data
    except Exception as e:  # noqa: BLE001
        print(f"[ai_search] 转译失败，降级关键词: {e}")
        return default


# ---------------------------------------------------------------- #
#  2. 知识库粗筛（MySQL）
# ---------------------------------------------------------------- #

def _notice_type_id(name: str) -> Optional[int]:
    try:
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            row = db.execute(
                text("SELECT id FROM dict_notice_type WHERE name LIKE :n LIMIT 1"),
                {"n": f"%{name}%"},
            ).fetchone()
            return int(row[0]) if row else None
        finally:
            db.close()
    except Exception:
        return None


def search_candidates(cond: Dict[str, Any]):
    """按条件粗筛候选，逐级放宽（日期最先放、地区最后放）。
    返回 (候选列表, 是否放宽了日期)。"""
    levels = [
        dict(region=True, date=True, extra=True),    # 严格：全部条件
        dict(region=True, date=False, extra=True),   # 放宽日期（库内数据可能较旧）
        dict(region=True, date=False, extra=False),  # 只留关键词 + 地区
        dict(region=False, date=False, extra=False), # 只留关键词
    ]
    for lv in levels:
        rows = _query_candidates(cond, lv)
        if rows:
            date_relaxed = (not lv["date"]
                            and bool(cond.get("date_from") or cond.get("date_to")))
            return rows, date_relaxed
    # 最终兜底：纯时间倒序，交给打分层过滤
    rows = _query_candidates(dict(cond, keywords=[]),
                             dict(region=False, date=False, extra=False))
    return rows, bool(cond.get("date_from") or cond.get("date_to"))


def _query_candidates(cond: Dict[str, Any], lv: Dict[str, bool]) -> List[Dict[str, Any]]:
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        where = ["b.status = 1"]
        params: Dict[str, Any] = {}
        score_expr_parts = []
        keywords = cond.get("keywords") or []
        for i, kw in enumerate(keywords):
            params[f"kw{i}"] = f"%{kw}%"
            score_expr_parts.append(
                f"(CASE WHEN b.title LIKE :kw{i} THEN 2 ELSE 0 END"
                f" + CASE WHEN b.content_text LIKE :kw{i} THEN 1 ELSE 0 END)"
            )
        if keywords:
            where.append("(" + " OR ".join(
                f"b.title LIKE :kw{i} OR b.content_text LIKE :kw{i}"
                for i in range(len(keywords))
            ) + ")")
        rank_expr = " + ".join(score_expr_parts) if score_expr_parts else ""

        if lv.get("region"):
            code = str(cond.get("region_code") or "").strip()
            if len(code) == 6 and code.isdigit():
                # 省码(尾4位0)按前2位匹配，市码(尾2位0)按前4位匹配，区县精确匹配
                if code.endswith("0000"):
                    where.append("b.region_code LIKE :region")
                    params["region"] = code[:2] + "%"
                elif code.endswith("00"):
                    where.append("b.region_code LIKE :region")
                    params["region"] = code[:4] + "%"
                else:
                    where.append("b.region_code = :region")
                    params["region"] = code
        if lv.get("date"):
            if cond.get("date_from"):
                where.append("b.publish_time >= :df")
                params["df"] = cond["date_from"]
            if cond.get("date_to"):
                where.append("b.publish_time <= :dt")
                params["dt"] = cond["date_to"] + " 23:59:59"
        if lv.get("extra"):
            if cond.get("notice_type"):
                nid = _notice_type_id(cond["notice_type"])
                if nid:
                    where.append("b.notice_type_id = :nt")
                    params["nt"] = nid
            if cond.get("procure_type"):
                where.append("b.procure_type LIKE :pt")
                params["pt"] = f"%{cond['procure_type']}%"
            if cond.get("customer_group"):
                where.append("b.customer_group = :cg")
                params["cg"] = cond["customer_group"]

        order_clause = (f"({rank_expr}) DESC, b.publish_time DESC"
                        if rank_expr else "b.publish_time DESC")
        sql = text(f"""
            SELECT b.id, b.title, b.tenderee, b.agency, b.procure_type,
                   b.publish_time, b.deadline, b.budget, b.winner_unit,
                   b.region_code, b.source_url,
                   COALESCE(r.name, '') AS region_name,
                   LEFT(COALESCE(b.content_text, ''), 200) AS snippet
            FROM bid_info b
            LEFT JOIN dict_region r ON r.code = b.region_code
            WHERE {' AND '.join(where)}
            ORDER BY {order_clause}
            LIMIT :lim
        """)
        params["lim"] = CANDIDATE_LIMIT
        rows = db.execute(sql, params).mappings().all()
        return [dict(r) for r in rows]
    finally:
        db.close()


# ---------------------------------------------------------------- #
#  3. DeepSeek 语义打分（>75 才展示）
# ---------------------------------------------------------------- #

SCORE_PROMPT = """你是标讯（招投标公告）相关性评分员。根据用户的检索意图，给每条候选公告打 0~100 分。

评分标准：
- 90~100：主题、地区、时间、类型全部高度吻合，就是用户要找的
- 76~89：核心主题吻合，个别条件（地区/时间/类型）有偏差
- 50~75：部分相关但偏离用户真实意图（如只要中标公告却是招标公告、地区不符）
- 0~49：基本无关

只输出 JSON 数组，格式：[{{"id": 1, "score": 88, "reason": "一句话理由"}}]，不要任何其他文字。"""


def score_candidates(query: str, candidates: List[Dict[str, Any]],
                     date_relaxed: bool = False) -> List[Dict[str, Any]]:
    """逐批调用 DeepSeek 打分；失败降级本地关键词加权。返回按分数降序的完整结果。"""
    if not candidates:
        return []
    if not settings.deepseek_api_key:
        return _local_score(query, candidates)

    date_note = ""
    if date_relaxed:
        date_note = ("\n注意：库内数据发布时间集中在 2025 年上半年，与用户要求的时间段不吻合。"
                     "忽略日期差异，按主题、地区、公告类型的相关性打分，不要因日期扣分。")

    import httpx
    results: List[Dict[str, Any]] = []
    try:
        for start in range(0, len(candidates), SCORING_CHUNK):
            batch = candidates[start:start + SCORING_CHUNK]
            items = [
                {"id": c["id"], "title": c["title"],
                 "snippet": (c.get("snippet") or "")[:160],
                 "tenderee": c.get("tenderee"), "procure_type": c.get("procure_type"),
                 "publish_time": str(c.get("publish_time") or "")[:10],
                 "budget": c.get("budget")}
                for c in batch
            ]
            resp = httpx.post(
                f"{settings.deepseek_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
                json={
                    "model": settings.deepseek_model,
                    "temperature": 0,
                    "messages": [
                        {"role": "system", "content": SCORE_PROMPT},
                        {"role": "user", "content":
                            f"用户检索意图：{query}{date_note}\n\n候选公告 JSON：\n"
                            + json.dumps(items, ensure_ascii=False)},
                    ],
                },
                timeout=60,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            m = re.search(r"\[.*\]", content, re.S)
            scores = json.loads(m.group(0)) if m else []
            by_id = {int(s["id"]): s for s in scores if isinstance(s, dict) and s.get("id") is not None}
            for c in batch:
                s = by_id.get(c["id"], {})
                results.append({**c, "score": int(s.get("score", 0)),
                                "reason": s.get("reason", "")})
        return sorted(results, key=lambda x: x["score"], reverse=True)
    except Exception as e:  # noqa: BLE001
        print(f"[ai_search] LLM 打分失败，降级本地打分: {e}")
        return _local_score(query, candidates)


def _local_score(query: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """降级：本地关键词加权打分（与 deepseek_match 的降级逻辑一致）。"""
    kws = _fallback_keywords(query)
    out = []
    for c in candidates:
        text_blob = (c["title"] or "") + (c.get("snippet") or "")
        hits = sum(1 for k in kws if k.lower() in text_blob.lower())
        score = int(hits / len(kws) * 90) if kws else 0
        out.append({**c, "score": score, "reason": "本地关键词匹配（AI 服务不可用）"})
    return sorted(out, key=lambda x: x["score"], reverse=True)


# ---------------------------------------------------------------- #
#  主流程
# ---------------------------------------------------------------- #

def ai_search(query: str, limit: int = 20) -> Dict[str, Any]:
    """一次完整 AI 检索：转译 → 粗筛 → 打分 → 过滤 >75。"""
    t0 = time.time()
    cond = translate_query(query)
    candidates, date_relaxed = search_candidates(cond)
    scored = score_candidates(query, candidates, date_relaxed=date_relaxed)
    passed = [s for s in scored if s["score"] > MIN_SCORE][:limit]
    return {
        "items": passed,
        "translated": dict(cond),
        "date_relaxed": date_relaxed,
        "candidate_count": len(candidates),
        "passed_count": len(passed),
        "cost_ms": int((time.time() - t0) * 1000),
    }
