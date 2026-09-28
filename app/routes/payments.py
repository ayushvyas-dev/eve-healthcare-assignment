import hashlib
import hmac
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.rate_limit import rate_limit, webhook_rate_limit
from app.models.payment import PaymentStatus
from app.models.user import User
from app.schemas.payment import PaymentCreate, PaymentOut, WebhookEvent
from app.services.payment_service import WebhookConflictError, create_simulated_payment, process_webhook
from app.services.retry_service import NoWebhookEventError, RetryLimitReachedError, retry_payment_webhook

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
async def create_payment(payload: PaymentCreate, request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await rate_limit(request, "payments", 10, str(user.id))
    try:
        return await create_simulated_payment(db, payload.booking_id, user.id)
    except LookupError as exc:
        raise HTTPException(404, detail={"code": "BOOKING_NOT_FOUND", "message": str(exc)})
    except PermissionError:
        raise HTTPException(403, detail={"code": "NOT_BOOKING_OWNER", "message": "You do not own this booking."})
    except RuntimeError as exc:
        raise HTTPException(409, detail={"code": "BOOKING_NOT_PAYABLE", "message": str(exc)})


@router.post("/webhook/", dependencies=[Depends(webhook_rate_limit)])
async def webhook(event: WebhookEvent, request: Request, db: AsyncSession = Depends(get_db), x_webhook_signature: str | None = Header(default=None)):
    if event.status not in (PaymentStatus.SUCCESS, PaymentStatus.FAILED):
        raise HTTPException(422, detail={"code": "INVALID_PAYMENT_STATUS", "message": "Webhook status must be SUCCESS or FAILED."})
    if not x_webhook_signature:
        raise HTTPException(400, detail={"code": "INVALID_SIGNATURE", "message": "Webhook signature is required."})
    expected = hmac.new(settings.webhook_signing_secret.encode(), await request.body(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, x_webhook_signature):
        raise HTTPException(400, detail={"code": "INVALID_SIGNATURE", "message": "Webhook signature is invalid."})
    try:
        processed = await process_webhook(db, event.provider_event_id, event.payment_id, event.status)
    except LookupError:
        raise HTTPException(404, detail={"code": "PAYMENT_NOT_FOUND", "message": "Payment not found."})
    except WebhookConflictError as exc:
        raise HTTPException(409, detail={"code": "WEBHOOK_EVENT_CONFLICT", "message": str(exc)})
    return {"status": "processed" if processed else "already_processed"}


@router.post("/webhook/retry/{payment_id}")
async def retry_webhook(payment_id: UUID, x_webhook_signature: str | None = Header(default=None), db: AsyncSession = Depends(get_db)):
    if not x_webhook_signature or not hmac.compare_digest(x_webhook_signature, settings.webhook_signing_secret):
        raise HTTPException(400, detail={"code": "INVALID_SIGNATURE", "message": "Webhook signature is invalid."})
    try:
        return await retry_payment_webhook(db, payment_id)
    except LookupError:
        raise HTTPException(404, detail={"code": "PAYMENT_NOT_FOUND", "message": "Payment not found."})
    except NoWebhookEventError as exc:
        raise HTTPException(409, detail={"code": "NO_WEBHOOK_EVENT", "message": str(exc)})
    except RetryLimitReachedError as exc:
        raise HTTPException(409, detail={"code": "RETRY_LIMIT_REACHED", "message": str(exc)})
