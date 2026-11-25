# -*- coding: utf-8 -*-
"""
AI 智能生成推送（设计文档 3.7）

流程：管理员自然语言描述需求 → DeepSeek function calling 调用标讯检索工具
     → 拿到命中标讯 → 产出 markdown 推送文案 + 引用 bid_ids
     → 人工预览/编辑 → 走临时推送管道发送（AI 不直接发）。

硬约束：
- AI 只读标讯，检索严禁 SELECT content / content_text 大列（性能规则）。
- 未配置 DEEPSEEK_API_KEY 时返回明确提示，不降级瞎编。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional

import httpx

from app.config import settings
from app.database import SessionLocal
from app.models.bid import BidInfo

logger = logging.getLogger(__name__)

# 每次检索最多返回给 AI 的标讯条数
SEARCH_LIMIT = 30

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_bids",
            "description": "在标讯数据库中检索招标/采购标讯。可按关键词、地区、公告类型、时间范围过滤，返回标讯列表（含 id、标题、发布时间、截止时间、链接）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "标题关键词，多个词用空格分隔，任意命中即可，可为空",
                    },
                    "days": {
                        "type": "integer",
                        "description": "最近 N 天内发布，默认 7 天",
                    },
                    "region_code": {
                        "type": "string",
                        "description": "地区代码前缀过滤（如 3301 表示杭州市），可为空",
                    },
                    "notice_type": {
                        "type": "string",
                        "description": "公告类型名称（如 招标公告/中标公告），可为空",
                    },
                },
                "required": ["keyword"],
            },
        },
    }
]

SYSTEM_PROMPT = """你是标讯系统的「推送文案生成助手」，为运营人员生成要发到企业微信群的推送消息。

工作方式：
1. 先调用 search_bids 工具检索用户需要的标讯（可以多次调用、换不同条件）
2. 基于检索到的真实标讯，按用户要求生成一条 markdown 推送文案

文案要求：
- 直接输出推送正文（不要输出"好的""以下是"之类的开场白，不要输出标题行，标题由系统另加）
- 用 markdown 格式；提到具体标讯时尽量带上 [标题](链接) 形式
- 严格基于工具返回的真实数据，禁止编造不存在的标讯、金额、日期
- 用户对语气/格式有要求时按要求来；没要求时简洁清晰、突出重点
- 全文不超过 3500 字节（企业微信消息有长度限制）

