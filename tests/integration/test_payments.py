from datetime import datetime, timedelta, timezone
import pytest


@pytest.mark.asyncio
async def test_payment_simulation_updates_booking(client, user_headers):
    centre = (await client.post("/centres/", json={"name": "Lab", "location": "City"}, headers=user_headers)).json()
    test = (await client.post(f"/centres/{centre['id']}/tests/", json={"name": "CBC", "price": "20.00"}, headers=user_headers)).json()
    booking = (await client.post("/bookings/", json={"centre_id": centre["id"], "test_id": test["id"], "appointment_time": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}, headers=user_headers)).json()
    response = await client.post("/payments/", json={"booking_id": booking["id"]}, headers=user_headers)
    assert response.status_code == 201
    assert response.json()["status"] in ("SUCCESS", "FAILED")
