from uuid import uuid4

from app.services.geo.base import GeoData
from tests.conftest import (
    create_widget,
    fetch_all,
    override_geo_chain,
    post_submission,
    register_and_login,
)

US_GEO = GeoData("US", "United States", "California", "Mountain View", 37.386, -122.0838)


async def test_happy_path_stores_enriched_row_and_enqueues_email_job(client):
    headers = await register_and_login(client, "owner@example.com")
    widget = await create_widget(client, headers)
    fake = override_geo_chain(US_GEO)

    response = await post_submission(
        client, widget["id"], idempotency_key=str(uuid4())
    )

    assert response.status_code == 201, response.text
    assert len(fake.calls) == 1

    rows = await fetch_all(
        "SELECT country, city, payload FROM submissions LIMIT 1"
    )
    assert rows[0].country == "US"
    assert rows[0].city == "Mountain View"
    assert rows[0].payload["email"] == "visitor@example.com"

    jobs = await fetch_all(
        "SELECT type, status, payload FROM jobs"
    )
    assert len(jobs) == 1
    assert jobs[0].type == "confirmation_email"
    assert jobs[0].status == "pending"
    assert jobs[0].payload["to"] == "visitor@example.com"


async def test_idempotent_replay_returns_stored_with_header(client):
    headers = await register_and_login(client, "replay@example.com")
    widget = await create_widget(client, headers)
    override_geo_chain(US_GEO)
    key = str(uuid4())

    first = await post_submission(client, widget["id"], idempotency_key=key)
    second = await post_submission(client, widget["id"], idempotency_key=key)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.headers["x-idempotent-replay"] == "true"
    assert first.json()["id"] == second.json()["id"]
    rows = await fetch_all("SELECT id FROM submissions")
    assert len(rows) == 1


async def test_same_key_different_payload_silently_returns_original(client):
    headers = await register_and_login(client, "tamper@example.com")
    widget = await create_widget(client, headers)
    override_geo_chain(US_GEO)
    key = str(uuid4())

    original = await post_submission(
        client,
        widget["id"],
        fields={"email": "first@example.com"},
        idempotency_key=key,
    )
    mutated = await post_submission(
        client,
        widget["id"],
        fields={"email": "changed@example.com"},
        idempotency_key=key,
    )

    assert original.status_code == 201
    assert mutated.status_code == 200
    assert original.json()["id"] == mutated.json()["id"]

    rows = await fetch_all("SELECT payload FROM submissions")
    assert len(rows) == 1
    assert rows[0].payload["email"] == "first@example.com"


async def test_missing_required_field_400_with_field_errors(client):
    headers = await register_and_login(client, "v1@example.com")
    widget = await create_widget(client, headers)

    response = await post_submission(client, widget["id"], fields={})

    assert response.status_code == 400
    errors = response.json()["detail"]["field_errors"]
    assert any(e["field"] == "email" for e in errors)


async def test_unknown_field_rejected_400(client):
    headers = await register_and_login(client, "v2@example.com")
    widget = await create_widget(client, headers)

    response = await post_submission(
        client, widget["id"], fields={"email": "a@b.com", "hax": "x"}
    )

    assert response.status_code == 400


async def test_invalid_email_format_rejected_400(client):
    headers = await register_and_login(client, "v3@example.com")
    widget = await create_widget(client, headers)

    response = await post_submission(
        client, widget["id"], fields={"email": "not-an-email"}
    )

    assert response.status_code == 400
    errors = response.json()["detail"]["field_errors"]
    assert any("invalid email" in e["message"] for e in errors)


async def test_wrong_origin_403_and_missing_origin_403(client):
    headers = await register_and_login(client, "origin@example.com")
    widget = await create_widget(client, headers)

    evil = await post_submission(
        client, widget["id"], origin="http://evil.example.net"
    )
    none = await post_submission(client, widget["id"], origin=None)

    assert evil.status_code == 403
    assert evil.json()["detail"] == "disallowed origin"
    assert none.status_code == 403


async def test_unknown_widget_404(client):
    response = await post_submission(client, str(uuid4()))
    assert response.status_code == 404


async def test_honeypot_returns_fake_success_and_stores_nothing(client):
    headers = await register_and_login(client, "bot@example.com")
    widget = await create_widget(client, headers)
    override_geo_chain(US_GEO)

    response = await post_submission(
        client, widget["id"], honeypot="http://spam.example"
    )

    assert response.status_code == 202
    assert response.json() == {"message": "received"}
    rows = await fetch_all("SELECT id FROM submissions")
    assert rows == []


async def test_burst_returns_429_with_retry_after_header(client):
    headers = await register_and_login(client, "burst@example.com")
    widget = await create_widget(client, headers)
    override_geo_chain(US_GEO)

    codes = []
    for _ in range(6):
        response = await post_submission(client, widget["id"])
        codes.append(response.status_code)

    assert codes[:5] == [201] * 5
    assert codes[5] == 429
    assert "retry-after" in {k.lower() for k in response.headers.keys()}

    rows = await fetch_all("SELECT count(*) AS n FROM submissions")
    assert rows[0].n == 5


async def test_enrichment_failure_still_stores_row_without_geo(client):
    headers = await register_and_login(client, "degrade@example.com")
    widget = await create_widget(client, headers)
    override_geo_chain(None)

    response = await post_submission(client, widget["id"])

    assert response.status_code == 201
    rows = await fetch_all("SELECT country FROM submissions")
    assert rows[0].country is None


async def test_preflight_options_reflects_origin_for_post(client):
    headers = await register_and_login(client, "cors@example.com")

    response = await client.options(
        "/api/v1/public/submissions",
        headers={
            "Origin": "http://localhost:5500",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == "http://localhost:5500"
    assert "POST" in response.headers["access-control-allow-methods"]
