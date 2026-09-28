from datetime import datetime, timedelta, timezone

MAX_RETRIES = 5


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
