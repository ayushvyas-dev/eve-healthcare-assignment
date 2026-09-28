from datetime import datetime, timedelta, timezone
import pytest


@pytest.mark.asyncio
async def test_booking_snapshot_and_owner(client, user_headers):
    centre = (await client.post("/centres/", json={"name": "Central Lab", "location": "Downtown"}, headers=user_headers)).json()
    test = (await client.post(f"/centres/{centre['id']}/tests/", json={"name": "CBC", "price": "15.50"}, headers=user_headers)).json()
    response = await client.post("/bookings/", json={"centre_id": centre["id"], "test_id": test["id"], "appointment_time": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()}, headers=user_headers)
    assert response.status_code == 201
    assert response.json()["amount"] == "15.50"
    assert response.json()["status"] == "PENDING"
    assert (await client.get(f"/bookings/{response.json()['id']}", headers=user_headers)).status_code == 200
    assert (await client.get("/bookings/", headers=user_headers)).json()["total"] == 1


@pytest.mark.asyncio
async def test_booking_rejects_past_time_mismatched_centre_and_non_owner(client, user_headers):
    centre = (await client.post("/centres/", json={"name": "Lab", "location": "City"}, headers=user_headers)).json()
    other_centre = (await client.post("/centres/", json={"name": "Other Lab", "location": "Town"}, headers=user_headers)).json()
    test = (await client.post(f"/centres/{centre['id']}/tests/", json={"name": "CBC", "price": "15.50"}, headers=user_headers)).json()
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    mismatch = await client.post("/bookings/", json={"centre_id": other_centre["id"], "test_id": test["id"], "appointment_time": future}, headers=user_headers)
    past_response = await client.post("/bookings/", json={"centre_id": centre["id"], "test_id": test["id"], "appointment_time": past}, headers=user_headers)
    assert mismatch.status_code == 400
    assert past_response.status_code == 400

    booking = await client.post("/bookings/", json={"centre_id": centre["id"], "test_id": test["id"], "appointment_time": future}, headers=user_headers)
    other_signup = await client.post("/auth/signup", json={"email": "other@example.com", "password": "long-password-123"})
    assert other_signup.status_code == 201
    other_login = await client.post("/auth/login", json={"email": "other@example.com", "password": "long-password-123"})
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}
    assert (await client.get(f"/bookings/{booking.json()['id']}", headers=other_headers)).status_code == 403
    assert (await client.get("/bookings/not-a-uuid", headers=user_headers)).status_code == 422