你不能：写数据库、发消息、回答与标讯推送无关的问题。"""


def _search_bids(keyword: str, days: int = 7, region_code: Optional[str] = None,
                 notice_type: Optional[str] = None) -> List[dict]:
    """标讯检索工具实现：只 SELECT 精选列，绝不碰 content 大列。
    notice_type 非空时 JOIN dict_notice_type 按名称过滤。"""
    from app.models.dict import DictNoticeType

    db = SessionLocal()
    try:
        since = datetime.now() - timedelta(days=max(1, min(days, 365)))
        q = db.query(
            BidInfo.id, BidInfo.title, BidInfo.publish_time, BidInfo.deadline,
            BidInfo.source_url, BidInfo.budget, BidInfo.region_code,
        ).join(DictNoticeType, DictNoticeType.id == BidInfo.notice_type_id, isouter=True) \
         .filter(BidInfo.status == 1)

        if notice_type:
            q = q.filter(DictNoticeType.name.like(f"%{notice_type}%"))
        if keyword:
            for word in [w for w in keyword.replace("，", " ").replace(",", " ").split() if w]:
                q = q.filter(BidInfo.title.like(f"%{word}%"))
        if days:
            q = q.filter(BidInfo.publish_time >= since)
        if region_code:
            q = q.filter(BidInfo.region_code.like(f"{region_code}%"))
        rows = q.order_by(BidInfo.publish_time.desc()).limit(SEARCH_LIMIT).all()

        return [
            {
                "id": r.id,
                "title": r.title,
                "publish_time": r.publish_time.strftime("%Y-%m-%d") if r.publish_time else None,
                "deadline": r.deadline.strftime("%Y-%m-%d %H:%M") if r.deadline else None,
                "budget": r.budget,
                "region_code": r.region_code,
                "source_url": r.source_url,
            }
            for r in rows
        ]
    finally:
        db.close()


async def generate_push(messages: List[dict]) -> dict:
    """
    对话式生成推送文案。
    messages: [{"role":"user"|"assistant","content": "..."}]
    返回: {"reply": str, "cited_bid_ids": [int], "candidates": [int],
           "searched": int, "full": bool}
         full=True 表示最终文案已生成；False 表示需要继续对话（如未配置 key）。
    """
    if not settings.deepseek_api_key:
        return {
            "reply": "⚠️ **DeepSeek API Key 未配置**，AI 生成不可用。请在服务器 backend/.env 配置 DEEPSEEK_API_KEY 并重启 biaoxun-api。",
            "cited_bid_ids": [], "candidates": [], "searched": 0, "full": False,
        }

    url = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    final_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages[-16:]

    candidates: list = []   # 本次会话检索到的标讯 id（按出现顺序去重）
    searched = 0

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # 最多 4 轮工具调用，防止死循环
            for _ in range(4):
                payload = {
                    "model": settings.deepseek_model,
                    "messages": final_messages,
                    "tools": TOOLS,
                    "temperature": 0.5,
                    "max_tokens": 3000,
                }
                r = await client.post(url, headers=headers, json=payload)
                r.raise_for_status()
                data = r.json()
                msg = data["choices"][0]["message"]

                tool_calls = msg.get("tool_calls") or []
                if not tool_calls:
                    reply = (msg.get("content") or "").strip()
                    return {
                        "reply": reply or "（AI 未返回内容，请重试）",
                        "cited_bid_ids": collect_cited_ids(reply, candidates),
                        "candidates": candidates,
                        "searched": searched,
                        "full": True,
                    }

                # 追加 assistant(tool_calls) 再逐个执行
                final_messages.append({
                    "role": "assistant",
                    "content": msg.get("content"),
                    "tool_calls": tool_calls,
                })
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    try:
                        args = json.loads(fn.get("arguments") or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    if fn.get("name") == "search_bids":
                        results = _search_bids(
                            keyword=args.get("keyword", ""),
                            days=args.get("days", 7),
                            region_code=args.get("region_code"),
                            notice_type=args.get("notice_type"),
                        )
                        searched += 1
                        for b in results:
                            if b["id"] not in candidates:
                                candidates.append(b["id"])
                    else:
                        results = {"error": f"unknown tool {fn.get('name')}"}
                    final_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id"),
                        "content": json.dumps(results, ensure_ascii=False),
                    })

            # 4 轮仍未收敛
            return {
                "reply": "⚠️ AI 调用轮次过多，请简化需求后重试。",
                "cited_bid_ids": [], "candidates": candidates,
                "searched": searched, "full": False,
            }
    except httpx.HTTPStatusError as e:
        logger.error(f"[ai-push] HTTP {e.response.status_code}: {e.response.text[:200]}")
        return {"reply": f"⚠️ AI 服务返回错误：HTTP {e.response.status_code}",
                "cited_bid_ids": [], "candidates": candidates,
                "searched": searched, "full": False}
    except Exception as e:
        logger.exception(f"[ai-push] generate failed: {e}")
        return {"reply": f"⚠️ AI 服务暂时不可用：{str(e)[:80]}",
                "cited_bid_ids": [], "candidates": candidates,
                "searched": searched, "full": False}


def collect_cited_ids(reply: str, candidate_ids: List[int]) -> List[int]:
    """从文案中回收引用的标讯 id。
    AI 会微调标题（丢字/截断），所以两路匹配：
    1) source_url 出现在文案中（AI 通常带链接，最可靠）
    2) 标题任意 6 字连续片段出现在文案中（滑动窗口，容忍首尾改写）
    候选限定在本次工具检索结果内，误报风险可控。"""
    if not reply or not candidate_ids:
        return []
    ids = []
    db = SessionLocal()
    try:
        rows = db.query(BidInfo.id, BidInfo.title, BidInfo.source_url) \
                 .filter(BidInfo.id.in_(candidate_ids)).all()
        for b in rows:
            if b.source_url and b.source_url in reply:
                ids.append(b.id)
                continue
            t = b.title or ""
            if len(t) >= 6 and any(t[i:i + 6] in reply for i in range(len(t) - 5)):
                ids.append(b.id)
    finally:
        db.close()
    return ids
