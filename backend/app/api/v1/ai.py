# -*- coding: utf-8 -*-
"""AI 检索接口"""
from fastapi import APIRouter, Depends, HTTPException
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
    """大白话 → AI 转译 → 知识库检索 → 相关性评分，>=75 分高度相关、60~74 分辅助展示。
    未登录 401 / 非付费会员 403，前端据此提示开通会员。"""
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="检索内容不能为空")
    result = ai_search(req.query.strip(), limit=max(1, min(req.limit, 120)))
    return ApiResponse.ok(result)
