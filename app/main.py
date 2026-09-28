from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.core.logging import configure_logging
from app.db.session import engine
from app.middleware.request_logging import RequestLoggingMiddleware
from app.routes.auth import router as auth_router
from app.routes.catalog import centres, tests
from app.routes.bookings import router as bookings_router
from app.routes.payments import router as payments_router

configure_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="EVE Healthcare API", version="0.1.0", description="Diagnostic test booking and simulated payment service", lifespan=lifespan)
app.add_middleware(RequestLoggingMiddleware)
app.include_router(auth_router)
app.include_router(centres)
app.include_router(tests)
app.include_router(bookings_router)
app.include_router(payments_router)


@app.exception_handler(HTTPException)
async def http_error_handler(_request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        error = detail
    else:
        error = {"code": "HTTP_ERROR", "message": str(detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": error}, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError):
    # Pydantic error contexts can contain Decimal/exception objects, and input
    # values may include credentials. Keep only JSON-safe, non-sensitive fields.
    details = [
        {key: value for key, value in error.items() if key not in {"ctx", "input", "url"}}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed.", "details": details}})


@app.get("/health", tags=["operations"])
async def health():
    return {"status": "ok"}
