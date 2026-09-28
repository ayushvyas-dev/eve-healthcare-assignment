import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app import models  # noqa: F401


@pytest_asyncio.fixture
async def client(tmp_path):
    db_path = tmp_path / "integration.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    transport = ASGITransport(app=app, client=(f"test-{uuid.uuid4()}", 12345))
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def user_headers(client):
    response = await client.post("/auth/signup", json={"email": "person@example.com", "password": "long-password-123"})
    assert response.status_code == 201
    response = await client.post("/auth/login", json={"email": "person@example.com", "password": "long-password-123"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
