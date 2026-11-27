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
from app.redis_client import cache_get, cache_set, cache_key
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

from app.config import settings
from app.services import ai_setting_service as svc
from app.services.data_clean import parse_budget_wan

logger = logging.getLogger(__name__)

HIGH_SCORE = 70        # >= 此分：高度相关
MID_SCORE = 60         # 60~69：较相关，辅助展示；<60 丢弃
# 相关性四维权重（总分 100）：主题40 / 地区25 / 类型20 / 时间15
W_TOPIC, W_REGION, W_TYPE, W_TIME = 40, 25, 20, 15
# 语义向量召回
SEMANTIC_TOPN = 60        # 每次语义召回的 TopN（与关键词候选求并集）
SEMANTIC_MIN_SIM = 0.30   # 语义召回最低余弦相似度，低于此不并入
CANDIDATE_LIMIT = 200  # 召回池上限（DB 粗筛）—— 扩大召回范围
SCORE_CAP = 100        # 默认送 LLM 打分的候选上限 —— 扩大 LLM 打分范围
MIN_CANDIDATES = 40    # 单层召回不足此数则继续放宽并累积合并（避免首层非空即停导致召回过少）
FALLBACK_MIN_SCORE = 40  # 兜底展示的分数线：最高分低于此值视为真无关，返回空态而非垃圾
SCORING_CHUNK = 25     # 每次打分调用的候选批量 —— 减小批次提高并行度
SCORE_WORKERS = 4      # 打分批次并行度 —— 提高并行度

FT_INDEX_CACHE_S = 300   # FULLTEXT 索引存在性探测缓存
LIB_DATE_CACHE_S = 600   # 库内日期范围缓存

# 大区/口语区域 → 覆盖地区的国标码前缀（省用 2 位，市用 4 位）
# 用于把「华南/珠三角」这类宏观词落成可判定的地区约束，供地区维度精确判分。
REGION_GROUPS: Dict[str, Tuple[str, List[str]]] = {
    "华南": ("华南", ["44", "45", "46", "81", "82"]),            # 广东 广西 海南 香港 澳门
    "华东": ("华东", ["31", "32", "33", "34", "35", "36", "37"]),  # 沪苏浙皖闽赣鲁
    "华北": ("华北", ["11", "12", "13", "14", "15"]),            # 京津冀晋蒙
    "华中": ("华中", ["41", "42", "43"]),                        # 豫鄂湘
    "西北": ("西北", ["61", "62", "63", "64", "65"]),            # 陕甘青宁新
    "西南": ("西南", ["50", "51", "52", "53", "54"]),            # 渝川贵云藏
    "东北": ("东北", ["21", "22", "23"]),                        # 辽吉黑
    "珠三角": ("珠三角", ["4401", "4403", "4404", "4406", "4407", "4412", "4413", "4419", "4420"]),
    "长三角": ("长三角", ["31", "3201", "3202", "3205", "3301", "3302"]),
    "京津冀": ("京津冀", ["11", "12", "1301"]),
    "粤北": ("粤北", ["4402", "4418", "4453"]),                  # 韶关 清远 云浮
    "粤东": ("粤东", ["4405", "4451", "4452", "4415"]),          # 汕头 潮州 揭阳 汕尾
    "粤西": ("粤西", ["4408", "4409", "4417"]),                  # 湛江 茂名 阳江
}


def _detect_region_group(query: str) -> Optional[Tuple[str, List[str]]]:
    """从用户原句里识别大区/口语区域词，返回 (显示名, 地区码前缀列表)；没命中返回 None。"""
    q = query or ""
    for name in sorted(REGION_GROUPS, key=len, reverse=True):  # 长词优先，避免"粤东"被"东"类干扰
        if name in q:
            return REGION_GROUPS[name]
    return None


# ---------------------------------------------------------------- #
#  1. 大白话 → 结构化检索条件
# ---------------------------------------------------------------- #

