from datetime import datetime, timedelta, timezone
import pytest
from app.models.booking import BookingStatus
from app.models.payment import PaymentStatus


@pytest.mark.asyncio
async def test_payment_simulation_updates_booking_and_rejects_second_attempt(client, user_headers, monkeypatch):
    centre = (await client.post("/centres/", json={"name": "Lab", "location": "City"}, headers=user_headers)).json()
    test = (await client.post(f"/centres/{centre['id']}/tests/", json={"name": "CBC", "price": "20.00"}, headers=user_headers)).json()
    booking = (await client.post("/bookings/", json={"centre_id": centre["id"], "test_id": test["id"], "appointment_time": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}, headers=user_headers)).json()
    for outcome, expected_booking_status in (
        (PaymentStatus.SUCCESS, BookingStatus.CONFIRMED),
        (PaymentStatus.FAILED, BookingStatus.FAILED),
    ):
        monkeypatch.setattr("app.services.payment_service.choose_simulated_outcome", lambda outcome=outcome: outcome)
        created_booking = booking
        if outcome is PaymentStatus.FAILED:
            centre2 = (await client.post("/centres/", json={"name": "Lab 2", "location": "City"}, headers=user_headers)).json()
            test2 = (await client.post(f"/centres/{centre2['id']}/tests/", json={"name": "CBC", "price": "20.00"}, headers=user_headers)).json()
            created_booking = (await client.post("/bookings/", json={"centre_id": centre2["id"], "test_id": test2["id"], "appointment_time": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}, headers=user_headers)).json()

        response = await client.post("/payments/", json={"booking_id": created_booking["id"]}, headers=user_headers)
        assert response.status_code == 201
        assert response.json()["status"] == outcome.value
        stored_booking = await client.get(f"/bookings/{created_booking['id']}", headers=user_headers)
        assert stored_booking.json()["status"] == expected_booking_status.value
        assert (await client.post("/payments/", json={"booking_id": created_booking["id"]}, headers=user_headers)).status_code == 409


@pytest.mark.asyncio
async def test_payment_rejects_missing_booking(client, user_headers):
    missing = await client.post("/payments/", json={"booking_id": "00000000-0000-0000-0000-000000000001"}, headers=user_headers)
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_payment_rejects_another_users_booking(client, user_headers):
    centre = (await client.post("/centres/", json={"name": "Lab", "location": "City"}, headers=user_headers)).json()
    test = (await client.post(f"/centres/{centre['id']}/tests/", json={"name": "CBC", "price": "20.00"}, headers=user_headers)).json()
    booking = (await client.post("/bookings/", json={"centre_id": centre["id"], "test_id": test["id"], "appointment_time": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}, headers=user_headers)).json()
    await client.post("/auth/signup", json={"email": "payer@example.com", "password": "long-password-123"})
    login = await client.post("/auth/login", json={"email": "payer@example.com", "password": "long-password-123"})
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = await client.post("/payments/", json={"booking_id": booking["id"]}, headers=other_headers)
    assert response.status_code == 403
