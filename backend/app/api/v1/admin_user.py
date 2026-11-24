"""后台用户 & 角色管理"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import SysUser, SysRole
from app.utils.security import hash_password
from app.utils.response import ApiResponse
from app.api.deps import require_role
from app.models.user import SysUser as UserModel

router = APIRouter(prefix="/admin/users")


def _user_to_dict(u: SysUser) -> dict:
    """SysUser ORM → 干净 dict。绝不返回 password_hash。"""
    d = {
        "id": u.id,
        "username": u.username,
        "nickname": getattr(u, "nickname", None),
        "avatar": getattr(u, "avatar", None),
        "email": getattr(u, "email", None),
        "phone": getattr(u, "phone", None),
        "company": getattr(u, "company", None),
        "status": u.status,
        "is_admin": getattr(u, "is_admin", 0),
        "last_login_at": u.last_login_at.isoformat() if getattr(u, "last_login_at", None) else None,
        "created_at": u.created_at.isoformat() if getattr(u, "created_at", None) else None,
    }
    return d


def _role_to_dict(r: SysRole) -> dict:
    return {
        "id": r.id,
        "code": getattr(r, "code", None),
        "name": getattr(r, "name", None),
        "description": getattr(r, "description", None),
        "status": r.status,
        "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None,
    }


@router.get("", response_model=ApiResponse, summary="用户列表")
def list_users(
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: UserModel = Depends(require_role("admin")),
):
    q = db.query(SysUser)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(SysUser.username.like(like) | SysUser.nickname.like(like))
    total = q.count()
    items = q.order_by(SysUser.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return ApiResponse.ok({
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_user_to_dict(u) for u in items],
    })


@router.post("", response_model=ApiResponse, summary="新增后台用户")
def create_user(
    payload: dict,
    db: Session = Depends(get_db),
    _: UserModel = Depends(require_role("admin")),
):
    exists = db.query(SysUser).filter(SysUser.username == payload["username"]).first()
    if exists:
        raise HTTPException(status_code=400, detail="用户名已存在")
    payload["password_hash"] = hash_password(payload.pop("password", "123456"))
    user = SysUser(**payload)
    db.add(user)
    db.commit()
    return ApiResponse.ok({"id": user.id}, msg="新增成功")


@router.put("/{user_id}/status", response_model=ApiResponse, summary="启用/禁用")
def change_status(user_id: int, status: int, db: Session = Depends(get_db), _: UserModel = Depends(require_role("admin"))):
    user = db.query(SysUser).filter(SysUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.status = status
    db.commit()
    return ApiResponse.ok(msg="状态更新成功")


@router.get("/roles", response_model=ApiResponse, summary="角色列表")
def list_roles(db: Session = Depends(get_db), _: UserModel = Depends(require_role("admin"))):
    items = db.query(SysRole).order_by(SysRole.id.asc()).all()
    return ApiResponse.ok([_role_to_dict(r) for r in items])
