"""认证接口：登录 / 注册 / 当前用户"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.utils.security import hash_password, verify_password, create_access_token
from app.models.user import SysUser
from app.schemas.auth import LoginIn, TokenOut, UserRegisterIn, UserInfoOut
from app.api.deps import get_current_user

router = APIRouter(prefix="/auth")


@router.post("/login", response_model=TokenOut, summary="用户登录")
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.query(SysUser).filter(SysUser.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if user.status != 1:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已禁用")

    token = create_access_token(subject=user.id, extra={"username": user.username})
    return TokenOut(access_token=token, expire_minutes=1440)


@router.post("/register", response_model=UserInfoOut, summary="用户注册")
def register(payload: UserRegisterIn, db: Session = Depends(get_db)):
    exists = db.query(SysUser).filter(SysUser.username == payload.username).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")
    user = SysUser(
        username=payload.username,
        password_hash=hash_password(payload.password),
        nickname=payload.nickname or payload.username,
        email=payload.email,
        phone=payload.phone,
        company=payload.company,
        status=1,
        is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserInfoOut(id=user.id, username=user.username, nickname=user.nickname, company=user.company)


@router.get("/me", response_model=UserInfoOut, summary="获取当前用户信息")
def me(user: SysUser = Depends(get_current_user)):
    return UserInfoOut(
        id=user.id,
        username=user.username,
        nickname=user.nickname,
        avatar=user.avatar,
        company=user.company,
        roles=[r.code for r in user.roles],
    )
