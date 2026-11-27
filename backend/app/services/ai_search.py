# -*- coding: utf-8 -*-
"""
AI 检索（大白话搜索）
=====================
流程：
  1. LLM 转译：用户大白话 → 结构化检索条件（关键词/地区/日期/公告类型/预算/同义词）
  2. 知识库粗筛：FULLTEXT(ngram) 召回为主，逐级放宽，LIKE 兜底（最多 120 条候选）
  3. 预算软过滤：budget 超出用户要求的候选剔除（解析失败的保留交打分层判断）
  4. LLM 语义打分：DeepSeek 分批并行打 0~100 分（单批失败只降级该批，不再整体降级）
  5. 分档返回：>=75 高度相关 / 60~74 辅助展示 / <60 丢弃，附诊断信息

DeepSeek 不可用时降级：转译失败直接用原句分词，打分失败用本地关键词加权分。
FULLTEXT 索引不存在时自动走 LIKE 老路（解耦部署顺序，回滚只需 drop 索引）。
"""
from __future__ import annotations

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

from app.config import settings
from app.services import ai_setting_service as svc
from app.services.data_clean import parse_budget_wan

logger = logging.getLogger(__name__)

HIGH_SCORE = 75        # >= 此分：高度相关
MID_SCORE = 60         # 60~74：较相关，辅助展示；<60 丢弃
CANDIDATE_LIMIT = 120  # 召回池上限（DB 粗筛）
SCORE_CAP = 60         # 默认送 LLM 打分的候选上限（先本地关键词粗排取 Top，控制成本）
MIN_CANDIDATES = 40    # 单层召回不足此数则继续放宽并累积合并（避免首层非空即停导致召回过少）
FALLBACK_MIN_SCORE = 40  # 兜底展示的分数线：最高分低于此值视为真无关，返回空态而非垃圾
SCORING_CHUNK = 30     # 每次打分调用的候选批量
SCORE_WORKERS = 3      # 打分批次并行度

FT_INDEX_CACHE_S = 300   # FULLTEXT 索引存在性探测缓存
LIB_DATE_CACHE_S = 600   # 库内日期范围缓存


# ---------------------------------------------------------------- #
#  1. 大白话 → 结构化检索条件
# ---------------------------------------------------------------- #

TRANSLATE_PROMPT = """你是标讯（招投标公告）检索系统的查询转译器。把用户的大白话检索意图转译成结构化的 JSON 检索条件。

今天日期：{today}

可用字段与取值规则：
- keywords: string[]，3~6 个核心检索词（保留原意，名词短语，不要含"找/帮我/最近"等虚词）
- synonyms: string[]，2~10 个同义词、上位词或地区展开词（如 学校→中小学、幼儿园、教育局；医院→卫生院、人民医院），用于扩大召回；没有合适的给 []
- 地区概念必须展开：用户提到口语化区域（粤北/珠三角/粤东/粤西/粤西地区/长三角/京津冀/东北/西北 等）时，keywords 保留概念词本身，synonyms 必须列出该区域覆盖的城市名（粤北→韶关、清远、云浮；珠三角→广州、深圳、佛山、东莞、中山、珠海、惠州、江门、肇庆；粤东→汕头、潮州、揭阳、汕尾；粤西→湛江、茂名、阳江；长三角→上海、南京、杭州、苏州、无锡、宁波；京津冀→北京、天津、石家庄），让城市名参与召回
- region_code: 6 位国标行政区划代码（如 合肥=340100、安徽=340000、北京=110000、朝阳区=110105）。用户提到市/区县用对应完整代码，提到省用省代码，没提则 null
- region_name: 与 region_code 对应的中文名（如 合肥、安徽），用于显示，没提则 null
- date_from / date_to: YYYY-MM-DD，按用户话里的相对时间换算成具体日期（如"最近一个月"→ date_from=一个月前），没提则 null
- notice_type: 公告类型（招标公告/中标公告/政府采购/询价公告等），用户没提则 null
- procure_type: 招采类型（公开招标/邀请招标/竞争性谈判/单一来源等），没提则 null
- customer_group: 客群（政务/国企/民企），没提则 null
- budget_min / budget_max: 数字，单位万元。用户提到预算时提取（"预算100万以内"→ budget_max=100；"300万以上"→ budget_min=300；"50~200万"→ 两个都给），没提则 null

硬性要求：
1. 用户话里提到的地区、时间范围、公告类型、预算，必须逐一提取到对应字段，一个都不能漏
2. 提到"最近/近 N 天/本月"等相对时间必须换算成具体日期
3. keywords 必须覆盖检索主题核心名词（如"学校""医院"），不得用"项目""招标"这类泛词顶替

只输出 JSON，不要任何其他文字。示例输出：
{"keywords":["学校","消防设施改造"],"synonyms":["中小学","幼儿园"],"region_code":"340100","region_name":"合肥","date_from":"2026-10-24","date_to":null,"notice_type":"中标公告","procure_type":null,"customer_group":null,"budget_min":null,"budget_max":null}
"""


