"""Redis 异步客户端（验证码存取）。"""

from functools import lru_cache

import redis.asyncio as redis

from config import settings


@lru_cache
def get_redis() -> redis.Redis:
    """进程级共享连接池；decode_responses 让取出的值直接是 str。"""
    return redis.from_url(settings.redis_url, decode_responses=True)
