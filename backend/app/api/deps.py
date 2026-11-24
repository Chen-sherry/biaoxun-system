"""依赖注入：获取当前用户、权限判断"""
from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.utils.security import decode_token
from app.models.user import SysUser


def _extract_token(authorization: Optional[str] = Header(default=None)) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.strip().split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return authorization.strip()


def get_current_user(
    token: Optional[str] = Depends(_extract_token),
    db: Session = Depends(get_db),
) -> SysUser:
    """获取当前登录用户，未登录则 401"""
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌无效或过期")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌无效")
    user = db.query(SysUser).filter(SysUser.id == int(user_id)).first()
    if not user or user.status != 1:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")
    return user


def get_current_user_optional(
    token: Optional[str] = Depends(_extract_token),
    db: Session = Depends(get_db),
) -> Optional[SysUser]:
    """可选登录：有令牌就返回用户，没有就返回 None"""
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    return db.query(SysUser).filter(SysUser.id == int(user_id)).first()


def require_role(*codes: str):
    """依赖：要求用户拥有指定角色编码之一（或超级管理员）"""
    def _dep(user: SysUser = Depends(get_current_user)) -> SysUser:
        if user.is_admin:
            return user
        user_codes = {r.code for r in user.roles}
        if not any(c in user_codes for c in codes):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
        return user
    return _dep


def require_permission(code: str):
    """依赖：要求用户拥有指定权限编码"""
    def _dep(user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)) -> SysUser:
        if user.is_admin:
            return user
        sql = (
            db.query(SysUser)
            .join(SysUser.roles)
            .join(SysUser.roles.property.mapper.class_.permissions)
            .filter(SysUser.id == user_id)
        )
        # 简化起见，这里只做角色级别校验，实际可缓存
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="permission check not ready")
    return _dep


def require_member(min_level: int = 1):
    """
    依赖：要求当前登录用户是会员（有未到期的 MemberOrder 且对应套餐 level >= min_level）。
    admin 放行。
    """
    def _dep(
        user: SysUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> SysUser:
        if getattr(user, "is_admin", False):
            return user
        from datetime import datetime
        from app.models.member import MemberOrder, MemberPackage
        now = datetime.now()
        active_order = (
            db.query(MemberOrder)
            .join(MemberPackage)
            .filter(
                MemberOrder.user_id == user.id,
                MemberOrder.status == 1,  # 已支付
                MemberOrder.start_date <= now,
                MemberOrder.end_date >= now,
                MemberPackage.level >= min_level,
            )
            .order_by(MemberOrder.end_date.desc())
            .first()
        )
        if not active_order:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要等级 ≥ {min_level} 的会员才能使用该功能",
            )
        return user
    return _dep
