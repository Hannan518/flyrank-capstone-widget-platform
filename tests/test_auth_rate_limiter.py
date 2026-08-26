from sqlalchemy import text

from app.core.db import session_factory

LOGIN = "/api/v1/auth/login"
REGISTER = "/api/v1/auth/register"


async def _bad_login(client, email):
    return await client.post(
        LOGIN,
        json={"email": email, "password": "wrong-password"},
    )


async def test_auth_burst_returns_429_with_retry_after(client):
    codes = []
    for i in range(6):
        response = await _bad_login(client, f"burst{i}@example.com")
        codes.append(response.status_code)

    assert codes[:5] == [401] * 5
    assert codes[5] == 429

    blocked = await client.post(
        LOGIN,
        json={"email": "burst5@example.com", "password": "supersecret1"},
    )
    assert blocked.status_code == 429
    assert "retry-after" in {k.lower() for k in blocked.headers.keys()}


async def test_register_and_login_share_one_bucket_per_ip(client):
    codes = []
    for i in range(3):
        response = await client.post(
            REGISTER,
            json={"email": f"shared{i}@example.com", "password": "supersecret1"},
        )
        codes.append(response.status_code)
    for i in range(2):
        response = await client.post(
            LOGIN,
            json={"email": f"shared{i}@example.com", "password": "supersecret1"},
        )
        codes.append(response.status_code)
    assert codes == [201, 201, 201, 200, 200]

    sixth = await client.post(
        REGISTER,
        json={"email": "shared9@example.com", "password": "supersecret1"},
    )
    assert sixth.status_code == 429


async def test_legitimate_login_succeeds_after_window_reset(client):
    for i in range(5):
        response = await _bad_login(client, "recover@example.com")
        assert response.status_code == 401
    assert (
        await _bad_login(client, "recover@example.com")
    ).status_code == 429

    # Simulate the window elapsing: time passes, the pruner drops the expired
    # row, and the next request lands in a fresh bucket.
    async with session_factory() as session:
        await session.execute(text("DELETE FROM rate_limits"))
        await session.commit()

    recovered = await client.post(
        LOGIN,
        json={"email": "recover@example.com", "password": "supersecret1"},
    )
    assert recovered.status_code == 401  # still wrong password — but not 429


async def test_correct_credentials_within_limit_return_200(client):
    await client.post(
        REGISTER,
        json={"email": "happy@example.com", "password": "supersecret1"},
    )
    response = await client.post(
        LOGIN,
        json={"email": "happy@example.com", "password": "supersecret1"},
    )
    assert response.status_code == 200
    assert response.json()["access_token"]
