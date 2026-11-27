"""
Redis 连接管理
"""
import hashlib
import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis
import redis as sync_redis

from app.config import settings

logger = logging.getLogger(__name__)


def _build_url(db: int) -> str:
    if settings.redis_password:
        return (
            f"redis://:{settings.redis_password}@{settings.redis_host}"
            f":{settings.redis_port}/{db}"
        )
    return f"redis://{settings.redis_host}:{settings.redis_port}/{db}"


# 同步客户端（用于 Celery 任务等场景）
redis_sync = sync_redis.from_url(
    _build_url(settings.redis_db),
    decode_responses=True,
    health_check_interval=30,
)


def get_redis() -> sync_redis.Redis:
    """返回已连接的同步 Redis 客户端"""
    return redis_sync


# ========== 通用缓存工具 ==========

def cache_get(key: str) -> Optional[Any]:
    """从 Redis 获取缓存，失败返回 None"""
    try:
        raw = get_redis().get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as e:
        logger.debug(f"[cache] get {key} failed: {e}")
        return None


def cache_set(key: str, value: Any, ttl: int = 300) -> bool:
    """写入 Redis 缓存，失败静默"""
    try:
        get_redis().setex(key, ttl, json.dumps(value, ensure_ascii=False, default=str))
        return True
    except Exception as e:
        logger.debug(f"[cache] set {key} failed: {e}")
        return False


def cache_key(prefix: str, *parts: str) -> str:
    """生成缓存 key：prefix:hash(parts)"""
    raw = ":".join(str(p) for p in parts)
    h = hashlib.md5(raw.encode()).hexdigest()[:12]
    return f"{prefix}:{h}"
