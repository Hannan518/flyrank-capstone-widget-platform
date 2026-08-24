from tests.conftest import create_widget, register_and_login


async def test_create_widget_returns_embed_snippet(client):
    headers = await register_and_login(client, "snippet@example.com")
    widget = await create_widget(client, headers)

    assert widget["embed_snippet"].startswith("<script src=")
    expected = f"/widget.v1.js?id={widget['id']}"
    assert expected in widget["embed_snippet"]


async def test_widget_list_scoped_to_owner(client):
    headers_a = await register_and_login(client, "a@example.com")
    headers_b = await register_and_login(client, "b@example.com")

    widget_a = await create_widget(client, headers_a, title="A-widget")
    widget_b = await create_widget(client, headers_b, title="B-widget")

    list_a = (await client.get("/api/v1/widgets", headers=headers_a)).json()
    list_b = (await client.get("/api/v1/widgets", headers=headers_b)).json()

    assert [w["id"] for w in list_a] == [widget_a["id"]]
    assert [w["id"] for w in list_b] == [widget_b["id"]]


async def test_foreign_widget_get_is_404_not_403(client):
    headers_a = await register_and_login(client, "owner@example.com")
    headers_b = await register_and_login(client, "intruder@example.com")

    widget = await create_widget(client, headers_a)

    response = await client.get(f"/api/v1/widgets/{widget['id']}", headers=headers_b)
    assert response.status_code == 404
    assert response.json()["detail"] == "widget not found"


async def test_foreign_widget_patch_is_404(client):
    headers_a = await register_and_login(client, "patch-owner@example.com")
    headers_b = await register_and_login(client, "patch-intruder@example.com")

    widget = await create_widget(client, headers_a)

    response = await client.patch(
        f"/api/v1/widgets/{widget['id']}",
        json={"title": "hijacked"},
        headers=headers_b,
    )
    assert response.status_code == 404


async def test_foreign_widget_delete_is_404(client):
    headers_a = await register_and_login(client, "del-owner@example.com")
    headers_b = await register_and_login(client, "del-intruder@example.com")

    widget = await create_widget(client, headers_a)

    response = await client.delete(
        f"/api/v1/widgets/{widget['id']}", headers=headers_b
    )
    assert response.status_code == 404

    still_there = await client.get(f"/api/v1/widgets/{widget['id']}", headers=headers_a)
    assert still_there.status_code == 200


async def test_patch_updates_own_widget(client):
    headers = await register_and_login(client, "updater@example.com")
    widget = await create_widget(client, headers)

    response = await client.patch(
        f"/api/v1/widgets/{widget['id']}",
        json={"title": "Renamed", "button_text": "Join!"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Renamed"
    assert response.json()["button_text"] == "Join!"


async def test_delete_then_get_404(client):
    headers = await register_and_login(client, "deleter@example.com")
    widget = await create_widget(client, headers)

    delete_response = await client.delete(
        f"/api/v1/widgets/{widget['id']}", headers=headers
    )
    assert delete_response.status_code == 204

    get_response = await client.get(f"/api/v1/widgets/{widget['id']}", headers=headers)
    assert get_response.status_code == 404


async def test_create_rejects_unknown_fields_400(client):
    headers = await register_and_login(client, "strict@example.com")
    response = await client.post(
        "/api/v1/widgets",
        json={"type": "cta", "title": "X", "hax": True},
        headers=headers,
    )
    assert response.status_code == 400


async def test_create_rejects_invalid_origin_400(client):
    headers = await register_and_login(client, "origins@example.com")
    response = await client.post(
        "/api/v1/widgets",
        json={
            "type": "cta",
            "title": "X",
            "allowed_origins": ["ftp://nope", "javascript:alert(1)"],
        },
        headers=headers,
    )
    assert response.status_code == 400
