"""认证、登录相关 Schema"""
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr


class LoginIn(BaseModel):
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")
    captcha: Optional[str] = Field(None, description="验证码")


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expire_minutes: int


class UserRegisterIn(BaseModel):
    username: str
    password: str
    nickname: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company: Optional[str] = None


class UserInfoOut(BaseModel):
    id: int
    username: str
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    company: Optional[str] = None
    roles: List[str] = []
