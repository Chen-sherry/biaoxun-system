"""
安全相关：密码哈希、JWT 令牌
"""
from datetime import datetime, timedelta
from typing import Any, Optional, Union
from jose import jwt, JWTError
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """密码哈希"""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """校验密码"""
    return pwd_context.verify(plain, hashed)


def create_access_token(
    subject: Union[str, int],
    extra: Optional[dict] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """生成 JWT 访问令牌"""
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload: dict[str, Any] = {"sub": str(subject), "exp": expire}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> Optional[dict]:
    """解析并验证 JWT 令牌"""
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None
