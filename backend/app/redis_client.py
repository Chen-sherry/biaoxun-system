"""
Redis 连接管理
"""
from typing import Optional
import redis.asyncio as aioredis
import redis as sync_redis

from app.config import settings


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
