import time
import uuid
import structlog
from starlette.middleware.base import BaseHTTPMiddleware

log = structlog.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            log.info("http_request", request_id=request_id, method=request.method, path=request.url.path, status_code=status, duration_ms=round((time.perf_counter() - started) * 1000, 2))
