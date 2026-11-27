# -*- coding: utf-8 -*-
"""AI 助手 + AI 匹配 两个接口"""
import json as _json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional

from app.api.deps import get_current_user_optional, require_member
from app.models.user import SysUser
from app.schemas.bid import AIMatchRequest, MatchedBid
from app.services.deepseek_match import match_bids_for_user
from app.services.ai_chat import ai_chat, ai_chat_stream
from app.services.ai_search import ai_search
from app.utils.response import ApiResponse

router = APIRouter(prefix="/ai", tags=["AI 功能"])


# ============ AI 检索（大白话搜索，会员专属） ============

class AISearchIn(BaseModel):
    query: str  # 用户大白话检索意图
    limit: int = 120  # 打分结果全量返回上限（前端按 75/60/40/20/0 分档渐进展示）


@router.post("/search", summary="AI 检索（大白话搜索，付费会员可用）")
def search(
    req: AISearchIn,
    _: SysUser = Depends(require_member(min_level=2)),
):
    """大白话 → AI 转译 → 知识库检索 → 相关性评分，>=75 分高度相关、60~74 分辅助展示。
    未登录 401 / 非付费会员 403，前端据此提示开通会员。"""
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="检索内容不能为空")
    result = ai_search(req.query.strip(), limit=max(1, min(req.limit, 120)))
    return ApiResponse.ok(result)


# ============ P2: 多轮 AI 助手（AI 悬浮球） ============

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str

class ChatIn(BaseModel):
    messages: List[ChatMessage]  # 历史对话（前端携带，上限由记忆窗口按字符预算裁剪）
    inject_context: bool = True   # 是否注入最新标讯上下文


def _chat_rate_limit(user_id: int) -> None:
    """每会员每日对话条数频控（Redis 计数，超限 429）。
    Redis 异常时放行（可用性优先），只记 warning。"""
    from datetime import datetime
    from app.config import settings
    limit = settings.chat_daily_limit
    if limit <= 0:
        return
    try:
        from app.redis_client import get_redis
        r = get_redis()
        key = f"ai_chat:limit:{user_id}:{datetime.now():%Y%m%d}"
        n = r.incr(key)
        if n == 1:
            r.expire(key, 86400)
        if n > limit:
            raise HTTPException(
                status_code=429,
                detail=f"今日 AI 对话次数已达上限（{limit} 条），请明天再来",
            )
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning("[ai_chat] 频控 Redis 异常，放行: %s", e)


@router.post("/chat", summary="多轮 AI 助手对话（付费会员可用）")
async def chat(
    req: ChatIn,
    current_user: SysUser = Depends(require_member(min_level=2)),
):
    """
    P2 AI 悬浮球：多轮长对话助手（与 AI 检索同级会员门槛）。
    - 四段管道：记忆窗口 → 意图分流 → 分支执行（工具 ≤3 轮）→ 输出（见 ai_chat.py）
    - 只读工具：search_bids / count_bids / get_bid_detail，不写库
    - 每会员每日 chat_daily_limit 条频控（Redis），超限 429
    - 未登录 401 / 非付费会员 403，前端据此提示开通会员
    """
    # 只保留 user/assistant，过滤掉奇怪的 role（历史裁剪交给 ai_chat 记忆窗口）
    cleaned = [
        {"role": m.role if m.role in ("user", "assistant") else "user", "content": m.content}
        for m in req.messages
    ]
    if not cleaned:
        raise HTTPException(status_code=400, detail="messages 不能为空")

    _chat_rate_limit(current_user.id)

    result = await ai_chat(cleaned, inject_context=req.inject_context)
    return ApiResponse.ok(result)


@router.post("/chat/stream", summary="多轮 AI 助手对话（流式 SSE，付费会员可用）")
async def chat_stream(
    req: ChatIn,
    current_user: SysUser = Depends(require_member(min_level=2)),
):
    """
    P2 AI 悬浮球：流式多轮对话助手。
    - 依赖/频控与 /ai/chat 完全一致：会员门槛 + 每日 chat_daily_limit 条
    - 事件格式：data: {json}\\n\\n；type ∈ {status, delta, results, done, error}
    - nginx 通过 X-Accel-Buffering: no 关闭缓冲，SSE 逐条透传
    """
    cleaned = [
        {"role": m.role if m.role in ("user", "assistant") else "user", "content": m.content}
        for m in req.messages
    ]
    if not cleaned:
        raise HTTPException(status_code=400, detail="messages 不能为空")

    _chat_rate_limit(current_user.id)

    async def _gen():
        async for event in ai_chat_stream(cleaned, inject_context=req.inject_context):
            yield f"data: {_json.dumps(event, ensure_ascii=False)}\n\n"

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return StreamingResponse(_gen(), media_type="text/event-stream", headers=headers)

@router.post("/match", response_model=ApiResponse[list[MatchedBid]], summary="AI 智能匹配")
async def ai_match(
    req: AIMatchRequest,
    current_user: Optional[SysUser] = Depends(get_current_user_optional),
):
    """
    根据订阅关键词 + 最近 N 天标讯，走 DeepSeek LLM 做语义打分。
    - 未配置 DEEPSEEK_API_KEY 时自动降级为本地关键词加权
    - 门户可匿名调用；登录会员体验更完整
    """
    if not req.keywords:
        raise HTTPException(status_code=400, detail="keywords 不能为空")
    result = await match_bids_for_user(
        keywords=req.keywords,
        days=req.days,
        limit=req.limit,
    )
    return ApiResponse(code=0, data=result, message="ok")


@router.get("/config", summary="AI 服务状态")
async def ai_match_config():
    from app.config import settings
    return ApiResponse(code=0, data={
        "deepseek_enabled": bool(settings.deepseek_api_key),
        "deepseek_model": settings.deepseek_model,
        "fallback_to_local": True,
        "chat_enabled": True,   # 多轮 AI 助手是否可用
        "chat_daily_limit": settings.chat_daily_limit,  # 每会员每日对话条数（悬浮球展示余量用）
    }, message="ok")