TRANSLATE_PROMPT = """你是标讯（招投标公告）检索系统的查询转译器。把用户的大白话检索意图转译成结构化的 JSON 检索条件。

今天日期：{today}

可用字段与取值规则：
- keywords: string[]，3~6 个核心检索词（保留原意，名词短语，不要含"找/帮我/最近"等虚词）
- synonyms: string[]，2~10 个同义词、上位词或地区展开词（如 学校→中小学、幼儿园、教育局；医院→卫生院、人民医院），用于扩大召回；没有合适的给 []
- 地区概念必须展开：用户提到口语化区域时，keywords 保留概念词本身，synonyms 必须列出该区域覆盖的省市名，让省市名参与召回。常见展开：华南→广东、广西、海南、香港、澳门；华东→上海、江苏、浙江、安徽、福建、江西、山东；华北→北京、天津、河北、山西、内蒙古；华中→河南、湖北、湖南；西北→陕西、甘肃、青海、宁夏、新疆；西南→重庆、四川、贵州、云南、西藏；粤北→韶关、清远、云浮；珠三角→广州、深圳、佛山、东莞、中山、珠海、惠州、江门、肇庆；粤东→汕头、潮州、揭阳、汕尾；粤西→湛江、茂名、阳江；长三角→上海、南京、杭州、苏州、无锡、宁波；京津冀→北京、天津、石家庄；东北→辽宁、吉林、黑龙江
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


# 口语化区域 → 覆盖城市（确定性展开，不依赖 LLM 是否听话；DB Prompt 可另补充）
REGION_ALIAS = {
    "华南": ["广东", "广西", "海南", "香港", "澳门"],
    "华东": ["上海", "江苏", "浙江", "安徽", "福建", "江西", "山东"],
    "华北": ["北京", "天津", "河北", "山西", "内蒙古"],
    "华中": ["河南", "湖北", "湖南"],
    "西北": ["陕西", "甘肃", "青海", "宁夏", "新疆"],
    "西南": ["重庆", "四川", "贵州", "云南", "西藏"],
    "粤北": ["韶关", "清远", "云浮"],
    "珠三角": ["广州", "深圳", "佛山", "东莞", "中山", "珠海", "惠州", "江门", "肇庆"],
    "粤东": ["汕头", "潮州", "揭阳", "汕尾"],
    "粤西": ["湛江", "茂名", "阳江"],
    "长三角": ["上海", "南京", "杭州", "苏州", "无锡", "宁波"],
    "京津冀": ["北京", "天津", "石家庄"],
    "东北": ["沈阳", "大连", "长春", "哈尔滨"],
}


def _expand_region_aliases(query: str, cond: Dict[str, Any]) -> Dict[str, Any]:
    """用户话里出现口语区域词时，把覆盖城市并入 synonyms 参与召回。"""
    blob = (query or "") + " " + " ".join(cond.get("keywords") or [])
    syn = list(cond.get("synonyms") or [])
    for alias, cities in REGION_ALIAS.items():
        if alias in blob:
            for c in cities:
                if c not in syn:
                    syn.append(c)
    cond["synonyms"] = syn[:12]
    return cond


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
    """大白话 → 结构化条件。返回 (条件, LLM 是否成功)。失败降级为纯关键词。
    带 Redis 缓存（TTL 600s），相同 query 直接返回缓存结果。"""
    # 缓存查询
    ck = cache_key("ai_translate", query)
    cached = cache_get(ck)
    if cached is not None:
        logger.debug(f"[ai_search] 转译缓存命中: {query[:30]}")
        return cached, True

    default = _expand_region_aliases(query, _default_cond(query))
    model_cfg = svc.get_model("search")
    if not (model_cfg.get("api_key") or settings.deepseek_api_key):
        return default, False
    try:
        from app.services.llm import chat_json
        prompt = svc.get_prompt("prompt.search_translate", TRANSLATE_PROMPT)
        # 用 replace 而非 format：Prompt 可在 admin 后台编辑，避免用户写入花括号导致格式化异常
        prompt_text = prompt.replace("{today}", _today())
        # 转译是结构化 JSON 提取任务，用 qwen-turbo 加速（比 qwen-plus 快 2~3x）
        translate_model = "qwen-turbo" if model_cfg.get("provider") == "alibaba" else model_cfg.get("model")
        data = chat_json(
            [
                {"role": "system", "content": prompt_text},
                {"role": "user", "content": query},
            ],
            expect="object",
            temperature=0,
            timeout=15,
            json_mode=True,
            tag="translate",
            model_override=translate_model,
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
        result = _expand_region_aliases(query, data)
        # 写入缓存
        cache_set(ck, result, ttl=600)
        return result, True
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


def search_candidates(cond: Dict[str, Any], query: str = ""
                      ) -> Tuple[List[Dict[str, Any]], bool, Dict[str, Any]]:
    """按条件粗筛候选。
    
    【优化】region/date/type/group 已改为软过滤（加权排序），不再硬剔除。
    策略简化为：ft_or_exp(+同义词) → like_or 兜底 → latest 纯最新
    返回 (候选列表, 是否放宽了日期, 诊断 meta)。"""
    keywords = cond.get("keywords") or []
    synonyms = cond.get("synonyms") or []
    has_date = bool(cond.get("date_from") or cond.get("date_to"))
    
    # lv 参数已无实际意义（软过滤不依赖它），保留空 dict 兼容接口
    _lv = {}

    meta: Dict[str, Any] = {"match_mode": "latest", "relax_level": "latest",
                            "dropped_short": []}

    strategies: List[Tuple[str, Dict[str, bool], Optional[Dict[str, Any]], str]] = []
    ft_cols = _ft_columns()
    
    if ft_cols and keywords:
        or_expr, dropped1 = build_ft_query(keywords, "or")
        exp_expr, dropped2 = build_ft_query(keywords, "or", extra=synonyms)
        meta["dropped_short"] = sorted(set(dropped1 + dropped2))
        
        if or_expr:
            ft_match = {"kind": "ft", "cols": ft_cols}
            # 优先用带同义词的扩展查询
            if exp_expr and exp_expr != or_expr:
                strategies.append(("ft_or_exp", _lv, dict(ft_match, expr=exp_expr), "soft"))
            strategies.append(("ft_or", _lv, dict(ft_match, expr=or_expr), "soft"))
            # FT 无结果 → LIKE 兜底
            strategies.append(("like_or", _lv, {"kind": "like"}, "like"))
        else:
            meta["match_mode"] = "like"
            strategies.append(("like_or", _lv, {"kind": "like"}, "like"))
    else:
        # 索引缺失 / 无关键词 → LIKE
        meta["match_mode"] = "like"
        strategies.append(("like_or", _lv, {"kind": "like"}, "like"))

    # 逐层累积
    merged: Dict[int, Dict[str, Any]] = {}
    order: List[str] = []
    first_mode = strategies[0][0] if strategies else "latest"
    
    for mode, lv, match, relax in strategies:
        rows = _fetch_rows(cond, lv, match)
        for r in rows:
            if r["id"] not in merged:
                merged[r["id"]] = r
                order.append(mode)
        if len(merged) >= MIN_CANDIDATES:
            break

    if merged:
        meta["match_mode"] = first_mode
        meta["relax_level"] = "soft"
        candidates = [merged[k] for k in merged]
        meta["layer_counts"] = {m: order.count(m) for m in set(order)}
        candidates, sem_meta = _augment_with_semantic(candidates, cond, query)
        meta.update(sem_meta)
        return candidates, False, meta

    # 所有策略 0 行 → 最终兜底：纯时间倒序
    rows = _fetch_rows(dict(cond, keywords=[]), _lv, None)
    meta["match_mode"] = "latest"
    meta["relax_level"] = "latest"
    rows, sem_meta = _augment_with_semantic(rows, cond, query)
    meta.update(sem_meta)
    return rows, has_date, meta


def _fetch_rows(cond: Dict[str, Any], lv: Dict[str, bool],
                match: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按一层策略取候选。match: {"kind":"ft","cols":[...],"expr":...} / {"kind":"like"} / None(纯最新)。
    严禁 SELECT content / content_text 大列（snippet 只取 LEFT 前 400 字）。
    
    【优化】region/date/type/group 改为软过滤（加权排序），不再硬剔除。"""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        where = ["b.status = 1"]
        params: Dict[str, Any] = {}
        rank_expr_parts = []
        keywords = cond.get("keywords") or []
        ft_expr = None
        
        # ===== 关键词匹配（硬过滤）=====
        if match and match["kind"] == "ft":
            ft_expr = match["expr"]
            match_cols = ", ".join(f"b.`{c}`" for c in match["cols"])
            where.append(f"MATCH({match_cols}) AGAINST(:ft IN BOOLEAN MODE) > 0")
            params["ft"] = ft_expr
        elif match and match["kind"] == "like":
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

        # ===== 软过滤加权（region/date/type/group）=====
        # 地区匹配加分
        code = str(cond.get("region_code") or "").strip()
        if len(code) == 6 and code.isdigit():
            if code.endswith("0000"):
                params["_rp"] = code[:2] + "%"
                rank_expr_parts.append("(CASE WHEN b.region_code LIKE :_rp THEN 5 ELSE 0 END)")
            elif code.endswith("00"):
                params["_rp"] = code[:4] + "%"
                rank_expr_parts.append("(CASE WHEN b.region_code LIKE :_rp THEN 5 ELSE 0 END)")
            else:
                params["_rp"] = code
                rank_expr_parts.append("(CASE WHEN b.region_code = :_rp THEN 5 ELSE 0 END)")
        
        # 日期范围加分
        if cond.get("date_from"):
            params["_df"] = cond["date_from"]
            rank_expr_parts.append("(CASE WHEN b.publish_time >= :_df THEN 3 ELSE 0 END)")
        if cond.get("date_to"):
            params["_dt"] = cond["date_to"] + " 23:59:59"
            rank_expr_parts.append("(CASE WHEN b.publish_time <= :_dt THEN 3 ELSE 0 END)")
        
        # 公告类型加分
        if cond.get("notice_type"):
            nid = _notice_type_id(cond["notice_type"])
            if nid:
                params["_nt"] = nid
                rank_expr_parts.append("(CASE WHEN b.notice_type_id = :_nt THEN 4 ELSE 0 END)")
        
        # 招采类型加分
        if cond.get("procure_type"):
            params["_pt"] = f"%{cond['procure_type']}%"
            rank_expr_parts.append("(CASE WHEN b.procure_type LIKE :_pt THEN 3 ELSE 0 END)")
        
        # 客群加分
        if cond.get("customer_group"):
            params["_cg"] = cond["customer_group"]
            rank_expr_parts.append("(CASE WHEN b.customer_group = :_cg THEN 2 ELSE 0 END)")
        
        # ===== 预算过滤（保留硬过滤，因为超出预算的结果无意义）=====
        if cond.get("budget_min") is not None:
            where.append("b.budget >= :bmin")
            params["bmin"] = cond["budget_min"] * 10000
        if cond.get("budget_max") is not None:
            where.append("b.budget <= :bmax")
            params["bmax"] = cond["budget_max"] * 10000

        # ===== 构建 ORDER BY =====
        rank_expr = " + ".join(rank_expr_parts) if rank_expr_parts else ""
        if ft_expr:
            ft_select = f", MATCH({match_cols}) AGAINST(:ft IN BOOLEAN MODE) AS ft_rank"
            if rank_expr:
                order_clause = f"(ft_rank + {rank_expr}) DESC, b.publish_time DESC"
            else:
                order_clause = "ft_rank DESC, b.publish_time DESC"
        else:
            order_clause = f"({rank_expr}) DESC, b.publish_time DESC" if rank_expr else "b.publish_time DESC"
            ft_select = ""
        
        sql = text(f"""
            SELECT b.id, b.title, b.tenderee, b.agency, b.procure_type,
                   b.publish_time, b.deadline, b.budget, b.winner_unit, b.project_code,
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
#  3.5 语义向量召回（关键词 ∪ 向量 TopN）
# ---------------------------------------------------------------- #

def _semantic_enabled() -> bool:
    """语义召回开关（后台 param.search_semantic_recall，缺省开启）。"""
    try:
        return bool(svc.get("param.search_semantic_recall", True))
    except Exception:
        return True


def _fetch_bids_by_ids(ids: List[int]) -> List[Dict[str, Any]]:
    """按 id 批量取候选（字段与 _fetch_rows 一致），供语义召回补入关键词缺口。"""
    if not ids:
        return []
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        in_clause = ", ".join(f":id{i}" for i in range(len(ids)))
        params = {f"id{i}": int(v) for i, v in enumerate(ids)}
        sql = text(f"""
            SELECT b.id, b.title, b.tenderee, b.agency, b.procure_type,
                   b.publish_time, b.deadline, b.budget, b.winner_unit, b.project_code,
                   b.region_code, b.source_url,
                   COALESCE(r.name, '') AS region_name,
                   COALESCE(nt.name, '') AS notice_type,
                   LEFT(COALESCE(b.content_text, ''), 400) AS snippet
            FROM bid_info b
            LEFT JOIN dict_region r ON r.code = b.region_code
            LEFT JOIN dict_notice_type nt ON nt.id = b.notice_type_id
            WHERE b.status = 1 AND b.id IN ({in_clause})
        """)
        rows = db.execute(sql, params).mappings().all()
        return [dict(r) for r in rows]
    finally:
        db.close()


def _augment_with_semantic(candidates: List[Dict[str, Any]], cond: Dict[str, Any],
                           query: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """向量语义召回：取语义 TopN 与关键词候选求并集，并给每条候选挂上 _sim（余弦）。
    失败/未建库/关闭时静默降级为纯关键词，不影响主流程。"""
    if not query or not _semantic_enabled():
        return candidates, {"semantic_enabled": False}
    try:
        from app.services import embedding_service as emb
        cand_ids = [c["id"] for c in candidates]
        ordered, sim_by_id = emb.semantic_recall(query, SEMANTIC_TOPN, cand_ids)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[ai_search] 语义召回失败，降级关键词: {e}")
        return candidates, {"semantic_enabled": False}
    if not ordered:
        return candidates, {"semantic_enabled": True, "semantic_added": 0}

    ordered = [i for i in ordered if sim_by_id.get(i, 0.0) >= SEMANTIC_MIN_SIM]
    existing = {c["id"] for c in candidates}
    for c in candidates:
        s = sim_by_id.get(c["id"])
        if s is not None:
            c["_sim"] = s
    missing = [i for i in ordered if i not in existing]
    extra = _fetch_bids_by_ids(missing)
    # 有地区约束时，语义新增候选必须命中地区，否则不并入（避免污染地区限定查询）
    extra = [r for r in extra if _region_match(cond, r.get("region_code")) is not False]
    for r in extra:
        r["_sim"] = sim_by_id.get(r["id"], 0.0)
    return candidates + extra, {"semantic_enabled": True, "semantic_added": len(extra)}


def _dedup_by_project(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按 project_code 合并同一项目的多条公告（招标/中标/更正）。
    保留分数最高的一条，并标注 variant_count（该项目共几条）；无 project_code 的不合并。"""
    if not items:
        return items
    seen: Dict[str, Dict[str, Any]] = {}
    out: List[Dict[str, Any]] = []
    for it in items:  # items 已按分数降序
        pc = str(it.get("project_code") or "").strip()
        if not pc:
            it["variant_count"] = 1
            out.append(it)
            continue
        if pc in seen:
            seen[pc]["variant_count"] = int(seen[pc].get("variant_count", 1)) + 1
            continue
        it["variant_count"] = 1
        seen[pc] = it
        out.append(it)
    return out


# ---------------------------------------------------------------- #
#  4. DeepSeek 语义打分（分批并行，单批失败只降级该批）
# ---------------------------------------------------------------- #

SCORE_PROMPT = """你是标讯相关性评分员。对每条候选公告，分别给出四个维度的吻合度（0~100 的整数），不要自己加权求和，只给分维度。

维度定义（100=完全吻合，0=完全不相关）：
- topic（主题吻合度）：公告标题、采购内容与用户检索主体的匹配程度。完全吻合 95~100；高度相关 75~94；部分相关 45~74；弱相关 10~44；无关 0。
- region（地区吻合度）：公告地区与用户要求地区的吻合度。完全一致 100；同省或相邻 85；同大区 60；不同大区 0。用户未提地区时给 0 即可（系统会忽略此维度）。
- type（公告类型吻合度）：公告类型与用户要求类型的吻合度。一致 100；相近 60；不符 0。用户未提类型时给 0 即可（系统会忽略）。
- time（时间吻合度）：发布日期与用户要求时间段的吻合度。在区间内 100；略有超出 70；明显超出 0。用户未提时间时给 0 即可（系统会忽略）。

只输出 JSON：{"results":[{"id":1,"topic":92,"region":100,"type":90,"time":100}]}"""


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


def _region_match(cond: Optional[Dict[str, Any]], region_code: Any) -> Optional[bool]:
    """判断候选是否落在用户地区约束内。
    True=命中 / False=明确不符或无法确认 / None=用户未限定地区（不判分）。
    大区用前缀集合；精确区划码按层级前缀比对；有约束但候选缺码时判 False（无法确认不算命中）。"""
    if not cond:
        return None
    prefixes = cond.get("region_prefixes")
    code = str(region_code or "").strip()
    if prefixes:
        if not code:
            return False
        return any(code.startswith(p) for p in prefixes)
    rc = str(cond.get("region_code") or "").strip()
    if len(rc) == 6 and rc.isdigit():
        if not code:
            return False
        if rc.endswith("0000"):
            return code.startswith(rc[:2])
        if rc.endswith("00"):
            return code.startswith(rc[:4])
        return code == rc
    return None


def _region_subscore(cond: Optional[Dict[str, Any]], region_code: Any) -> Optional[int]:
    """地区维度确定性命中分：命中 100 / 不符 0 / 无地区约束 None（交给模型）。"""
    m = _region_match(cond, region_code)
    if m is None:
        return None
    return 100 if m else 0


def _compose_score(s: Dict[str, Any], cond: Optional[Dict[str, Any]],
                   cand: Optional[Dict[str, Any]] = None) -> int:
    """把 LLM 返回的四维吻合度按权重合成总分（代码确定性加权，避免模型自求和出错）。
    地区维度：大区词（华南等）已落成地区码前缀，用候选 region_code 精确命中，不依赖模型。
    用户未限定的维度直接计满分权重；主题无关/地区不符时按硬规则压分。"""
    if s.get("score") is not None and s.get("topic") is None:
        return _to_score(s.get("score"))   # 兼容旧格式（直接给了总分）

    def _v(k: str) -> int:
        try:
            return max(0, min(100, int(float(s.get(k, 0)))))
        except (TypeError, ValueError):
            return 0

    topic = _v("topic")
    total = topic / 100 * W_TOPIC

    has_region = bool(cond and (cond.get("region_code") or cond.get("region_name")
                                or cond.get("region_prefixes")))
    has_type = bool(cond and cond.get("notice_type"))
    has_time = bool(cond and (cond.get("date_from") or cond.get("date_to")))

    region_zero = False
    if has_region:
        rs = _region_subscore(cond, (cand or {}).get("region_code"))
        rv = rs if rs is not None else _v("region")
        total += rv / 100 * W_REGION
        region_zero = (rv == 0)
    else:
        total += W_REGION

    total += (_v("type") / 100 * W_TYPE) if has_type else W_TYPE
    total += (_v("time") / 100 * W_TIME) if has_time else W_TIME
    total = int(round(total))

    if topic == 0:
        total = min(total, 25)
    if has_region and region_zero:
        total = min(total, 60)
    return max(0, min(100, total))


def _score_batch(query: str, batch: List[Dict[str, Any]], date_note: str,
                 cond_note: str = "", cond: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """对一个批次（SCORING_CHUNK 条）调用 LLM 打四维分；失败抛异常由调用方按批降级。"""
    from app.services.llm import chat_json
    model_cfg = svc.get_model("search")
    prompt = svc.get_prompt("prompt.search_score", SCORE_PROMPT)
    items = [
        {"id": c["id"], "title": c["title"],
         "snippet": (c.get("snippet") or "")[:120],
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
        out.append({**c, "score": _compose_score(s, cond, c),
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
        return _local_score(query, candidates, cond), {"batch_failures": 0, "llm_score_ok": False}

    cap = score_cap or SCORE_CAP
    if len(candidates) > cap:
        if any(c.get("_sim") is not None for c in candidates):
            # 混合预排：关键词 Top 70% + 语义 TopN 补齐，保证语义召回结果能进 LLM 打分池
            kw = _local_score(query, candidates, cond)
            n_kw = max(1, int(cap * 0.7))
            pool: List[Dict[str, Any]] = []
            seen: set = set()
            for c in kw[:n_kw]:
                pool.append(c)
                seen.add(c["id"])
            for c in sorted(candidates, key=lambda x: x.get("_sim", -1), reverse=True):
                if len(pool) >= cap:
                    break
                if c["id"] not in seen:
                    pool.append(c)
                    seen.add(c["id"])
            candidates = pool
        else:
            # 本地关键词粗排，只把最相关的一批送 LLM（使用转译后的 keywords + synonyms）
            candidates = _local_score(query, candidates, cond)[:cap]

    date_note = ""
    if date_relaxed:
        _, date_note = _lib_date_note()
    cond_note = _cond_note(cond)

    batches = [candidates[i:i + SCORING_CHUNK]
               for i in range(0, len(candidates), SCORING_CHUNK)]
    batch_results: List[Optional[List[Dict[str, Any]]]] = [None] * len(batches)
    batch_failures = 0

    with ThreadPoolExecutor(max_workers=SCORE_WORKERS) as ex:
        futs = {ex.submit(_score_batch, query, b, date_note, cond_note, cond): i
                for i, b in enumerate(batches)}
        for fut in as_completed(futs):
            i = futs[fut]
            try:
                batch_results[i] = fut.result()
            except Exception as e:  # noqa: BLE001
                batch_failures += 1
                logger.warning(f"[ai_search] 打分批次 {i + 1}/{len(batches)} 失败，本地降级: {e}")
                batch_results[i] = _local_score(query, batches[i], cond)

    results: List[Dict[str, Any]] = []
    for br in batch_results:
        results.extend(br or [])
    results.sort(key=lambda x: x["score"], reverse=True)
    return results, {"batch_failures": batch_failures, "llm_score_ok": batch_failures == 0}


def _local_score(query: str, candidates: List[Dict[str, Any]],
                 cond: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """降级/粗排：本地关键词加权打分。
    优先使用 LLM 转译后的 keywords + synonyms，失败时用原始 query 分词。"""
    # 优先用转译后的关键词
    if cond:
        kws = list(cond.get("keywords") or []) + list(cond.get("synonyms") or [])
    else:
        kws = _fallback_keywords(query)
    kws = [k for k in kws if len(k) >= 2][:12]  # 去空、限长

    out = []
    for c in candidates:
        text_blob = (c["title"] or "") + " " + (c.get("snippet") or "")
        text_lower = text_blob.lower()
        # 标题命中权重更高
        title_lower = (c.get("title") or "").lower()
        hits = sum(2 for k in kws if k.lower() in title_lower)
        hits += sum(1 for k in kws if k.lower() in text_lower and k.lower() not in title_lower)
        max_hits = len(kws) * 3  # 标题命中满分
        score = int(hits / max_hits * 90) if max_hits else 0
        out.append({**c, "score": score, "reason": "本地关键词匹配"})
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
    带 Redis 缓存（TTL 300s），相同 query+limit 直接返回缓存结果。
    """
    # 缓存查询
    ck = cache_key("ai_search", query, str(limit), str(score_cap or ""))
    cached = cache_get(ck)
    if cached is not None:
        logger.debug(f"[ai_search] 结果缓存命中: {query[:30]}")
        cached["cost_ms"] = 0
        cached["cache_hit"] = True
        return cached

    t0 = time.time()
    cond, llm_translate_ok = translate_query(query)
    # 大区/口语区域（华南/珠三角…）优先：覆盖转译层可能误设的单省 region_code，改用地区码前缀集合
    grp = _detect_region_group(query)
    if grp:
        cond["region_name"] = grp[0]
        cond["region_prefixes"] = grp[1]
        cond["region_code"] = None
    candidates, date_relaxed, meta = search_candidates(cond, query)
    candidates, budget_dropped = _apply_budget_filter(cond, candidates)
    scored, score_diag = score_candidates(query, candidates, date_relaxed=date_relaxed,
                                          cond=cond, score_cap=score_cap)
    scored = _dedup_by_project(scored)   # 同一项目多条公告合并（招标/中标/更正）

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
    for _it in items_out:      # 不把内部字段 _sim 暴露给前端
        _it.pop("_sim", None)
    high_count = sum(1 for s in items_out if s["score"] >= HIGH_SCORE)
    mid_count = sum(1 for s in items_out if MID_SCORE <= s["score"] < HIGH_SCORE)
    lib_range, _ = _lib_date_note()
    total_hits = _count_total(cond)   # 关键词全量命中数（前端显示真实总数）

    result = {
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
            "semantic_enabled": bool(meta.get("semantic_enabled")),
            "semantic_added": meta.get("semantic_added", 0),
        },
    }
    # 写入缓存（TTL 300s）
    cache_set(ck, result, ttl=300)
    # 记录热门搜索（Redis sorted set，异步不阻塞主流程）
    _record_hot_search(query)
    return result


# ---------------------------------------------------------------- #
#  热门搜索（Redis sorted set）
# ---------------------------------------------------------------- #

_HOT_SEARCH_KEY = "search:hot"
_HOT_SEARCH_MAX = 200  # 最多保留 200 个词


def _record_hot_search(query: str) -> None:
    """把搜索词记入 Redis sorted set（ZINCRBY），失败静默。"""
    q = (query or "").strip()
    if not q or len(q) < 2:
        return
    try:
        from app.redis_client import get_redis
        r = get_redis()
        r.zincrby(_HOT_SEARCH_KEY, 1, q)
        # 保留 top N，避免集合无限膨胀
        r.zremrangebyrank(_HOT_SEARCH_KEY, 0, -_HOT_SEARCH_MAX - 1)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"[ai_search] 记录热门搜索失败: {e}")


def get_hot_searches(limit: int = 10) -> list:
    """返回热门搜索词列表 [{"query": "...", "count": N}, ...]"""
    try:
        from app.redis_client import get_redis
        r = get_redis()
        # ZREVRANGE 按分数降序取 top N，WITHSCORES 返回分数
        items = r.zrevrange(_HOT_SEARCH_KEY, 0, limit - 1, withscores=True)
        return [{"query": q, "count": int(c)} for q, c in items]
    except Exception as e:  # noqa: BLE001
        logger.debug(f"[ai_search] 获取热门搜索失败: {e}")
        return []
