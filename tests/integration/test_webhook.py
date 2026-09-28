import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
import pytest
from app.core.config import settings


@pytest.mark.asyncio
async def test_webhook_requires_signature(client):
    event = {"provider_event_id": "event-1", "payment_id": "00000000-0000-0000-0000-000000000001", "status": "SUCCESS"}
    assert (await client.post("/payments/webhook/", json=event)).status_code == 400
    raw = json.dumps(event, separators=(",", ":"))
    signature = hmac.new(settings.webhook_signing_secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
    response = await client.post("/payments/webhook/", content=raw, headers={"Content-Type": "application/json", "X-Webhook-Signature": signature})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_webhook_replay_is_idempotent(client, user_headers):
    centre = (await client.post("/centres/", json={"name": "Lab", "location": "City"}, headers=user_headers)).json()
    test = (await client.post(f"/centres/{centre['id']}/tests/", json={"name": "CBC", "price": "20.00"}, headers=user_headers)).json()
    booking = (await client.post("/bookings/", json={"centre_id": centre["id"], "test_id": test["id"], "appointment_time": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}, headers=user_headers)).json()
    payment = (await client.post("/payments/", json={"booking_id": booking["id"]}, headers=user_headers)).json()
    event = {"provider_event_id": "evt-replay", "payment_id": payment["id"], "status": "SUCCESS"}
    raw = json.dumps(event, separators=(",", ":"))
    signature = hmac.new(settings.webhook_signing_secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
    headers = {"Content-Type": "application/json", "X-Webhook-Signature": signature}
    first = await client.post("/payments/webhook/", content=raw, headers=headers)
    replay = await client.post("/payments/webhook/", content=raw, headers=headers)
    assert first.status_code == replay.status_code == 200
    assert first.json()["status"] == "processed"
    assert replay.json()["status"] == "already_processed"
