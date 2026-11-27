# -*- coding: utf-8 -*-
"""
DeepSeek 多轮 AI 助手（P2 AI 悬浮球）
======================================
对话流程（借鉴 Dify Chatflow 编排，自行实现，四段管道）：
  ① 记忆窗口：历史按字符预算组装（≤24000 字、至少保留最近 60 条，超预算丢最旧）
  ② 意图分类：规则快判 检索/统计/通用（0 成本 0 延迟；只优化路径不设死门槛，
     误判由 function calling 兜底——所有分支都带工具）
  ③ 分支执行：检索/统计分支注入标讯上下文 + 工具；通用分支不注入上下文
     （省 token、防"闲聊带 30 条标题"错位），工具循环上限 3 轮
  ④ 输出：reply（Markdown）+ results（检索卡片数据）+ tool_calls + truncated

工具（只读，不写库）：
  search_bids   —— ai_search 大白话检索 Top10
  count_bids    —— 按关键词/地区/天数统计条数（status=1，FT/LIKE 口径）
  get_bid_detail—— 单条标讯详情（不取 content_text 大列）

硬边界：不创建/修改/删除数据、不执行代码/SQL、不泄密、不编造库内数据。
DeepSeek 不可用时返回可读提示，不抛 500。
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings
from app.services.llm import achat, achat_stream, LLMError
from app.services.ai_search import ai_search, _ft_columns, build_ft_query
from app.services import ai_setting_service as svc

logger = logging.getLogger(__name__)

# ---- 记忆窗口（①）----
HISTORY_CHAR_BUDGET = 8000    # 历史总字符预算（约 4~5k token，控制对话成本）
HISTORY_MIN_KEEP = 6          # 至少保留最近 N 条（预算内也保证长对话不硬断）

# ---- 工具循环（③）----
TOOL_ROUNDS = 3               # 工具轮上限
TOTAL_DEADLINE_S = 60         # 单次对话总时长预算
MAX_TOKENS = 2000             # 单次回复上限（长对话总结更完整）

# ---- 意图分类词表（②）----
COUNT_TRIGGERS = ("多少条", "几条", "统计", "数量", "新增多少", "共有多少",
                  "总共", "总数", "多少个")
SEARCH_TRIGGERS = ("找", "查", "检索", "搜", "有哪些", "哪些", "招标", "投标",
                   "中标", "采购", "询价", "标讯", "公告", "供应商",
                   "预算", "中标人", "采购人")
BID_WORDS = ("标讯", "招标", "投标", "中标", "采购", "公告", "询价", "供应商")


# ================================================================== #
#  系统提示词（拍板⑥：标讯为主业，通用问题也能答；硬边界只留安全项）
# ================================================================== #

CHAT_SYSTEM_PROMPT = """你是「标讯助手」，服务标讯系统（招投标公告库）的用户：主业标讯，兼答通用问题。

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
3. 库内查询类问题以工具返回为准；不确定的数据明确说"没有查到"，不要编造
"""


# ================================================================== #
#  ① 记忆窗口：按字符预算裁剪历史
# ================================================================== #

def trim_history(messages: List[Dict[str, str]]) -> Tuple[List[Dict[str, str]], bool]:
    """超预算从最旧丢，但至少保留最近 HISTORY_MIN_KEEP 条。
    返回 (裁剪后历史, 是否发生过截断)。"""
    if not messages:
        return [], False
    total = sum(len(m.get("content") or "") for m in messages)
    n = len(messages)
    keep_from = 0
    # 保留至少 HISTORY_MIN_KEEP 条；在此前提下超预算才丢最旧
    while keep_from < n - HISTORY_MIN_KEEP and total > HISTORY_CHAR_BUDGET:
        total -= len(messages[keep_from].get("content") or "")
        keep_from += 1
    return messages[keep_from:], keep_from > 0


# ================================================================== #
#  ② 意图分类：规则快判（只优化路径，不设死门槛）
# ================================================================== #

def classify_intent(text: str) -> str:
    """返回 count | search | general。误判无害：所有分支都带工具兜底。"""
    if any(w in text for w in COUNT_TRIGGERS):
        return "count"
    if any(w in text for w in SEARCH_TRIGGERS):
        return "search"
    return "general"


def _should_inject_context(intent: str, history: List[Dict[str, str]]) -> bool:
    """检索/统计分支注入；通用分支看最近消息是否还在聊标讯（追问"只要合肥的"无触发词）。"""
    if intent in ("search", "count"):
        return True
    recent = " ".join((m.get("content") or "") for m in history[-2:])
    return any(w in recent for w in BID_WORDS)


# ================================================================== #
#  工具定义与实现（只读）
# ================================================================== #

TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_bids",
            "description": "按自然语言条件检索标讯公告库，返回最相关的标讯列表（标题/时间/评分/理由）。"
                           "支持地区、关键词、时间、公告类型、预算等自然语言描述。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string",
                              "description": "检索条件的完整自然语言描述，如：合肥的学校招标，预算100万以内，最近一个月"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "count_bids",
            "description": "统计标讯库中符合条件的公告条数（只统计已发布 status=1）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keywords": {"type": "array", "items": {"type": "string"},
                                 "description": "关键词列表，可为空数组表示不限关键词"},
                    "region": {"type": "string",
                               "description": "地区中文名（如 合肥、安徽、广东省），可省略"},
                    "days": {"type": "integer",
                             "description": "只统计最近 N 天发布的，省略或 0 表示不限"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_bid_detail",
            "description": "按标讯 id 获取单条标讯详情（标题/时间/中标/预算等，不含正文）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "标讯 id"},
                },
                "required": ["id"],
            },
        },
    },
]


def _resolve_region_code(region: str) -> Optional[str]:
    """地区中文名 → 区划代码（先精确，再前缀）。找不到返回 None。"""
    from app.database import SessionLocal
    from sqlalchemy import text
    db = SessionLocal()
    try:
        row = db.execute(text(
            "SELECT code FROM dict_region WHERE name = :n OR name LIKE :p "
            "ORDER BY level LIMIT 1"),
            {"n": region, "p": f"{region}%"}).first()
        return row[0] if row else None
    except Exception:
        logger.warning("[ai_chat] 地区解析失败 region=%s", region, exc_info=True)
        return None
    finally:
        db.close()


def _count_bids_db(keywords: Optional[List[str]], region: Optional[str],
                   days: Optional[int]) -> Dict[str, Any]:
    """关键词/地区/天数统计（status=1）。FT 优先，短词/索引缺失退 LIKE。"""
    from app.database import SessionLocal
    from sqlalchemy import text
    kws = [str(k).strip() for k in (keywords or []) if str(k).strip()][:6]
    conds = ["status = 1"]
    params: Dict[str, Any] = {}
    if region:
        rc = _resolve_region_code(region)
        if rc:
            conds.append("region_code = :rc")
            params["rc"] = rc
    try:
        d = int(days) if days else 0
    except (TypeError, ValueError):
        d = 0
    if d > 0:
        conds.append("publish_time >= DATE_SUB(NOW(), INTERVAL :d DAY)")
        params["d"] = d
    if kws:
        cols = _ft_columns()
        expr = None
        if cols:
            expr, _ = build_ft_query(kws, "or")
        if cols and expr:
            mc = ", ".join(f"`{c}`" for c in cols)
            conds.append(f"MATCH({mc}) AGAINST(:ft IN BOOLEAN MODE) > 0")
            params["ft"] = expr
        else:
            likes = " OR ".join(
                f"(title LIKE :kw{i} OR content_text LIKE :kw{i})"
                for i in range(len(kws)))
            conds.append(f"({likes})")
            for i, kw in enumerate(kws):
                params[f"kw{i}"] = f"%{kw}%"
    db = SessionLocal()
    try:
        sql = text(f"SELECT COUNT(*) FROM bid_info WHERE {' AND '.join(conds)}")
        total = int(db.execute(sql, params).scalar() or 0)
        return {"total": total, "keywords": kws, "region": region or None,
                "days": d or None}
    finally:
        db.close()


def _get_bid_detail_db(bid_id: int) -> Dict[str, Any]:
    """单条标讯详情（不取 content/content_text 大列）。"""
    from app.database import SessionLocal
    from sqlalchemy import text
    db = SessionLocal()
    try:
        row = db.execute(text(
            "SELECT b.id, b.title, b.project_code, b.tenderee, b.agency, "
            "       b.publish_time, b.deadline, b.budget, b.winner_unit, "
            "       b.win_amount, b.procure_type, b.customer_group, b.source_url, "
            "       nt.name AS notice_type, dr.name AS region_name "
            "FROM bid_info b "
            "LEFT JOIN dict_notice_type nt ON nt.id = b.notice_type_id "
            "LEFT JOIN dict_region dr ON dr.code = b.region_code "
            "WHERE b.id = :id AND b.status = 1"), {"id": bid_id}).first()
        if not row:
            return {"error": f"未找到 id={bid_id} 的已发布标讯"}
        d = dict(row._mapping)
        for k in ("publish_time", "deadline"):
            if d.get(k) is not None:
                d[k] = str(d[k])
        if d.get("win_amount") is not None:
            d["win_amount"] = float(d["win_amount"])
        return d
    finally:
        db.close()


async def _exec_tool(name: str, args: Dict[str, Any],
                     results_acc: List[Dict[str, Any]]) -> Dict[str, Any]:
    """执行单个工具，返回给模型的 JSON 可序列化结果；检索结果同步收集给前端。"""
    try:
        if name == "search_bids":
            query = str(args.get("query") or "").strip()
            if not query:
                return {"error": "query 不能为空"}
            # ai_search 内含 LLM 转译+打分，线程池执行避免阻塞事件循环
            # score_cap=24：对话场景只要 Top 几条，不必按检索页的 60 条打分（省 token）
            data = await asyncio.to_thread(ai_search, query, 10, 24)
            items = data.get("items") or []
            brief = [{
                "id": it.get("id"),
                "title": it.get("title"),
                "publish_time": it.get("publish_time"),
                "score": it.get("score"),
            } for it in items]
            for b in brief:
                if len(results_acc) >= 10:
                    break
                if all(x.get("id") != b["id"] for x in results_acc):
                    results_acc.append(b)
            out: Dict[str, Any] = {"items": brief, "count": len(brief)}
            if data.get("total_hits") is not None:
                out["total_hits"] = data.get("total_hits")
            return out
        if name == "count_bids":
            return await asyncio.to_thread(
                _count_bids_db,
                keywords=args.get("keywords"),
                region=args.get("region"),
                days=args.get("days"),
            )
        if name == "get_bid_detail":
            try:
                bid_id = int(args.get("id"))
            except (TypeError, ValueError):
                return {"error": "id 必须是整数"}
            return await asyncio.to_thread(_get_bid_detail_db, bid_id)
        return {"error": f"unknown tool {name}"}
    except Exception as e:  # noqa: BLE001
        logger.warning("[ai_chat] 工具执行失败 tool=%s: %s", name, e, exc_info=True)
        return {"error": f"工具执行失败：{str(e)[:120]}"}


# ================================================================== #
#  主入口：多轮对话（四段管道）
# ================================================================== #

async def ai_chat(
    messages: List[Dict[str, str]],
    inject_context: bool = True,
) -> Dict[str, Any]:
    """多轮 AI 助手对话。返回 {reply, results, tool_calls, truncated}。

    - ① 记忆窗口裁剪历史
    - ② 规则意图分类
    - ③ 分支：检索/统计注入标讯上下文；所有分支带工具（误判兜底），循环 ≤3 轮
    - ④ 结果卡片数据只回传前端，不回历史（省 token；AI 靠文字总结接续追问）
    """
    if not settings.deepseek_api_key:
        return {"reply": "AI 助手未配置 DeepSeek API Key，请联系管理员。",
                "results": [], "tool_calls": [], "truncated": False}

    # ① 记忆窗口
    history, truncated = trim_history(messages)

    # ② 意图分类（取最后一条用户消息）
    last_user = next(
        (m.get("content") or "" for m in reversed(history)
         if m.get("role") == "user"), "")
    intent = classify_intent(last_user)

    # ③ 系统提示词 + （可选）标讯上下文
    system = svc.get_prompt("prompt.chat_system", CHAT_SYSTEM_PROMPT)
    if inject_context and _should_inject_context(intent, history):
        system += "\n\n" + _get_context_snippet()
    llm_messages: List[Dict[str, Any]] = [{"role": "system", "content": system}]
    llm_messages += [{"role": m["role"], "content": m["content"]} for m in history]

    results_acc: List[Dict[str, Any]] = []
    tool_calls_log: List[str] = []
    reply: Optional[str] = None
    deadline = time.time() + TOTAL_DEADLINE_S
    model_cfg = svc.get_model("chat_system")
    max_tokens = svc.get_param_int("param.llm_max_tokens", MAX_TOKENS)
    temperature = svc.get_param_float("param.llm_temperature", 0.0)
    timeout_sec = svc.get_param_float("param.llm_timeout_s", 60.0)

    try:
        for round_i in range(TOOL_ROUNDS + 1):
            remaining = deadline - time.time()
            if remaining <= 5:
                break
            use_tools = round_i < TOOL_ROUNDS
            resp = await achat(
                llm_messages,
                tools=TOOLS if use_tools else None,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=max(5.0, min(timeout_sec, remaining)),
                tag="chat",
                model_override=model_cfg.get("model"),
                base_url_override=model_cfg.get("base_url"),
                api_key_override=model_cfg.get("api_key"),
            )
            tool_calls = resp.tool_calls or []
            if not tool_calls:
                reply = (resp.content or "").strip()
                break
            if not use_tools:
                # 最后一轮仍要工具：不执行，直接让模型凭已有信息作答（下一轮无工具）
                reply = (resp.content or "").strip()
                break
            # 追加 assistant(tool_calls) 再逐个执行
            llm_messages.append({
                "role": "assistant",
                "content": resp.content,
                "tool_calls": tool_calls,
            })
            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name") or ""
                tool_calls_log.append(name)
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                if not isinstance(args, dict):
                    args = {}
                out = await _exec_tool(name, args, results_acc)
                llm_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id"),
                    "content": json.dumps(out, ensure_ascii=False, default=str),
                })
            logger.info("[ai_chat] route=%s round=%d tools=%s", intent,
                        round_i + 1, ",".join(tool_calls_log[-len(tool_calls):]))
        else:
            # TOOL_ROUNDS+1 次调用仍未收敛（防御，正常不会走到）
            reply = "⚠️ 对话轮次过多，请换个更简单的问法。"

        if not reply:
            if time.time() >= deadline:
                reply = "⚠️ 本次对话耗时过长，请稍后重试，或把问题拆简单一点。"
            else:
                reply = "⚠️ AI 未返回内容，请重试。"
    except LLMError as e:
        logger.warning("[ai_chat] LLM error kind=%s: %s", e.kind, e)
        reply = f"AI 暂时不可用：{str(e)[:80]}"
    except Exception as e:  # noqa: BLE001
        logger.exception("[ai_chat] 对话异常: %s", e)
        reply = "AI 服务暂时不可用，请稍后再试。"

    return {
        "reply": reply,
        "results": results_acc,
        "tool_calls": tool_calls_log,
        "truncated": truncated,
    }


# ================================================================== #
#  标讯上下文注入（防幻觉：最新 30 条标题，只读）+ TTL 60s 缓存
# ================================================================== #

_CONTEXT_CACHE: Dict[str, Any] = {"data": "", "ts": 0.0}
_CONTEXT_CACHE_TTL = 60


def _get_context_snippet() -> str:
    """取最新 30 条标讯标题/时间/中标人，拼成简短上下文（60s TTL）。"""
    now = time.time()
    cached = _CONTEXT_CACHE.get("ts") or 0
    if now - cached < _CONTEXT_CACHE_TTL and _CONTEXT_CACHE["data"]:
        return _CONTEXT_CACHE["data"]
    try:
        from app.database import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        try:
            rows = db.execute(text(
                "SELECT id, title, publish_time, winner_unit FROM bid_info "
                "WHERE status = 1 ORDER BY publish_time DESC LIMIT 30"
            )).fetchall()
        finally:
            db.close()
        lines = []
        for r in rows:
            t = str(r[2])[:10] if r[2] else "未知日期"
            w = f"｜中标：{r[3]}" if r[3] else ""
            lines.append(f"- [{r[0]}] {r[1]}（{t}）{w}")
        snippet = ""
        if lines:
            snippet = ("【库内最新标讯（仅参考，真实查询请调用工具）】\n"
                       + "\n".join(lines))
        _CONTEXT_CACHE["data"] = snippet
        _CONTEXT_CACHE["ts"] = now
        return snippet
    except Exception:
        logger.warning("[ai_chat] 上下文注入失败", exc_info=True)
        return ""


# ================================================================== #
#  流式主入口：多轮对话（四段管道，异步生成器）
# ================================================================== #

async def ai_chat_stream(
    messages: List[Dict[str, str]],
    inject_context: bool = True,
):
    """流式多轮 AI 助手对话（async generator）。

    yield {"type": "status",  "text": "..."}                —— 阶段提示
    yield {"type": "delta",   "text": "..."}                —— 文本增量
    yield {"type": "results", "results":[...], "query":"..."} —— 工具产出的卡片（工具轮结束即发）
    yield {"type": "done",    "reply":..., "results":..., "tool_calls":..., "truncated":...}
    yield {"type": "error",   "message": "..."}
    """
    if not settings.deepseek_api_key:
        yield {"type": "error",
               "message": "AI 助手未配置 DeepSeek API Key，请联系管理员。"}
        return

    # ① 记忆窗口
    history, truncated = trim_history(messages)

    # ② 意图分类
    last_user = next(
        (m.get("content") or "" for m in reversed(history)
         if m.get("role") == "user"), "")
    intent = classify_intent(last_user)

    # ③ system + （可选）上下文
    system = svc.get_prompt("prompt.chat_system", CHAT_SYSTEM_PROMPT)
    if inject_context and _should_inject_context(intent, history):
        # 包 to_thread 让同步 DB 查询不阻塞事件循环（含 TTL 缓存）
        ctx = await asyncio.to_thread(_get_context_snippet)
        if ctx:
            system += "\n\n" + ctx

    llm_messages: List[Dict[str, Any]] = [{"role": "system", "content": system}]
    llm_messages += [{"role": m["role"], "content": m["content"]} for m in history]

    results_acc: List[Dict[str, Any]] = []
    tool_calls_log: List[str] = []
    deadline = time.time() + TOTAL_DEADLINE_S
    model_cfg = svc.get_model("chat_system")
    max_tokens = svc.get_param_int("param.llm_max_tokens", MAX_TOKENS)
    temperature = svc.get_param_float("param.llm_temperature", 0.0)
    timeout_sec = svc.get_param_float("param.llm_timeout_s", 60.0)

    yield {"type": "status", "text": "AI 思考中…"}

    try:
        for round_i in range(TOOL_ROUNDS + 1):
            remaining = deadline - time.time()
            if remaining <= 5:
                break
            use_tools = round_i < TOOL_ROUNDS
            round_content: List[str] = []
            round_tcs: Optional[list] = None
            stream_finished = False

            async for kind, payload in achat_stream(
                llm_messages,
                tools=TOOLS if use_tools else None,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=max(5.0, min(timeout_sec, remaining)),
                tag="chat",
                model_override=model_cfg.get("model"),
                base_url_override=model_cfg.get("base_url"),
                api_key_override=model_cfg.get("api_key"),
            ):
                if kind == "error":
                    yield {"type": "error", "message": str(payload)}
                    return
                if kind == "content":
                    round_content.append(payload)
                    yield {"type": "delta", "text": payload}
                elif kind == "tool_calls":
                    round_tcs = payload
                    stream_finished = True
                    break
                # usage 忽略
                # 注意：当无 tool_calls 时，achat_stream 自然结束后 for-async 循环退出，
                # 此时 stream_finished=False、round_tcs=None，走到下面的"最终回答"分支

            # 如果本轮收到了 tool_calls，执行工具并继续下一轮
            if round_tcs:
                if not use_tools:
                    # 最后一轮还想要工具：收口
                    reply = "".join(round_content).strip() or ""
                    if not reply:
                        reply = "⚠️ AI 想继续调用工具但已到上限，请换个问法。"
                    yield {"type": "done", "reply": reply,
                           "results": results_acc, "tool_calls": tool_calls_log,
                           "truncated": truncated}
                    return

                # 追加 assistant 消息（含已流出的 content + tool_calls）
                # 注意：每个 tool_call 对象必须有 type="function"（DeepSeek 协议）
                normalized_tcs = []
                for tc in round_tcs:
                    fn = tc.get("function") or {}
                    normalized_tcs.append({
                        "id": tc.get("id") or "",
                        "type": "function",
                        "function": {
                            "name": fn.get("name") or "",
                            "arguments": fn.get("arguments") or "{}",
                        },
                    })
                llm_messages.append({
                    "role": "assistant",
                    "content": "".join(round_content) or None,
                    "tool_calls": normalized_tcs,
                })
                yield {"type": "status", "text": "正在检索标讯…"}

                # 并行执行所有工具
                tasks = []
                prev_count = len(results_acc)
                for tc in round_tcs:
                    fn = tc.get("function", {})
                    name = fn.get("name") or ""
                    tool_calls_log.append(name)
                    try:
                        args = json.loads(fn.get("arguments") or "{}")
                        if not isinstance(args, dict):
                            args = {}
                    except json.JSONDecodeError:
                        args = {}
                    tasks.append(_exec_tool(name, args, results_acc))

                outs = await asyncio.gather(*tasks, return_exceptions=True)
                for tc, out in zip(round_tcs, outs):
                    if isinstance(out, Exception):
                        out = {"error": f"工具异常: {out}"}
                    llm_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id"),
                        "content": json.dumps(out, ensure_ascii=False, default=str),
                    })

                logger.info("[ai_chat.stream] route=%s round=%d tools=%s", intent,
                            round_i + 1, ",".join(tool_calls_log[-len(round_tcs):]))

                # 发最新 results（仅新增）
                if len(results_acc) > prev_count:
                    yield {"type": "results",
                           "results": list(results_acc),
                           "query": last_user}
                continue

            # 无 tool_calls：这是最终回答
            reply = "".join(round_content).strip()
            if not reply:
                if time.time() >= deadline:
                    reply = "⚠️ 本次对话耗时过长，请稍后重试，或把问题拆简单一点。"
                else:
                    reply = "⚠️ AI 未返回内容，请重试。"
            yield {"type": "done", "reply": reply,
                   "results": results_acc, "tool_calls": tool_calls_log,
                   "truncated": truncated}
            return

        # 走出循环（超时或轮次耗尽）
        if time.time() >= deadline:
            reply = "⚠️ 本次对话耗时过长，请稍后重试，或把问题拆简单一点。"
        else:
            reply = "⚠️ 对话轮次过多，请换个更简单的问法。"
        yield {"type": "done", "reply": reply,
               "results": results_acc, "tool_calls": tool_calls_log,
               "truncated": truncated}

    except LLMError as e:
        logger.warning("[ai_chat.stream] LLM error kind=%s: %s", e.kind, e)
        yield {"type": "error", "message": f"AI 暂时不可用：{str(e)[:80]}"}
    except Exception as e:  # noqa: BLE001
        logger.exception("[ai_chat.stream] 对话异常: %s", e)
        yield {"type": "error", "message": "AI 服务暂时不可用，请稍后再试。"}
