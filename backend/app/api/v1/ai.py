# -*- coding: utf-8 -*-
"""AI 检索 + 悬浮球对话接口"""
import json as _json
from typing import List, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.deps import require_member
from app.models.user import SysUser
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
    """大白话 → AI 转译 → 知识库检索 → 相关性评分，>=70 分高度相关、60~69 分辅助展示。
    未登录 401 / 非付费会员 403，前端据此提示开通会员。"""
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="检索内容不能为空")
    result = ai_search(req.query.strip(), limit=max(1, min(req.limit, 120)))
    return ApiResponse.ok(result)


# ============ AI 悬浮球对话（流式 SSE） ============

class AIChatStreamIn(BaseModel):
    messages: List[Dict[str, str]]
    inject_context: Optional[bool] = True


@router.get("/hot-searches", summary="热门搜索词 Top N")
def hot_searches(limit: int = 10):
    """返回热门搜索词（按搜索次数降序），无需登录。"""
    from app.services.ai_search import get_hot_searches
    return ApiResponse.ok(get_hot_searches(min(limit, 20)))


@router.post("/chat/stream", summary="AI 悬浮球流式对话（SSE）")
async def chat_stream(
    req: AIChatStreamIn,
    user: SysUser = Depends(require_member(min_level=2)),
):
    """流式 SSE 对话，yield 事件：status / delta / results / done / error"""
    from app.services.ai_chat import ai_chat_stream

    async def event_generator():
        async for event in ai_chat_stream(req.messages, inject_context=req.inject_context):
            yield f"data: {_json.dumps(event, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
