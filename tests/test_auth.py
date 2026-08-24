async def test_register_returns_201_with_lowercased_email(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "Owner@Example.COM", "password": "supersecret1"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "owner@example.com"
    assert "id" in body


async def test_register_duplicate_email_conflicts_409(client):
    for _ in range(2):
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "dup@example.com", "password": "supersecret1"},
        )
    assert response.status_code == 409


async def test_register_invalid_email_400(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "supersecret1"},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "field_errors" in detail


async def test_register_short_password_400(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "shortpw@example.com", "password": "tiny"},
    )
    assert response.status_code == 400


async def test_login_success_token_authenticates(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "login@example.com", "password": "supersecret1"},
    )
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "supersecret1"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    widgets_response = await client.get(
        "/api/v1/widgets", headers={"Authorization": f"Bearer {token}"}
    )
    assert widgets_response.status_code == 200


async def test_login_wrong_password_401(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "wrongpw@example.com", "password": "supersecret1"},
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpw@example.com", "password": "otherpassword"},
    )
    assert response.status_code == 401


async def test_login_unknown_user_401_generic_message(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@example.com", "password": "supersecret1"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "invalid email or password"


async def test_widget_endpoints_reject_missing_token(client):
    response = await client.post(
        "/api/v1/widgets",
        json={"type": "cta", "title": "X"},
    )
    assert response.status_code == 401

    list_response = await client.get("/api/v1/widgets")
    assert list_response.status_code == 401
