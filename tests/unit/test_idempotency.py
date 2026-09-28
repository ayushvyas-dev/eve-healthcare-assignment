from types import SimpleNamespace
from datetime import datetime, timezone
import pytest
from app.services.retry_service import retry_delay, schedule_retry


def test_retry_backoff_is_exponential_and_capped():
    assert [retry_delay(n) for n in range(1, 7)] == [2, 4, 8, 16, 32, 60]


def test_retry_metadata_and_limit():
    payment = SimpleNamespace(retry_count=0, last_attempt_at=None, next_retry_at=None)
    now = datetime.now(timezone.utc)
    assert schedule_retry(payment, now)
    assert payment.retry_count == 1
    assert payment.next_retry_at > now
    payment.retry_count = 5
    assert schedule_retry(payment, now) is False
