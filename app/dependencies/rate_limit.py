import asyncio
from fastapi import HTTPException, Request
from redis.asyncio import Redis
from app.core.config import settings

_redis: Redis | None = None


async def rate_limit(request: Request, scope: str = "default", limit: int = 60, identifier: str | None = None):
    global _redis
    try:
        if _redis is None:
            _redis = Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=0.5, socket_timeout=0.5)
        identity = identifier or (request.client.host if request.client else "unknown")
        key = f"ratelimit:{scope}:{identity}"
        count = await asyncio.wait_for(_redis.incr(key), timeout=0.75)
        if count == 1:
            await asyncio.wait_for(_redis.expire(key, 60), timeout=0.75)
        if count > limit:
            raise HTTPException(429, detail={"code": "RATE_LIMITED", "message": "Too many requests, try again later."}, headers={"Retry-After": "60"})
    except HTTPException:
        raise
    except Exception:
        # Redis is an optional infrastructure dependency in local development.
        return


async def login_rate_limit(request: Request):
    await rate_limit(request, "login", 5)


async def webhook_rate_limit(request: Request):
    await rate_limit(request, "webhook", 60)
