import asyncio
import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://widget:widget@localhost:5432/widget_platform_test",
)
os.environ.setdefault("APP_ENV", "test")

import pytest
from httpx import ASGITransport, AsyncClient

TEST_DB_NAME = "widget_platform_test"


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    import asyncpg

    async def _recreate():
        conn = await asyncpg.connect(
            "postgresql://widget:widget@localhost:5432/postgres"
        )
        await conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}")
        await conn.execute(f"CREATE DATABASE {TEST_DB_NAME}")
        await conn.close()

    asyncio.run(_recreate())

    from alembic import command
    from alembic.config import Config

    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    command.upgrade(config, "head")
    yield


@pytest.fixture(autouse=True)
async def clean_tables(migrated_database):
    yield
    from sqlalchemy import text

    from app.core.db import engine

    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE widgets, users CASCADE"))


@pytest.fixture
async def client():
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


async def register_and_login(client, email, password="supersecret1"):
    response = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": password}
    )
    assert response.status_code == 201, response.text
    login_response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert login_response.status_code == 200, login_response.text
    return {"Authorization": f"Bearer {login_response.json()['access_token']}"}


async def create_widget(client, headers, **overrides):
    payload = {
        "type": "signup_form",
        "title": "Newsletter",
        "fields": [
            {"name": "email", "label": "Email", "type": "email", "required": True}
        ],
        "allowed_origins": ["http://localhost:5500"],
    }
    payload.update(overrides)
    response = await client.post("/api/v1/widgets", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()