def _today() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")


def _fallback_keywords(query: str) -> List[str]:
    """LLM 不可用时的粗暴分词：按标点/空白拆 + 提取 2 字以上片段。"""
    parts = re.split(r"[,，、。.\s]+", query)
    kws = [p.strip() for p in parts if len(p.strip()) >= 2]
    return kws[:6] or ([query.strip()] if query.strip() else [])


def _default_cond(query: str) -> Dict[str, Any]:
    return dict(keywords=_fallback_keywords(query), region_code=None, region_name=None,
                date_from=None, date_to=None, notice_type=None,
                procure_type=None, customer_group=None,
                budget_min=None, budget_max=None, synonyms=[])


def translate_query(query: str) -> Tuple[Dict[str, Any], bool]:
    """大白话 → 结构化条件。返回 (条件, LLM 是否成功)。失败降级为纯关键词。"""
    default = _default_cond(query)
    model_cfg = svc.get_model("search")
    if not (model_cfg.get("api_key") or settings.deepseek_api_key):
        return default, False
    try:
        from app.services.llm import chat_json
        prompt = svc.get_prompt("prompt.search_translate", TRANSLATE_PROMPT)
        # 用 replace 而非 format：Prompt 可在 admin 后台编辑，避免用户写入花括号导致格式化异常
        prompt_text = prompt.replace("{today}", _today())
        data = chat_json(
            [
                {"role": "system", "content": prompt_text},
                {"role": "user", "content": query},
            ],
            expect="object",
            temperature=0,
            timeout=30,
            json_mode=True,
            tag="translate",
            model_override=model_cfg.get("model"),
            base_url_override=model_cfg.get("base_url"),
            api_key_override=model_cfg.get("api_key"),
        )
        if not isinstance(data.get("keywords"), list) or not data["keywords"]:
            data["keywords"] = default["keywords"]
        syn = data.get("synonyms")
        data["synonyms"] = [str(s).strip() for s in syn if isinstance(s, str) and s.strip()][:10] \
            if isinstance(syn, list) else []
        for k in default:
            data.setdefault(k, default[k])
        return data, True
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[ai_search] 转译失败，降级关键词: {e}")
        return default, False


# ---------------------------------------------------------------- #
#  2. FULLTEXT 索引探测 + 布尔模式查询构造
# ---------------------------------------------------------------- #

_ft_cache: Dict[str, Any] = {"t": 0.0, "cols": None}


