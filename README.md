# flyrank-capstone-widget-platform

Embeddable Widget & Lead-Capture Platform — FlyRank Backend Track capstone.

Customers create widgets (signup forms / CTAs / popovers) through an
authenticated, multi-tenant admin API and install them on any website with a
single `<script>` tag. Visitor submissions travel back through a hardened
public pipeline: validated → spam-filtered → rate-limited → geo-enriched with
provider fallback → stored idempotently → surfaced in an owner dashboard.
Email/webhook side effects run as background jobs that can fail without ever
breaking the main path.

> **Status:** complete — all phases done (design · auth + multi-tenant
> widgets · hardened public pipeline · background jobs · embeddable bundle +
> dashboard). Architecture and locked decisions live in
> [docs/design.md](docs/design.md); proof per requirement in
> [EVIDENCE.md](EVIDENCE.md).

## Architecture

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

One command boots the whole stack — Postgres plus the API container, which
applies migrations before serving:

```bash
docker compose up --build
```

Then seed demo data (registers `demo-owner@example.com`, creates two widgets,
submits five leads through the public pipeline, prints dashboard stats):

```bash
scripts/seed_demo.sh
```

- Health check: <http://localhost:8000/health>
- Embed anywhere (any page on `http://localhost:5500` or another allow-listed
  origin):
  `<script src="http://localhost:8000/widget.v1.js?id=<widget_id>"></script>`
- A ready customer-site test page lives in [`site/`](site/) — serve it on port
  5500 (`python3 -m http.server 5500 --directory site`) and open
  <http://localhost:5500/?widget=<widget_id>>.

### Local development (without the API container)

```bash
docker compose up -d db          # Postgres only
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp .env.example .env             # adjust if your DB differs
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --port 8000
.venv/bin/pytest                 # spins up its own throwaway test database
```

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
