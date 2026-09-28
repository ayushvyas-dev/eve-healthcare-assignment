from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment

MAX_RETRIES = 5


class RetryLimitReachedError(ValueError):
    pass


class NoWebhookEventError(ValueError):
    pass


def retry_delay(attempt: int, base_delay: int = 2, max_delay: int = 60) -> int:
    if attempt < 1:
        raise ValueError("attempt must be at least 1")
    return min((2 ** (attempt - 1)) * base_delay, max_delay)


def schedule_retry(payment, now: datetime | None = None) -> bool:
    if payment.retry_count >= MAX_RETRIES:
        return False
    now = now or datetime.now(timezone.utc)
    payment.retry_count += 1
    payment.last_attempt_at = now
    payment.next_retry_at = now + timedelta(seconds=retry_delay(payment.retry_count))
    return True


async def retry_payment_webhook(db: AsyncSession, payment_id):
    payment = await db.get(Payment, payment_id)
    if payment is None:
        raise LookupError("Payment not found")
    if not payment.provider_event_id:
        raise NoWebhookEventError("Payment has no webhook event to retry.")
    if not schedule_retry(payment):
        raise RetryLimitReachedError("Maximum retry attempts reached.")
    await db.commit()

    # Import locally to avoid a module cycle: payment processing also uses the
    # pure retry backoff helpers above.
    from app.services.payment_service import process_webhook

    await process_webhook(db, payment.provider_event_id, payment.id, payment.status)
    return {
        "payment_id": str(payment.id),
        "retry_count": payment.retry_count,
        "next_retry_at": payment.next_retry_at,
    }
