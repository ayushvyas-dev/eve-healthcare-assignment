import pytest


@pytest.mark.asyncio
async def test_signup_login_and_duplicate(client):
    payload = {"email": "user@example.com", "password": "long-password-123"}
    assert (await client.post("/auth/signup", json=payload)).status_code == 201
    assert (await client.post("/auth/signup", json=payload)).status_code == 409
    assert (await client.post("/auth/login", json=payload)).status_code == 200
    assert (await client.post("/auth/login", json={**payload, "password": "incorrect-password"})).status_code == 401
    invalid = await client.post("/auth/signup", json={"email": "bad@example.com", "password": "short"})
    assert invalid.status_code == 422
    assert '"input"' not in invalid.text
    assert (await client.get("/bookings/")).status_code == 401
    assert (await client.get("/bookings/", headers={"Authorization": "Bearer malformed"})).status_code == 401
