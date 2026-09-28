from datetime import datetime, timedelta, timezone
import pytest


@pytest.mark.asyncio
async def test_booking_snapshot_and_owner(client, user_headers):
    centre = (await client.post("/centres/", json={"name": "Central Lab", "location": "Downtown"}, headers=user_headers)).json()
    test = (await client.post(f"/centres/{centre['id']}/tests/", json={"name": "CBC", "price": "15.50"}, headers=user_headers)).json()
    response = await client.post("/bookings/", json={"centre_id": centre["id"], "test_id": test["id"], "appointment_time": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()}, headers=user_headers)
    assert response.status_code == 201
    assert response.json()["amount"] == "15.50"
    assert (await client.get(f"/bookings/{response.json()['id']}", headers=user_headers)).status_code == 200
