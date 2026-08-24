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

Automated suite run (Phase 3): `pytest -q`

```text
.........................................                                [100%]
41 passed in 33.07s
```

- **Public POST endpoint accepts submissions for known widgets** —
  `test_happy_path_stores_enriched_row_and_enqueues_email_job` (201 + row +
  queued job).
- **Idempotency-Key honored; replays return stored response without creating a
  duplicate** — live gate transcript below (`200` + `x-idempotent-replay:
  true`, one row), plus `test_idempotent_replay_returns_stored_with_header`
  and `test_same_key_different_payload_silently_returns_original`.
- **Validation errors are structured JSON** (`400 {field_errors}`) —
  `test_missing_required_field_400_with_field_errors`,
  `test_unknown_field_rejected_400`, `test_invalid_email_format_rejected_400`.

Live cross-origin gate against a running server
(`scripts/demo_gate.sh`, dev fallback IP geolocated via ip-api.com):

```text
== health ==                       {"status":"ok","database":"ok"}
== create widget ==                widget: 5808d416-c783-4e07-bb37-874329201dcb
== cross-origin submission ==      HTTP/1.1 201 Created
                                   {"id":"8cd9b62d-eeb9-45e7-bae0-2cd89df1eeac"}
== replay same key ==              HTTP/1.1 200 OK / x-idempotent-replay: true
== disallowed origin ==            403
== malformed payload ==            400
== honeypot filled ==              202
```

## Abuse protection

From the same live gate transcript:

```text
== burst until window cap ==       201 201 201 429 429 429
```

(the two earlier accepted posts had already consumed part of the 5-per-60 s
per-(ip,widget) window; the cap held and 429 carries `Retry-After`)

- **Rate limiting works** — `test_blocks_after_ip_limit_and_reports_retry_after`
  (5 allowed, 6th blocked with bounded Retry-After),
  `test_limits_are_scoped_per_widget_and_ip` (other widget / other ip
  unaffected), `test_prune_removes_only_expired_rows`.
- **Honeypot silently rejects** — `test_honeypot_returns_fake_success_and_
  stores_nothing` (202 fake success, zero rows).

## Enrichment & safe side effects

Live proof from the gate transcript — visitor IPs enriched before storage,
side effect processed by the outbox worker off-path:

```text
 country |  city   |  region  |       email
---------+---------+----------+-------------------
 US      | Ashburn | Virginia | burst@example.com
 US      | Ashburn | Virginia | lead@example.com

 type                | status | attempts
---------------------+--------+----------
 confirmation_email  | done   |        1

INFO:app.services.mailers:[fake email] To: lead@example.com |
Subject: Thanks for signing up via Gate Widget | Body: Your submission was received.
```

- **IP-based enrichment** — geo chain unit tests
  `test_falls_back_to_second_provider_on_failure`,
  `test_budget_exhaustion_skips_later_providers`,
  `test_returns_none_when_all_providers_fail`; pipeline degrades to a row
  with null geo when every provider is down
  (`test_enrichment_failure_still_stores_row_without_geo`).
- **Side effects happen later, not in the request path** — submission handler
  only enqueues; worker claims and delivers:
  `test_successful_job_marked_done`, `test_failing_job_is_retried_with_backoff`
  (status pending, attempts+1, next_attempt_at in future),
  `test_terminal_failure_marks_failed_permanent`.

## Tests & documentation

(pending)