def _ft_columns() -> Optional[List[str]]:
    """返回 FULLTEXT 索引覆盖列（优先含 content_text 的索引），None=无索引。缓存 300s。"""
    now = time.time()
    if _ft_cache["cols"] is not None and now - _ft_cache["t"] < FT_INDEX_CACHE_S:
        return _ft_cache["cols"]
    cols: Optional[List[str]] = None
    try:
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            rows = db.execute(text(
                "SELECT INDEX_NAME, COLUMN_NAME FROM information_schema.STATISTICS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'bid_info' "
                "AND INDEX_TYPE = 'FULLTEXT' ORDER BY INDEX_NAME, SEQ_IN_INDEX"
            )).fetchall()
            if rows:
                by_name: Dict[str, List[str]] = {}
                for name, col in rows:
                    by_name.setdefault(name, []).append(col)
                for _, cols_ in by_name.items():
                    if "content_text" in cols_:
                        cols = cols_
                        break
                if cols is None:
                    cols = list(by_name.values())[0]
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[ai_search] FULLTEXT 索引探测失败，走 LIKE: {e}")
        cols = None
    _ft_cache.update(t=now, cols=cols)
    if cols:
        logger.info(f"[ai_search] FULLTEXT 索引可用: {cols}")
    return cols


_FT_SPECIAL = re.compile(r'[+\-<>()~*"@\\]')


def build_ft_query(keywords: List[str], mode: str = "or",
                   extra: Optional[List[str]] = None) -> Tuple[Optional[str], List[str]]:
    """构造 FULLTEXT 布尔模式表达式。
    - 关键词必须带引号（ngram 下裸词会被拆成单 bigram 全库噪音）
    - AND 用 + 前缀；len<2 的词 ngram 无法索引，丢弃
    - 全部词都过短 → 返回 (None, dropped)（AGAINST('') 会 1064，整层跳过 FT）
    返回 (表达式或 None, 被丢弃的短词列表)。"""
    words = list(keywords or [])
    if extra:
        words = words + list(extra)
    dropped: List[str] = []
    seen = set()
    cleaned: List[str] = []
    for w in words:
        w = _FT_SPECIAL.sub("", str(w or "")).strip()
        if not w:
            continue
        if len(w) < 2:
            if w not in dropped:
                dropped.append(w)
            continue
        if w in seen:
            continue
        seen.add(w)
        cleaned.append(w)
        if len(cleaned) >= 8:
            break
    if not cleaned:
        return None, dropped
    if mode == "and" and len(cleaned) >= 2:
        expr = " ".join(f'+\"{w}\"' for w in cleaned)
    else:
        expr = " ".join(f'\"{w}\"' for w in cleaned)
    return expr, dropped


# ---------------------------------------------------------------- #
#  3. 知识库粗筛（FULLTEXT 为主，LIKE 兜底）
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


