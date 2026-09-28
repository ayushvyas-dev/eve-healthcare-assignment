import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.dependencies import rate_limit as rate_limit_module


class FakeRedis:
    def __init__(self):
        self.counts = {}
        self.expirations = {}

    async def incr(self, key):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key, seconds):
        self.expirations[key] = seconds
        return True


def make_request(host="192.0.2.1"):
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/limited",
        "raw_path": b"/limited",
        "query_string": b"",
        "headers": [],
        "client": (host, 12345),
        "server": ("test", 80),
    })


@pytest.mark.asyncio
async def test_rate_limit_sets_expiry_once_and_rejects_over_limit(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(rate_limit_module, "_redis", redis)
    request = make_request()

    await rate_limit_module.rate_limit(request, "login", limit=2)
    await rate_limit_module.rate_limit(request, "login", limit=2)
    assert redis.expirations == {"ratelimit:login:192.0.2.1": 60}

    with pytest.raises(HTTPException) as error:
        await rate_limit_module.rate_limit(request, "login", limit=2)
    assert error.value.status_code == 429
    assert error.value.headers["Retry-After"] == "60"
