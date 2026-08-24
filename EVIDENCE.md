# EVIDENCE

One pasted proof per Definition-of-Done checkbox (brief §6), appended as each
box goes green — not retroactively. A claim without evidence scores as not
done, so nothing here is written ahead of its proof.

## Toolchain (Phase 0)

`docker compose up -d` — Postgres 16 reaches `healthy`, port mapped:

```text
CONTAINER ID   IMAGE               COMMAND                  CREATED         STATUS                    PORTS                                         NAMES
907baffc00d8   postgres:16-alpine  "docker-entrypoint.s…"   8 seconds ago   Up 6 seconds (healthy)    0.0.0.0:5432->5432/tcp, [::]:5432->5432/tcp   widget-platform-db
```

App booted against the containerized DB; `GET /health` pings the database with `SELECT 1`:

```text
GATE-RESULT: HTTP-200 {"status":"ok","database":"ok"}
```

A DB outage degrades honestly instead of lying (handler returns 503
`{"status":"degraded","database":"unavailable"}` on connection failure).

## Widget management

Automated suite run (Phase 2): `pytest -q`

```text
.................                                                        [100%]
17 passed in 25.99s
```

- **Authenticated CRUD; requests without valid auth are rejected** —
  `test_widget_endpoints_reject_missing_token` (create + list → 401),
  `test_login_wrong_password_401`, `test_login_unknown_user_401_generic_message`.
- **Multi-tenant isolation proven: tenant A cannot read or modify tenant B's
  widgets** — `test_widget_list_scoped_to_owner` (each owner sees only their
  own), `test_foreign_widget_get_is_404_not_403`,
  `test_foreign_widget_patch_is_404`, `test_foreign_widget_delete_is_404`
  (foreign delete → 404 and the row survives for its real owner).
- **Embed snippet generated per widget** — `test_create_widget_returns_embed_snippet`
  asserts `<script src="…/widget.v1.js?id={id}"></script>` shape.
- Honest codes: unknown-field payloads → 400 via normalized validation errors
  (`test_create_rejects_unknown_fields_400`, `test_create_rejects_invalid_origin_400`);
  foreign resources answer **404** (never 403) so cross-tenant existence is
  not leaked.

## Widget delivery

(pending)

## Public submission API

(pending)

## Abuse protection

(pending)

## Enrichment & safe side effects

(pending)

## Tests & documentation

(pending)
