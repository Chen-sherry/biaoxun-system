# -*- coding: utf-8 -*-
"""AI 助手 + AI 匹配 两个接口"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from app.api.deps import get_current_user_optional, require_member
from app.models.user import SysUser
from app.schemas.bid import AIMatchRequest, MatchedBid
from app.services.deepseek_match import match_bids_for_user
from app.services.ai_chat import ai_chat
from app.services.ai_search import ai_search
from app.utils.response import ApiResponse

router = APIRouter(prefix="/ai", tags=["AI 功能"])


# ============ AI 检索（大白话搜索，会员专属） ============

class AISearchIn(BaseModel):
    query: str  # 用户大白话检索意图
    limit: int = 20


@router.post("/search", summary="AI 检索（大白话搜索，付费会员可用）")
def search(
    req: AISearchIn,
    _: SysUser = Depends(require_member(min_level=2)),
):
    """大白话 → AI 转译 → 知识库检索 → 相关性评分，只返回 >75 分的结果。
    未登录 401 / 非付费会员 403，前端据此提示开通会员。"""
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="检索内容不能为空")
    result = ai_search(req.query.strip(), limit=max(1, min(req.limit, 50)))
    return ApiResponse.ok(result)


# ============ P2: 多轮 AI 助手 ============

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str

class ChatIn(BaseModel):
    messages: List[ChatMessage]  # 历史对话
    inject_context: bool = True   # 是否注入最新标讯上下文


@router.post("/chat", summary="多轮 AI 助手对话")
async def chat(
    req: ChatIn,
    current_user: Optional[SysUser] = Depends(get_current_user_optional),
):
    """
    P2 新功能：多轮 AI 助手。
    - 系统提示词硬限定：AI 只有**只读查询权限**
    - 自动注入最新标讯数据库上下文，减少幻觉
    - 未登录也能用，登录用户可加个性化
    """
    # 只保留 user/assistant，过滤掉奇怪的 role
    cleaned = [
        {"role": m.role if m.role in ("user", "assistant") else "user", "content": m.content}
        for m in req.messages
    ]
    if not cleaned:
        raise HTTPException(status_code=400, detail="messages 不能为空")
    if len(cleaned) > 20:
        cleaned = cleaned[-20:]  # 最多保留最近 20 条，避免超限

    reply = await ai_chat(cleaned, inject_context=req.inject_context)
    return ApiResponse(code=0, data={"reply": reply}, message="ok")


# ============ AI 智能匹配（P1 已有，接 API 后切 LLM） ============

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
    }, message="ok")
