"""订阅管理 — 用户自己的 CRUD + admin 全量管理"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.subscribe import BidSubscribe
from app.models.user import SysUser
from app.api.deps import get_current_user, get_current_user_optional, require_role
from app.utils.response import ApiResponse, PageData

router = APIRouter(prefix="/subscribes")


def _to_dict(s: BidSubscribe, username: Optional[str] = None) -> dict:
    """把 BidSubscribe ORM 转成干净 dict。username 由 JOIN 预先查出，
    避免 ORM 没有定义 user backref 时 s.user 抛 AttributeError。"""
    return {
        "id": s.id,
        "user_id": s.user_id,
        "username": username,
        "keyword": s.keyword,
        "region_code": s.region_code,
        "industry_id": s.industry_id,
        "notice_type_id": s.notice_type_id,
        "push_email": bool(s.push_email),
        "push_wechat": bool(s.push_wechat),
        "frequency": s.frequency,
        "last_push_at": s.last_push_at.isoformat() if s.last_push_at else None,
        "status": s.status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


# ===== 用户自己的订阅 =====

@router.get("/mine", summary="我的订阅列表（登录用户）")
def list_my_subscribes(
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    items = (
        db.query(BidSubscribe)
        .filter(BidSubscribe.user_id == user.id)
        .order_by(BidSubscribe.id.desc())
        .all()
    )
    return ApiResponse.ok([_to_dict(s, username=user.username) for s in items])


@router.post("", summary="新增订阅")
def create_subscribe(
    payload: dict,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    sub = BidSubscribe(**payload, user_id=user.id)
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return ApiResponse.ok(_to_dict(sub), msg="订阅创建成功")


@router.put("/{subscribe_id}", summary="修改订阅")
def update_subscribe(
    subscribe_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    sub = db.query(BidSubscribe).filter(
        BidSubscribe.id == subscribe_id, BidSubscribe.user_id == user.id
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    for k, v in payload.items():
        setattr(sub, k, v)
    db.commit()
    db.refresh(sub)
    return ApiResponse.ok(_to_dict(sub), msg="修改成功")


@router.delete("/{subscribe_id}", summary="删除订阅")
def delete_subscribe(
    subscribe_id: int,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    sub = db.query(BidSubscribe).filter(
        BidSubscribe.id == subscribe_id, BidSubscribe.user_id == user.id
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    db.delete(sub)
    db.commit()
    return ApiResponse.ok(msg="删除成功")


# ===== Admin 全量管理 =====

@router.get("", response_model=ApiResponse[PageData[dict]], summary="admin：全量订阅列表")
def admin_list_subscribes(
    user_id: Optional[int] = None,
    status: Optional[int] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: SysUser = Depends(require_role("admin", "admin_role")),
):
    """admin 登录后可以看到所有用户订阅（带筛选 + 分页）。"""
    q = (
        db.query(BidSubscribe, SysUser.username)
        .outerjoin(SysUser, SysUser.id == BidSubscribe.user_id)
    )
    if user_id is not None:
        q = q.filter(BidSubscribe.user_id == user_id)
    if status is not None:
        q = q.filter(BidSubscribe.status == status)
    if keyword:
        q = q.filter(BidSubscribe.keyword.like(f"%{keyword}%"))
    total = q.count()
    rows = (
        q.order_by(BidSubscribe.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return ApiResponse.ok(PageData(
        total=total, page=page, page_size=page_size,
        items=[_to_dict(s, username=u) for (s, u) in rows],
    ))


@router.put("/{subscribe_id}/toggle", summary="admin：启用/禁用订阅")
def toggle_subscribe(
    subscribe_id: int,
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_role("admin", "admin_role")),
):
    sub = db.query(BidSubscribe).filter(BidSubscribe.id == subscribe_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    sub.status = 0 if sub.status else 1
    db.commit()
    db.refresh(sub)
    return ApiResponse.ok(_to_dict(sub), msg="已更新")
