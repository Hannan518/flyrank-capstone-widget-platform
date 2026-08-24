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

(pending)

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
