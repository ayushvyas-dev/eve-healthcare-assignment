import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.models.booking import BookingStatus
from app.models.payment import PaymentStatus


def signed_headers(event):
    raw = json.dumps(event, separators=(",", ":"))
    signature = hmac.new(settings.webhook_signing_secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return raw, {"Content-Type": "application/json", "X-Webhook-Signature": signature}


async def create_payment(client, user_headers):
    centre = (await client.post("/centres/", json={"name": "Webhook Lab", "location": "City"}, headers=user_headers)).json()
    test = (await client.post(f"/centres/{centre['id']}/tests/", json={"name": "CBC", "price": "20.00"}, headers=user_headers)).json()
    booking = (await client.post("/bookings/", json={"centre_id": centre["id"], "test_id": test["id"], "appointment_time": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}, headers=user_headers)).json()
    payment = (await client.post("/payments/", json={"booking_id": booking["id"]}, headers=user_headers)).json()
    return booking, payment


@pytest.mark.asyncio
async def test_webhook_rejects_unsigned_invalid_and_unknown_events(client):
    event = {"provider_event_id": "event-1", "payment_id": "00000000-0000-0000-0000-000000000001", "status": "SUCCESS"}
    assert (await client.post("/payments/webhook/", json=event)).status_code == 400

    raw, headers = signed_headers(event)
    response = await client.post("/payments/webhook/", content=raw, headers=headers)
    assert response.status_code == 404

    invalid = {**event, "status": "PENDING"}
    assert (await client.post("/payments/webhook/", json=invalid, headers=headers)).status_code == 422


@pytest.mark.asyncio
async def test_webhook_replay_is_idempotent_and_preserves_consistent_state(client, user_headers):
    booking, payment = await create_payment(client, user_headers)
    event = {"provider_event_id": "evt-replay", "payment_id": payment["id"], "status": payment["status"]}
    raw, headers = signed_headers(event)

    first = await client.post("/payments/webhook/", content=raw, headers=headers)
    replay = await client.post("/payments/webhook/", content=raw, headers=headers)
    assert first.status_code == replay.status_code == 200
    assert first.json()["status"] == "processed"
    assert replay.json()["status"] == "already_processed"

    expected_booking_status = BookingStatus.CONFIRMED if payment["status"] == PaymentStatus.SUCCESS.value else BookingStatus.FAILED
    stored_booking = await client.get(f"/bookings/{booking['id']}", headers=user_headers)
    assert stored_booking.json()["status"] == expected_booking_status.value

    opposite_status = PaymentStatus.FAILED.value if payment["status"] == PaymentStatus.SUCCESS.value else PaymentStatus.SUCCESS.value
    conflict = {"provider_event_id": "evt-conflict", "payment_id": payment["id"], "status": opposite_status}
    conflict_raw, conflict_headers = signed_headers(conflict)
    assert (await client.post("/payments/webhook/", content=conflict_raw, headers=conflict_headers)).status_code == 409
    unchanged = await client.get(f"/bookings/{booking['id']}", headers=user_headers)
    assert unchanged.json()["status"] == expected_booking_status.value

    changed_replay = {**event, "status": opposite_status}
    changed_raw, changed_headers = signed_headers(changed_replay)
    assert (await client.post("/payments/webhook/", content=changed_raw, headers=changed_headers)).status_code == 409

    other_booking, other_payment = await create_payment(client, user_headers)
    reused_id = {"provider_event_id": event["provider_event_id"], "payment_id": other_payment["id"], "status": other_payment["status"]}
    reused_raw, reused_headers = signed_headers(reused_id)
    assert (await client.post("/payments/webhook/", content=reused_raw, headers=reused_headers)).status_code == 409
    other_state = await client.get(f"/bookings/{other_booking['id']}", headers=user_headers)
    expected_other = BookingStatus.CONFIRMED if other_payment["status"] == PaymentStatus.SUCCESS.value else BookingStatus.FAILED
    assert other_state.json()["status"] == expected_other.value


@pytest.mark.asyncio
async def test_webhook_retry_records_bounded_retry_metadata(client, user_headers):
    _, payment = await create_payment(client, user_headers)
    event = {"provider_event_id": "evt-retry", "payment_id": payment["id"], "status": payment["status"]}
    raw, headers = signed_headers(event)
    assert (await client.post("/payments/webhook/", content=raw, headers=headers)).status_code == 200

    retry_path = f"/payments/webhook/retry/{payment['id']}"
    assert (await client.post(retry_path, headers={"X-Webhook-Signature": "wrong"})).status_code == 400
    retry = await client.post(retry_path, headers={"X-Webhook-Signature": settings.webhook_signing_secret})
    assert retry.status_code == 200
    assert retry.json()["retry_count"] == 1
    for expected_attempt in range(2, 6):
        retry = await client.post(retry_path, headers={"X-Webhook-Signature": settings.webhook_signing_secret})
        assert retry.status_code == 200
        assert retry.json()["retry_count"] == expected_attempt
    exhausted = await client.post(retry_path, headers={"X-Webhook-Signature": settings.webhook_signing_secret})
    assert exhausted.status_code == 409
