from uuid import uuid4

from app.services.geo.base import GeoData
from tests.conftest import (
    create_widget,
    override_geo_chain,
    post_submission,
    register_and_login,
)

US_GEO = GeoData("US", "United States", "California", "Mountain View", 37.386, -122.0838)


async def _seed_submissions(client, email, count, *, origin="http://localhost:5500"):
    headers = await register_and_login(client, email)
    widget = await create_widget(client, headers)
    override_geo_chain(US_GEO)
    ids = []
    for i in range(count):
        response = await post_submission(
            client,
            widget["id"],
            fields={"email": f"{i}-{email}"},
            origin=origin,
        )
        assert response.status_code == 201, response.text
        ids.append(response.json()["id"])
    return headers, widget, ids


async def test_config_returns_render_config_only(client):
    headers = await register_and_login(client, "cfg@example.com")
    widget = await create_widget(
        client,
        headers,
        title="Config Widget",
        description="hello",
        button_text="Join!",
        display_options={"position": "bottom-right"},
    )

    response = await client.get(f"/api/v1/public/widgets/{widget['id']}/config")

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "signup_form"
    assert body["title"] == "Config Widget"
    assert body["description"] == "hello"
    assert body["button_text"] == "Join!"
    assert body["display_options"] == {"position": "bottom-right"}
    assert body["fields"][0]["name"] == "email"
    forbidden_keys = {
        "allowed_origins",
        "owner",
        "owner_id",
        "embed_snippet",
        "created_at",
    }
    assert forbidden_keys.isdisjoint(body.keys())


async def test_config_unknown_or_malformed_id_404(client):
    assert (
        await client.get(f"/api/v1/public/widgets/{uuid4()}/config")
    ).status_code == 404
    assert (
        await client.get("/api/v1/public/widgets/not-a-uuid/config")
    ).status_code == 404


async def test_config_cache_headers_and_cors_echo(client):
    headers = await register_and_login(client, "cachecfg@example.com")
    widget = await create_widget(client, headers)

    allowed = await client.get(
        f"/api/v1/public/widgets/{widget['id']}/config",
        headers={"Origin": "http://localhost:5500"},
    )
    assert allowed.headers["cache-control"] == "public, max-age=30"
    assert allowed.headers["vary"] == "Origin"
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5500"

    stranger = await client.get(
        f"/api/v1/public/widgets/{widget['id']}/config",
        headers={"Origin": "http://evil.example.net"},
    )
    assert stranger.status_code == 200
    assert "access-control-allow-origin" not in stranger.headers


async def test_versioned_bundle_served_immutable(client):
    headers = await register_and_login(client, "js@example.com")
    widget = await create_widget(client, headers)

    response = await client.get(f"/widget.v1.js?id={widget['id']}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/javascript")
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert b"data-flyrank-widget" in response.content
    assert b"idempotency_key" in response.content


async def test_bundle_alias_served_short_cache(client):
    headers = await register_and_login(client, "alias@example.com")
    widget = await create_widget(client, headers)

    response = await client.get(f"/widget.js?id={widget['id']}")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=60"


async def test_bundle_unknown_widget_404(client):
    assert (await client.get(f"/widget.v1.js?id={uuid4()}")).status_code == 404
    assert (await client.get("/widget.js?id=nope")).status_code == 404


async def test_dashboard_submissions_paginated_no_duplicates(client):
    _, _, ids = await _seed_submissions(client, "pager@example.com", 3)

    page1 = await client.get(
        "/api/v1/dashboard/submissions",
        params={"limit": 2},
        headers=await _auth(client, "pager@example.com"),
    )
    assert page1.status_code == 200
    data = page1.json()
    assert len(data["items"]) == 2
    assert data["next_cursor"]

    seen = [item["id"] for item in data["items"]]
    page2 = await client.get(
        f"/api/v1/dashboard/submissions?cursor={data['next_cursor']}",
        headers=await _auth(client, "pager@example.com"),
    )
    data2 = page2.json()
    seen += [item["id"] for item in data2["items"]]

    assert sorted(seen) == sorted(ids)
    assert len(seen) == len(set(seen))


async def _auth(client, email):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "supersecret1"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_dashboard_widget_filter_and_foreign_404(client):
    headers_a, widget_a, _ = await _seed_submissions(
        client, "ownera@example.com", 1
    )
    headers_b, widget_b, _ = await _seed_submissions(
        client, "ownerb@example.com", 1
    )

    filtered = await client.get(
        f"/api/v1/dashboard/submissions?widget_id={widget_a['id']}",
        headers=headers_a,
    )
    assert filtered.status_code == 200
    items = filtered.json()["items"]
    assert len(items) == 1
    assert items[0]["widget_id"] == widget_a["id"]

    foreign = await client.get(
        f"/api/v1/dashboard/submissions?widget_id={widget_b['id']}",
        headers=headers_a,
    )
    assert foreign.status_code == 404


async def test_dashboard_rejects_missing_auth_bad_cursor_bad_limit(client):
    anonymous = await client.get("/api/v1/dashboard/submissions")
    assert anonymous.status_code == 401

    headers = await register_and_login(client, "guards@example.com")

    bad_cursor = await client.get(
        "/api/v1/dashboard/submissions",
        params={"cursor": "@@@not-base64@@@"},
        headers=headers,
    )
    assert bad_cursor.status_code == 400

    big_limit = await client.get(
        "/api/v1/dashboard/submissions",
        params={"limit": 101},
        headers=headers,
    )
    assert big_limit.status_code == 400


async def test_stats_shape_tenant_scope_and_geo(client):
    override_geo_chain(US_GEO)
    headers_a, widget_a, _ = await _seed_submissions(client, "statsa@example.com", 2)
    widget_y = await create_widget(client, headers_a, title="Second Widget")
    extra = await post_submission(
        client, widget_y["id"], fields={"email": "y@example.com"}
    )
    assert extra.status_code == 201
    await _seed_submissions(client, "statsb@example.com", 1)

    response = await client.get("/api/v1/dashboard/stats", headers=headers_a)

    assert response.status_code == 200
    stats = response.json()
    assert stats["total"] == 3
    per_widget = {entry["title"]: entry["count"] for entry in stats["per_widget"]}
    assert per_widget == {"Newsletter": 2, "Second Widget": 1}
    assert {p["count"] for p in stats["timeseries"]} == {3}
    assert stats["geo"] == [{"country": "US", "count": 3}]
    assert {w["widget_id"] for w in stats["per_widget"]} <= {
        widget_a["id"],
        widget_y["id"],
    }


async def test_stats_days_validation(client):
    headers = await register_and_login(client, "daysval@example.com")

    assert (
        await client.get("/api/v1/dashboard/stats", params={"days": 0}, headers=headers)
    ).status_code == 400
    assert (
        await client.get(
            "/api/v1/dashboard/stats", params={"days": 91}, headers=headers
        )
    ).status_code == 400
    assert (
        await client.get("/api/v1/dashboard/stats", params={"days": 7}, headers=headers)
    ).status_code == 200


async def test_submission_row_carries_enrichment_into_dashboard(client):
    headers, _, _ = await _seed_submissions(client, "geoout@example.com", 1)

    response = await client.get("/api/v1/dashboard/submissions", headers=headers)
    item = response.json()["items"][0]
    assert item["country"] == "US"
    assert item["city"] == "Mountain View"
    assert item["region"] == "California"
    assert item["latitude"] == 37.386
    assert item["payload"]["email"].endswith("@example.com")
