# -*- coding: utf-8 -*-
"""
DeepSeek AI 智能匹配服务
企业订阅关键词 + 最新标讯 → 送 DeepSeek LLM 做语义打分 → 返回 Top-N

依赖：DEEPSEEK_API_KEY 配在 .env
未配置时走 **本地关键词加权** 的降级路径（兜底返回可用结果）。
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta
from typing import List, Optional

import httpx

from app.config import settings
from app.database import SessionLocal
from app.models.bid import BidInfo

logger = logging.getLogger(__name__)


# =====================================================
# 路径一：DeepSeek 语义匹配（需 API Key）
# =====================================================

SYSTEM_PROMPT = """你是一个标讯推荐助手。根据企业的订阅关键词，对最新的招标/采购标讯做匹配打分。
每条标讯给出 0-100 的分数（越相关分越高），并简述匹配理由。
仅返回 JSON 数组，不要返回其他文字。"""


def _build_prompt(keywords: List[str], bids_sample: List[dict]) -> str:
    bids_text = "\n".join(
        f"[{b['id']}] {b['title']} (发布: {b.get('publish_time','?')})" for b in bids_sample
    )
    return (
        f"企业订阅关键词：{', '.join(keywords)}\n\n"
        f"以下是近期标讯：\n{bids_text}\n\n"
        f"请输出 JSON 数组格式：\n"
        f'[{{"bid_id": int, "score": float, "reason": "匹配原因简述"}}]'
    )


async def deepseek_match(
    keywords: List[str],
    bids_sample: List[dict],
    limit: int = 10,
) -> List[dict]:
    """调用 DeepSeek API 做语义匹配。"""
    if not settings.deepseek_api_key:
        logger.warning("[ai-match] DEEPSEEK_API_KEY 未配置，走本地降级")
        return _fallback_keyword_score(keywords, bids_sample, limit)

    url = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_prompt(keywords, bids_sample)},
        ],
        "temperature": 0.3,
        "max_tokens": 4000,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            # 从返回里摘 JSON：先尝试直接 parse，再尝试正则
            parsed = None
            try:
                parsed = json.loads(content.strip())
            except (json.JSONDecodeError, ValueError):
                json_match = re.search(r"\[.*\]", content, re.DOTALL)
                if json_match:
                    try:
                        parsed = json.loads(json_match.group())
                    except Exception:
                        parsed = None
            if parsed and isinstance(parsed, list):
                parsed.sort(key=lambda x: -x.get("score", 0))
                return parsed[:limit]
            logger.warning(f"[ai-match] DeepSeek 返回无法解析: {content[:200]}")
            return _fallback_keyword_score(keywords, bids_sample, limit)
    except Exception as e:
        logger.exception(f"[ai-match] DeepSeek 调用失败: {e}")
        return _fallback_keyword_score(keywords, bids_sample, limit)


# =====================================================
# 路径二：本地关键词加权降级兜底
# =====================================================

def _fallback_keyword_score(
    keywords: List[str],
    bids_sample: List[dict],
    limit: int,
) -> List[dict]:
    """本地对每条标讯按关键词命中数做加权打分。"""
    scored = []
    kw_lower = [k.lower() for k in keywords if k]
    for b in bids_sample:
        title_lower = (b.get("title") or "").lower()
        text_lower = (b.get("content_text") or "")[:500].lower()
        hits_title = sum(1 for k in kw_lower if k in title_lower)
        hits_text = sum(1 for k in kw_lower if k in text_lower)
        score = min(100.0, hits_title * 20 + hits_text * 5)
        if score > 0:
            scored.append({
                "bid_id": b["id"],
                "score": round(score, 1),
                "reason": f"标题命中 {hits_title} 个关键词" if hits_title else f"正文命中 {hits_text} 个关键词",
            })
    scored.sort(key=lambda x: -x["score"])
    return scored[:limit]


# =====================================================
# 数据库查询 + 主入口
# =====================================================

def fetch_recent_bids(days: int = 30, max_bids: int = 80) -> List[dict]:
    """取最近 N 天 status=1 的标讯。"""
    db = SessionLocal()
    try:
        since = datetime.now() - timedelta(days=days)
        rows = (
            db.query(BidInfo)
            .filter(BidInfo.status == 1, BidInfo.publish_time >= since)
            .order_by(BidInfo.publish_time.desc())
            .limit(max_bids)
            .all()
        )
        return [
            {
                "id": r.id,
                "title": r.title,
                "publish_time": r.publish_time.isoformat() if r.publish_time else None,
                "content_text": r.content_text or "",
                "source_url": r.source_url,
            }
            for r in rows
        ]
    finally:
        db.close()


async def match_bids_for_user(
    keywords: List[str],
    days: int = 30,
    limit: int = 10,
) -> List[dict]:
    """
    主入口：给一个企业关键词列表，返回匹配度 Top-N 标讯。
    先调 DeepSeek；API Key 未配或调用失败时本地降级。
    """
    if not keywords:
        return []
    bids_sample = fetch_recent_bids(days=days)
    if not bids_sample:
        return []

    raw_matches = await deepseek_match(keywords, bids_sample, limit=limit)

    # 把 bid_id → 完整对象，填充 source_url / publish_time
    id_map = {b["id"]: b for b in bids_sample}
    result = []
    for m in raw_matches:
        bid = id_map.get(m["bid_id"])
        if bid:
            result.append({
                "bid_id": m["bid_id"],
                "title": bid["title"],
                "score": m.get("score", 0),
                "reason": m.get("reason"),
                "source_url": bid.get("source_url"),
                "publish_time": bid.get("publish_time"),
            })
    return result
