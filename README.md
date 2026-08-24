# flyrank-capstone-widget-platform

Embeddable Widget & Lead-Capture Platform — FlyRank Backend Track capstone.

Customers create widgets (signup forms / CTAs / popovers) through an
authenticated, multi-tenant admin API and install them on any website with a
single `<script>` tag. Visitor submissions travel back through a hardened
public pipeline: validated → spam-filtered → rate-limited → geo-enriched with
provider fallback → stored idempotently → surfaced in an owner dashboard.
Email/webhook side effects run as background jobs that can fail without ever
breaking the main path.

> **Status:** in development (Phase 0 — scaffold). Design doc lands in Phase 1
> at `docs/design.md`.

## Architecture (planned)

```text
Widget Owner (authenticated)
    └─► Widget Management API ─► Widget DB (tenant-isolated) ─► embed snippet

Customer Website (any origin)
    └─ <script src="widget.js?id=123">
           └─► GET /widgets/:id/config   (public · cached · CORS)
                   └─► render widget

Website Visitor
    └─► POST /submissions   (public · CORS)
           ├─► validation             ── bad payload? → 4xx, never 500
           ├─► rate limit + honeypot  ── flood/spam? → 429 or silent drop; service stays up
           ├─► geo enrichment chain   ── provider A → provider B → store anyway
           ├─► store submission       ── idempotent by client-generated key
           └─► outbox job: email/webhook (failure must NOT block success)

Widget Owner (authenticated)
    └─► Dashboard API ◄── submissions + stats
```

## Stack

FastAPI · PostgreSQL 16 (Docker Compose) · SQLAlchemy 2 async + Alembic ·
JWT auth · httpx · pytest

## Quickstart

Coming online in Phase 2. The finished project will run with one command:

```bash
docker compose up
```

plus a documented seed step for demo data.

## Repository files

| File | Purpose |
|---|---|
| `capstone.yaml` | Evaluator manifest: `run:` / `seed:` / `test:` / endpoints |
| `EVIDENCE.md` | Pasted proof per Definition-of-Done checkbox |
| `BUILDLOG.md` | Honest AI-usage log: what helped, what was wrong, what changed |
| `.env.example` | Every environment variable with safe placeholder values |

## Limitations

Tracked honestly as they are introduced; consolidated in the design doc:

- Background jobs run in-process; multi-instance deployment would need a
  job-claiming mechanism (e.g. `SELECT ... FOR UPDATE SKIP LOCKED`) to avoid
  redundant pruning work.

## License

[MIT](LICENSE)