def search_candidates(cond: Dict[str, Any]
                      ) -> Tuple[List[Dict[str, Any]], bool, Dict[str, Any]]:
    """按条件粗筛候选。召回策略序列（逐层累积）：
    ft_and(全条件) → ft_or(全条件) → ft_or_exp(+同义词)
    → 放宽日期 → 放宽类型 → 放宽地区
    → like_or 兜底（短词/FT 0 行/索引缺失时走原 4 级 LIKE）→ latest 纯最新
    单层结果不足 MIN_CANDIDATES 时继续放宽并按 id 去重合并，避免首层非空即停
    导致召回过少；达到目标数或策略用尽才返回。
    返回 (候选列表, 是否放宽了日期, 诊断 meta)。"""
    keywords = cond.get("keywords") or []
    synonyms = cond.get("synonyms") or []
    has_date = bool(cond.get("date_from") or cond.get("date_to"))

    strict = dict(region=True, date=True, extra=True)
    lv_date = dict(region=True, date=False, extra=True)    # 放宽日期
    lv_type = dict(region=True, date=False, extra=False)   # 放宽类型
    lv_kw = dict(region=False, date=False, extra=False)    # 只留关键词

    meta: Dict[str, Any] = {"match_mode": "latest", "relax_level": "latest",
                            "dropped_short": []}

    strategies: List[Tuple[str, Dict[str, bool], Optional[Dict[str, Any]], str]] = []
    ft_cols = _ft_columns()
    if ft_cols and keywords:
        and_expr, dropped = build_ft_query(keywords, "and")
        or_expr, dropped2 = build_ft_query(keywords, "or")
        exp_expr, dropped3 = build_ft_query(keywords, "or", extra=synonyms)
        meta["dropped_short"] = sorted(set(dropped + dropped2 + dropped3))
        if or_expr:
            ft_match = {"kind": "ft", "cols": ft_cols}
            if and_expr and and_expr != or_expr:
                strategies.append(("ft_and", strict, dict(ft_match, expr=and_expr), "strict"))
            strategies.append(("ft_or", strict, dict(ft_match, expr=or_expr), "strict"))
            if exp_expr and exp_expr != or_expr:
                strategies.append(("ft_or_exp", strict, dict(ft_match, expr=exp_expr), "strict"))
            strategies.append(("ft_or", lv_date, dict(ft_match, expr=or_expr), "date_relaxed"))
            strategies.append(("ft_or", lv_type, dict(ft_match, expr=or_expr), "type_relaxed"))
            strategies.append(("ft_or", lv_kw, dict(ft_match, expr=or_expr), "region_relaxed"))
            # FT 走完仍不足 → LIKE 关键词兜底
            strategies.append(("like_or", lv_kw, {"kind": "like"}, "like"))
        else:
            meta["match_mode"] = "like"   # 全是短词，直接 LIKE 老路
            meta["relax_level"] = "strict"
    else:
        # 索引缺失 / 无关键词：原 4 级 LIKE 语义不变
        meta["match_mode"] = "like"
        strategies = [
            ("like_and", strict, {"kind": "like"}, "strict"),
            ("like_and", lv_date, {"kind": "like"}, "date_relaxed"),
            ("like_and", lv_type, {"kind": "like"}, "type_relaxed"),
            ("like_and", lv_kw, {"kind": "like"}, "region_relaxed"),
        ]

    if not strategies:
        # 索引缺失 / 无关键词 / 全部短词 → 原 4 级 LIKE 语义不变
        meta["match_mode"] = "like"
        strategies = [
            ("like_and", strict, {"kind": "like"}, "strict"),
            ("like_and", lv_date, {"kind": "like"}, "date_relaxed"),
            ("like_and", lv_type, {"kind": "like"}, "type_relaxed"),
            ("like_and", lv_kw, {"kind": "like"}, "region_relaxed"),
        ]

    # 逐层累积：不足 MIN_CANDIDATES 就继续放宽合并，达到目标或用尽为止
    merged: Dict[int, Dict[str, Any]] = {}
    order: List[str] = []
    first_mode, first_relax = strategies[0][0], strategies[0][3]
    max_relax = first_relax
    relax_rank = {"strict": 0, "date_relaxed": 1, "type_relaxed": 2,
                  "region_relaxed": 3, "like": 4}
    for mode, lv, match, relax in strategies:
        rows = _fetch_rows(cond, lv, match)
        for r in rows:
            if r["id"] not in merged:
                merged[r["id"]] = r
                order.append(mode)
        if relax_rank.get(relax, 0) > relax_rank.get(max_relax, 0):
            max_relax = relax
        if len(merged) >= MIN_CANDIDATES:
            break

    if merged:
        # 诊断用：首层模式 + 实际达到的最宽放宽级别
        meta["match_mode"] = first_mode
        meta["relax_level"] = max_relax
        candidates = [merged[k] for k in merged]
        date_relaxed = has_date and max_relax != "strict"
        meta["layer_counts"] = {m: order.count(m) for m in set(order)}
        return candidates, date_relaxed, meta

    # 所有策略 0 行 → 最终兜底：纯时间倒序，交给打分层过滤
    rows = _fetch_rows(dict(cond, keywords=[]), lv_kw, None)
    meta["match_mode"] = "latest"
    meta["relax_level"] = "latest"
    return rows, has_date, meta


