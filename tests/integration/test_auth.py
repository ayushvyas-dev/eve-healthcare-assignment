import pytest


@pytest.mark.asyncio
async def test_signup_login_and_duplicate(client):
    payload = {"email": "user@example.com", "password": "long-password-123"}
    assert (await client.post("/auth/signup", json=payload)).status_code == 201
    assert (await client.post("/auth/signup", json=payload)).status_code == 409
    assert (await client.post("/auth/login", json=payload)).status_code == 200
    assert (await client.get("/bookings/")).status_code == 401
