import pytest


@pytest.mark.asyncio
async def test_catalog_creation_reads_filtering_and_pagination(client, user_headers):
    assert (await client.post("/centres/", json={"name": "Unauthorized", "location": "City"})).status_code == 401

    centre_response = await client.post(
        "/centres/", json={"name": " Central Lab ", "location": " Downtown "}, headers=user_headers
    )
    assert centre_response.status_code == 201
    centre = centre_response.json()
    assert centre["name"] == "Central Lab"
    assert centre["location"] == "Downtown"

    test_response = await client.post(
        f"/centres/{centre['id']}/tests/",
        json={"name": "CBC", "price": "15.50"},
        headers=user_headers,
    )
    assert test_response.status_code == 201
    test = test_response.json()

    assert (await client.get(f"/centres/{centre['id']}")).json()["tests"][0]["id"] == test["id"]
    assert (await client.get(f"/tests/{test['id']}")).json()["price"] == "15.50"
    filtered = await client.get("/tests/", params={"centre_id": centre["id"], "limit": 500})
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["limit"] == 100
    assert len(filtered.json()["items"]) == 1

    assert (await client.get("/centres/", params={"page": 0})).status_code == 422
    assert (await client.post(f"/centres/{centre['id']}/tests/", json={"name": "Free", "price": "0"}, headers=user_headers)).status_code == 422
    assert (await client.post("/centres/00000000-0000-0000-0000-000000000000/tests/", json={"name": "CBC", "price": "1.00"}, headers=user_headers)).status_code == 404
    assert (await client.get("/tests/00000000-0000-0000-0000-000000000000")).status_code == 404