def _fetch_rows(cond: Dict[str, Any], lv: Dict[str, bool],
                match: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按一层策略取候选。match: {"kind":"ft","cols":[...],"expr":...} / {"kind":"like"} / None(纯最新)。
    严禁 SELECT content / content_text 大列（snippet 只取 LEFT 前 400 字）。"""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        where = ["b.status = 1"]
        params: Dict[str, Any] = {}
        rank_expr_parts = []
        keywords = cond.get("keywords") or []
        ft_expr = None

        if match and match["kind"] == "ft":
            ft_expr = match["expr"]
            match_cols = ", ".join(f"b.`{c}`" for c in match["cols"])
            where.append(f"MATCH({match_cols}) AGAINST(:ft IN BOOLEAN MODE) > 0")
            params["ft"] = ft_expr
        elif match and match["kind"] == "like":
            # LIKE 兜底层同样带上 synonyms（地区展开词/同义词），避免口语区域词召回过少
            words = list(keywords)
            for s in cond.get("synonyms") or []:
                if s and s not in words:
                    words.append(s)
            keywords = words[:10]
            for i, kw in enumerate(keywords):
                params[f"kw{i}"] = f"%{kw}%"
                rank_expr_parts.append(
                    f"(CASE WHEN b.title LIKE :kw{i} THEN 2 ELSE 0 END"
                    f" + CASE WHEN b.content_text LIKE :kw{i} THEN 1 ELSE 0 END)"
                )
            if keywords:
                where.append("(" + " OR ".join(
                    f"b.title LIKE :kw{i} OR b.content_text LIKE :kw{i}"
                    for i in range(len(keywords))
                ) + ")")
        # match 为 None → 纯最新，无关键词条件

        rank_expr = " + ".join(rank_expr_parts) if rank_expr_parts else ""

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

        if ft_expr:
            # 用别名排序（WHERE 里已有同一表达式）；MATCH 列必须与索引列一致
            order_clause = "ft_rank DESC, b.publish_time DESC"
            ft_select = f", MATCH({match_cols}) AGAINST(:ft IN BOOLEAN MODE) AS ft_rank"
        else:
            order_clause = (f"({rank_expr}) DESC, b.publish_time DESC"
                            if rank_expr else "b.publish_time DESC")
            ft_select = ""
        sql = text(f"""
            SELECT b.id, b.title, b.tenderee, b.agency, b.procure_type,
                   b.publish_time, b.deadline, b.budget, b.winner_unit,
                   b.region_code, b.source_url,
                   COALESCE(r.name, '') AS region_name,
                   COALESCE(nt.name, '') AS notice_type,
                   LEFT(COALESCE(b.content_text, ''), 400) AS snippet
                   {ft_select}
            FROM bid_info b
            LEFT JOIN dict_region r ON r.code = b.region_code
            LEFT JOIN dict_notice_type nt ON nt.id = b.notice_type_id
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
#  4. DeepSeek 语义打分（分批并行，单批失败只降级该批）
# ---------------------------------------------------------------- #

SCORE_PROMPT = """你是标讯（招投标公告）相关性评分员。根据用户的检索意图与限定条件，给每条候选公告打 0~100 分。

候选已通过关键词预筛，多数与主题有一定关系，请拉开档位合理区分，不要一律给低分。

评分标准（按最吻合的维度给分，再按偏差扣分）：
- 90~100：主题完全吻合，且地区、公告类型、时间等限定条件也吻合，就是用户要找的
- 75~89：核心主题吻合，仅个别条件有轻微偏差
- 60~74：主题基本吻合，但地区或公告类型等条件有明显偏差（仍应展示）
- 40~59：仅部分相关（沾边的关键词命中，核心意图偏离）
- 0~39：基本无关

扣分参考：地区不符 −15；公告类型不符 −10；时间不符 −10（用户未限定的维度不扣分）。
注意：主题是先决条件——用户的核心意图（关键词）不吻合的条目，无论地区、类型多吻合都必须低于 60 分；只有主题吻合的条目才用地区/类型等条件微调档位，不要因为地区吻合就给主题无关的条目 60 分以上。

档位分布提示：主题相关且至少一项限定条件吻合的候选应落在 60~74；关键词仅沾边、核心意图偏离的才放 40~59。不要把大部分候选压到 40 分以下，每批都应区分出相对优劣。

只输出 JSON 对象，格式：{"results":[{"id": 1, "score": 88}, {"id": 2, "score": 45}]}，不要理由、不要任何其他文字。"""


def _lib_date_note() -> Tuple[str, str]:
    """查库内 publish_time 范围（缓存 600s）。返回 (范围串, 打分提示)。"""
    cache = _lib_date_note.__dict__
    now = time.time()
    if cache.get("range") is not None and now - cache.get("t", 0) < LIB_DATE_CACHE_S:
        return cache["range"], cache["note"]
    range_str, note = "", ""
    try:
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            row = db.execute(text(
                "SELECT MIN(publish_time), MAX(publish_time) FROM bid_info WHERE status = 1"
            )).fetchone()
            if row and row[0]:
                mn, mx = str(row[0])[:10], str(row[1])[:10]
                range_str = f"{mn}~{mx}"
                note = (f"\n注意：用户要求的时间段与库内数据范围（{range_str}）不完全重合。"
                        f"日期不吻合时按主题、地区、公告类型的相关性给分，最多扣 10 分，"
                        f"不要因日期直接打低分。")
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[ai_search] 查库内日期范围失败: {e}")
    _lib_date_note.__dict__.update(t=now, range=range_str, note=note)
    return range_str, note


def _to_score(v: Any) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def _cond_note(cond: Optional[Dict[str, Any]]) -> str:
    """把转译出的结构化限定条件拼成打分提示（未限定的维度不提，避免误扣分）。"""
    if not cond:
        return ""
    parts = []
    if cond.get("region_name"):
        parts.append(f"地区限定={cond['region_name']}")
    if cond.get("notice_type"):
        parts.append(f"公告类型限定={cond['notice_type']}")
    if cond.get("procure_type"):
        parts.append(f"采招方式限定={cond['procure_type']}")
    if cond.get("date_from") or cond.get("date_to"):
        parts.append(f"时间限定={cond.get('date_from') or '不限'}~{cond.get('date_to') or '不限'}")
    if cond.get("budget_min") is not None:
        parts.append(f"预算≥{cond['budget_min']}万")
    if cond.get("budget_max") is not None:
        parts.append(f"预算≤{cond['budget_max']}万")
    if not parts:
        return ""
    return "\n用户限定条件（只对这些维度扣分）：" + "；".join(parts)


def _score_batch(query: str, batch: List[Dict[str, Any]], date_note: str,
                 cond_note: str = "") -> List[Dict[str, Any]]:
    """对一个批次（SCORING_CHUNK 条）调用 LLM 打分；失败抛异常由调用方按批降级。"""
    from app.services.llm import chat_json
    model_cfg = svc.get_model("search")
    prompt = svc.get_prompt("prompt.search_score", SCORE_PROMPT)
    items = [
        {"id": c["id"], "title": c["title"],
         "snippet": (c.get("snippet") or "")[:80],
         "notice_type": c.get("notice_type"),
         "region": c.get("region_name")}
        for c in batch
    ]
    scores = chat_json(
        [
            {"role": "system", "content": prompt},
            {"role": "user", "content":
                f"用户检索意图：{query}{cond_note}{date_note}\n\n候选公告 JSON：\n"
                + json.dumps(items, ensure_ascii=False)},
        ],
        expect="array",
        json_mode=True,
        temperature=0,
        max_tokens=2000,
        timeout=60,
        tag="score",
        model_override=model_cfg.get("model"),
        base_url_override=model_cfg.get("base_url"),
        api_key_override=model_cfg.get("api_key"),
    )
    by_id = {int(s["id"]): s for s in scores
             if isinstance(s, dict) and s.get("id") is not None}
    out = []
    for c in batch:
        s = by_id.get(c["id"], {})
        out.append({**c, "score": _to_score(s.get("score", 0)),
                    "reason": (s.get("reason") or "")[:120]})
    return out


def score_candidates(query: str, candidates: List[Dict[str, Any]],
                     date_relaxed: bool = False,
                     cond: Optional[Dict[str, Any]] = None,
                     score_cap: Optional[int] = None,
                     ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """分批并行调用 DeepSeek 打分。单批失败只对该批降级本地分并计数。
    score_cap：送 LLM 打分的候选上限（先用本地关键词粗排取 Top，控制 token 成本）。
    返回 (按分数降序的完整结果, 诊断 {batch_failures, llm_score_ok})。"""
    if not candidates:
        return [], {"batch_failures": 0, "llm_score_ok": False}
    model_cfg = svc.get_model("search")
    if not (model_cfg.get("api_key") or settings.deepseek_api_key):
        return _local_score(query, candidates), {"batch_failures": 0, "llm_score_ok": False}

    cap = score_cap or SCORE_CAP
    if len(candidates) > cap:
        # 本地关键词粗排，只把最相关的一批送 LLM（召回池仍是 120，不打折召回）
        candidates = _local_score(query, candidates)[:cap]

    date_note = ""
    if date_relaxed:
        _, date_note = _lib_date_note()
    cond_note = _cond_note(cond)

    batches = [candidates[i:i + SCORING_CHUNK]
               for i in range(0, len(candidates), SCORING_CHUNK)]
    batch_results: List[Optional[List[Dict[str, Any]]]] = [None] * len(batches)
    batch_failures = 0

    with ThreadPoolExecutor(max_workers=SCORE_WORKERS) as ex:
        futs = {ex.submit(_score_batch, query, b, date_note, cond_note): i
                for i, b in enumerate(batches)}
        for fut in as_completed(futs):
            i = futs[fut]
            try:
                batch_results[i] = fut.result()
            except Exception as e:  # noqa: BLE001
                batch_failures += 1
                logger.warning(f"[ai_search] 打分批次 {i + 1}/{len(batches)} 失败，本地降级: {e}")
                batch_results[i] = _local_score(query, batches[i])

    results: List[Dict[str, Any]] = []
    for br in batch_results:
        results.extend(br or [])
    results.sort(key=lambda x: x["score"], reverse=True)
    return results, {"batch_failures": batch_failures, "llm_score_ok": batch_failures == 0}


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
#  5. 预算软过滤（budget 是 String(64)，只能在打分前过滤）
# ---------------------------------------------------------------- #

def _apply_budget_filter(cond: Dict[str, Any],
                         candidates: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    bmin, bmax = cond.get("budget_min"), cond.get("budget_max")
    if bmin is None and bmax is None:
        return candidates, 0
    kept: List[Dict[str, Any]] = []
    dropped = 0
    for c in candidates:
        v = parse_budget_wan(c.get("budget"))
        if v is None:
            kept.append(c)      # 解析失败的保留，交打分层判断
            continue
        if bmax is not None and v > float(bmax):
            dropped += 1
            continue
        if bmin is not None and v < float(bmin):
            dropped += 1
            continue
        kept.append(c)
    return kept, dropped


# ---------------------------------------------------------------- #
#  主流程
# ---------------------------------------------------------------- #

def _count_total(cond: Dict[str, Any]) -> Optional[int]:
    """关键词全量命中数（status=1，不限 LIMIT、不带地区/日期/类型收紧）。

    供前端展示「库里共 N 条含该关键词的标讯，AI 已精排前 M 条」——
    召回层每层 LIMIT CANDIDATE_LIMIT，打分池只是命中集的头部。
    FT 优先（与召回同索引同口径），短词/索引缺失退 LIKE；
    无关键词（纯最新兜底）返回 None，前端不显示该片段。"""
    keywords = cond.get("keywords") or []
    if not keywords:
        return None
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        cols = _ft_columns()
        expr: Optional[str] = None
        if cols:
            expr, _ = build_ft_query(keywords, "or")
        if cols and expr:
            mc = ", ".join(f"`{c}`" for c in cols)
            sql = text(
                f"SELECT COUNT(*) FROM bid_info WHERE status = 1 AND "
                f"MATCH({mc}) AGAINST(:ft IN BOOLEAN MODE) > 0")
            params: Dict[str, Any] = {"ft": expr}
        else:
            likes = " OR ".join(
                f"(b.title LIKE :kw{i} OR b.content_text LIKE :kw{i})"
                for i in range(len(keywords)))
            sql = text(
                f"SELECT COUNT(*) FROM bid_info b WHERE b.status = 1 "
                f"AND ({likes})")
            params = {f"kw{i}": f"%{kw}%"
                      for i, kw in enumerate(keywords)}
        return int(db.execute(sql, params).scalar() or 0)
    except Exception:
        logger.warning("[ai_search] total_hits 全量统计失败", exc_info=True)
        return None
    finally:
        db.close()


def ai_search(query: str, limit: int = 120,
              score_cap: Optional[int] = None) -> Dict[str, Any]:
    """一次完整 AI 检索：转译 → 召回 → 预算过滤 → 打分 → 分档。

    items 返回全部打分结果（按分数降序，最多 limit 条）：前端默认只展示
    高相关（>=75），点「加载更多」按 60/40/20/0 分档逐级放宽，直到全部显示。
    最高分低于展示底线（FALLBACK_MIN_SCORE）视为真无关 → 返回空列表走空态。
    score_cap：送 LLM 打分的候选条数上限（None=60；对话场景传 24 更省）。
    """
    t0 = time.time()
    cond, llm_translate_ok = translate_query(query)
    candidates, date_relaxed, meta = search_candidates(cond)
    candidates, budget_dropped = _apply_budget_filter(cond, candidates)
    scored, score_diag = score_candidates(query, candidates, date_relaxed=date_relaxed,
                                          cond=cond, score_cap=score_cap)

    if scored and scored[0]["score"] < FALLBACK_MIN_SCORE:
        # 真无关（最高分都不到展示底线）→ 空态，不给用户看垃圾
        items_out: List[Dict[str, Any]] = []
        fallback_used = False
    elif scored and scored[0]["score"] < MID_SCORE:
        # 兜底：没有 60+ 的结果，只给最接近的 10 条（前端标「兜底参考」并全量展示）
        items_out = scored[:min(10, limit)]
        fallback_used = True
    else:
        items_out = scored[:limit]
        fallback_used = False
    high_count = sum(1 for s in items_out if s["score"] >= HIGH_SCORE)
    mid_count = sum(1 for s in items_out if MID_SCORE <= s["score"] < HIGH_SCORE)
    lib_range, _ = _lib_date_note()
    total_hits = _count_total(cond)   # 关键词全量命中数（前端显示真实总数）

    return {
        "items": items_out,
        "translated": dict(cond),
        "date_relaxed": date_relaxed,
        "candidate_count": len(candidates),
        "passed_count": len(items_out),
        "total_hits": total_hits,
        "cost_ms": int((time.time() - t0) * 1000),
        "high_count": high_count,
        "mid_count": mid_count,
        "fallback_used": fallback_used,
        "diagnostics": {
            "match_mode": meta["match_mode"],
            "relax_level": meta["relax_level"],
            "dropped_short": meta.get("dropped_short") or [],
            "budget_dropped": budget_dropped,
            "top_score": scored[0]["score"] if scored else 0,
            "batch_failures": score_diag["batch_failures"],
            "library_date_range": lib_range,
            "llm_translate_ok": llm_translate_ok,
            "llm_score_ok": score_diag["llm_score_ok"],
        },
    }
