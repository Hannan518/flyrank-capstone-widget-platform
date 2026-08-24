# Design Doc — Embeddable Widget & Lead-Capture Platform

FlyRank Backend Track capstone · Phase 1 deliverable · status: **awaiting owner sign-off**

---

## 1 · Problem & scope

Customers define widgets (signup forms / CTAs / popovers) through an
authenticated admin API and install them on any website with one line of
`<script>`. Visitors on those sites submit through a **public** endpoint that
belongs to no one and is hit by everyone: it must validate, resist abuse,
enrich, store idempotently, and trigger side effects that can fail without
breaking the main path. Widget owners see their leads and stats in a dashboard
API.

Three actor paths, kept separate in head and code:

1. **Owner** (authenticated) — manages widgets, reads dashboard.
2. **Customer site** (any origin) — loads the versioned widget script + config.
3. **Visitor** (anonymous, untrusted) — submits leads.

Success criteria: every Definition-of-Done box green with evidence, all six
acceptance probes passing.

## 2 · Data model & indexes

```text
users(id uuid pk · email citext unique not null · password_hash not null · created_at)

widgets(id uuid pk
        · owner_id → users.id not null          -- tenant boundary, in EVERY query
        · type text check in ('signup_form','cta','popover') not null
        · title varchar(120) not null
        · description text null
        · fields jsonb not null default '[]'    -- [{name,label,type∈(text,email,textarea),required}]
        · button_text varchar(60) not null default 'Submit'
        · display_options jsonb not null default '{}'   -- position/theme/delay_seconds
        · allowed_origins text[] not null default '{}'  -- per-widget CORS allowlist; empty ⇒ fail closed
        · created_at · updated_at)
        idx_widgets_owner: (owner_id)

submissions(id uuid pk
        · widget_id → widgets.id not null
        · tenant_id uuid not null               -- denormalized owner_id: isolation without JOINs
        · payload jsonb not null                -- validated field values only
        · idempotency_key varchar(64) null      -- client-generated, see §6.1
        · country varchar(2)? · city? · region? -- enrichment, nullable by design
        · latitude? · longitude?
        · ip_address inet not null · user_agent text null · created_at)
        UNIQUE partial: uq_submissions_idem (widget_id, idempotency_key)
                        WHERE idempotency_key IS NOT NULL
        idx_sub_widget_time: (widget_id, created_at DESC)   -- per-widget timeseries
        idx_sub_tenant_time: (tenant_id, created_at DESC)   -- tenant-scoped dashboard

jobs(id bigserial pk
        · type text check in ('confirmation_email','webhook') not null
        · payload jsonb not null
        · submission_id uuid null references submissions(id)
        · status text check in ('pending','processing','done','failed_permanent')
                not null default 'pending'
        · attempts int not null default 0 · max_attempts int not null default 5
        · next_attempt_at timestamptz not null default now()
        · last_error text null · claimed_at timestamptz null
        · created_at · updated_at)
        idx_jobs_poll: (status, next_attempt_at)

rate_limits(scope_key text not null            -- sha256("ip|widget") or "widget|<id>" global tier
        · window_start timestamptz not null    -- epoch aligned to window size
        · count int not null default 0,
        PK (scope_key, window_start))
        idx_rate_window: (window_start)        -- pruning path
```

Why these shapes:

- **Window inside the PK**: an `ON CONFLICT` can only ever collide with the
  *current* window's row, so stale rows cannot corrupt live counters, and the
  pruner can drop expired rows without touching hot data.
- **Denormalized `tenant_id`** on submissions: every dashboard query is
  tenant-scoped without a JOIN; write-time duplication is trivial.
- **404-not-403** for foreign resources: never leak cross-tenant existence.
- Migrations are Alembic, forward-only, one logical change each.

## 3 · Embed flow

```text
owner creates widget ──► API returns:
    <script src="{BASE_URL}/widget.v1.js?id=<widget_uuid>"></script>

page loads script ──► GET /widget.v1.js?id=…          (immutable cache, see below)
                 ──► GET /api/v1/public/widgets/{id}/config   (max-age=30, Vary: Origin)
                 ──► renders <div><form> from minimal config JSON

visitor submits ──► POST /api/v1/public/submissions    (pipeline §5)
```

Cache strategy:

| Asset | Cache-Control | Rationale |
|---|---|---|
| `/widget.v{n}.js` | `public, max-age=31536000, immutable` | content frozen at URL; browsers never re-validate |
| `/widget.js` (latest alias) | `public, max-age=60` | short window so new versions propagate fast |
| `/config` | `public, max-age=30` | edits visible within ~30s without hammering DB |

`WIDGET_BUNDLE_VERSION` constant bumps manually whenever the script changes;
the embed snippet pins the versioned URL, so old pages keep loading old cached
copies until republished.

## 4 · API contracts

All admin routes under `/api/v1`, Bearer JWT (HS256, 24 h expiry, secret from
env with min-length enforced at startup). Login/register share the per-IP rate
limiter.

| Method & path | Auth | Success | Errors |
|---|---|---|---|
| POST `/api/v1/auth/register` | – | 201 `{id, email}` | 400 · 409 duplicate |
| POST `/api/v1/auth/login` | – | 200 `{access_token, token_type}` | 401 |
| POST `/api/v1/widgets` | JWT | 201 widget incl. `embed_snippet` | 400 · 401 |
| GET `/api/v1/widgets` | JWT | 200 list (scoped to caller) | 401 |
| GET/PATCH/DELETE `/api/v1/widgets/{id}` | JWT | 200 · 204 | 400 · 401 · **404 foreign** |
| GET `/api/v1/dashboard/submissions` | JWT | 200 cursor page (`widget_id`, `limit`) | 400 · 401 |
| GET `/api/v1/dashboard/stats?days=30` | JWT | `{total, per_widget[], timeseries[], geo[]}` | 401 |
| GET `/widget.v{n}.js?id=` | public | 200 JS | 404 unknown widget |
| GET `/api/v1/public/widgets/{id}/config` | public | 200 render-config only (no owner data) | 404 |
| POST `/api/v1/public/submissions` | public | **201** first · **200** replay | 400 · 403 origin · 404 · 413 · 429 |

Public error bodies are always structured JSON — `{"detail": …}` or
`{"detail": {"field_errors": …}}` — never an HTML traceback, never a 500 for
bad client input.

## 5 · Submission pipeline — order *is* the design

```text
① size guard          Content-Length > 64 KiB ⇒ 413 (checked before reading body)
② resolve widget      unknown ⇒ 404
③ origin check        server-side re-check vs widget.allowed_origins ⇒ 403 disallowed_origin
                      (CORSMiddleware handles browser-visible behavior; curl sends no Origin)
④ schema validation   fields vs widget.fields definition ⇒ 400 {field_errors}
⑤ honeypot            filled ⇒ silent fake-success 202, logged spam_honeypot, nothing stored
⑥ rate limits         per-(ip,widget) tier then global per-widget tier ⇒ 429 + Retry-After
⑦ idempotency         key present ⇒ INSERT … ON CONFLICT DO NOTHING RETURNING;
                      empty result ⇒ SELECT winner ⇒ 200 stored row + X-Idempotent-Replay: true
⑧ enrichment          provider A → provider B → none; hard timeout budget 2 s total
⑨ persist             BEGIN: INSERT submission + INSERT outbox job COMMIT   ← atomic
⑩ respond             201 {id} — side effects happen later, off-path
```

Design rules embedded in this order:

- Bad input dies **before** touching limiter or storage (cheap checks first).
- The honeypot reply is indistinguishable from success so bots learn nothing.
- Enrichment failure and job-insertion failure can degrade the response's
  *richness*, never its correctness: a submission either stores or returns a
  clean 4xx/5xx — it never half-happens.

## 6 · Locked decisions (sign-off sections)

### 6.1 Idempotency design

- **Source:** `widget.js` calls `crypto.randomUUID()` at render time, injects
  it as hidden field `idempotency_key`, and reuses it across automatic retries
  of that logical submission (fetch-wrapper level); regenerates only after a
  confirmed success so a visitor may submit again.
- **Server:** partial unique index `(widget_id, idempotency_key) WHERE
  idempotency_key IS NOT NULL`; conflict path is
  `INSERT … ON CONFLICT DO NOTHING RETURNING *` — empty result means select the
  winner and return it. One round-trip, race-proof, no exception control flow.
- **Replies:** first submission `201`; replay `200` with the stored submission
  plus `X-Idempotent-Replay: true`.
- **Tamper semantics (deliberate):** same key + different payload silently
  returns the original submission. Unlike Stripe, our submitters are anonymous
  and untrusted — they control both key and payload generation, so mismatch
  detection creates no security boundary (an attacker mints a fresh key);
  abuse prevention is honeypot/rate-limiting's jurisdiction. Legitimate drift
  cannot occur through our own first-party path because the retry wrapper
  resends a byte-identical body. A test pins this behavior.
- **Missing key:** allowed (old cached script versions, direct API callers);
  dedupe simply doesn't apply — hence the *partial* index.
- Key format validated like any other field (UUID, ≤64 chars).

### 6.2 Rate-limiting design

- **Backend:** Postgres fixed-window counters in `rate_limits`
  (§2). Atomic increment-and-check in one statement:

  ```sql
  INSERT INTO rate_limits (scope_key, window_start, count)
  VALUES ($1, $2, 1)
  ON CONFLICT (scope_key, window_start)
  DO UPDATE SET count = rate_limits.count + 1
  RETURNING count;
  ```

  Compare against the limit; exceed ⇒ 429 with `Retry-After =
  window_end − now`.
- **Tiers:** per `(ip, widget)` — `sha256(ip|widget_id)` so raw IPs aren't
  stored as keys — plus a global per-widget tier to blunt distributed floods
  aimed at one widget. Limits/window sizes from env config.
- **Why Postgres:** correct under any number of worker processes, zero new
  infrastructure, deterministic tests. Redis is the named swap for horizontal
  scale (limiter sits behind a protocol interface).
- **Pruning:** scheduled job (§6.3) deletes `window_start` older than twice
  the largest window. Table stays tiny; index keeps the sweep indexed.
- **Accepted tradeoff:** fixed windows permit up to 2× the limit across a
  window boundary; sliding-window/Redis is the upgrade path. Stated in README
  limitations.

### 6.3 Background jobs architecture

Two distinct jobs, two patterns — covering the program's "≥1 background job"
requirement with both event-driven and scheduled styles:

1. **Outbox worker** (event-driven): polls `jobs` every 2 s; claims atomically
   via `FOR UPDATE SKIP LOCKED`; retry backoff `min(60·2^attempts, 3600)s`;
   exhausting `max_attempts` ⇒ status `failed_permanent` + CRITICAL alert log
   line. Handler `confirmation_email` talks to a `Mailer` protocol
   (console logger locally; Mailpit SMTP optional). The outbox row is inserted
   in the *same transaction* as the submission (§5⑨), so "stored but never
   e-mailed" is impossible.
2. **Scheduled pruner** (cron-style): lifespan-managed asyncio task, sweeps
   expired `rate_limits` rows and terminal-state `jobs` past retention
   (done >7 days), logs `pruned N rows` each run — free evidence material.
   Wrapped in try/except with alert-log; self-heals next tick.

**Limitation (deliberate):** background jobs run in-process; multi-instance
deployment would need a job-claiming mechanism (e.g. `SELECT ... FOR UPDATE
SKIP LOCKED`) to avoid redundant pruning work. Note: the outbox worker already
claims atomically via exactly that pattern; the pruner is idempotent, so
multi-instance redundancy would be wasted work, not corruption.

## 7 · Layer sketch

```text
api/admin/*.py · api/public/*.py     HTTP ↔ Pydantic schemas ONLY (parse/respond)
        │ Depends(get_current_user) · Depends(get_session)
services/*.py                        business logic · transaction boundaries
        │
repos/*.py                           SQL only · tenant_id in EVERY query
providers/                           GeoProvider + Mailer Protocols; DI via Depends
core/                                config(.env) · security(JWT/bcrypt) · errors · CORS
jobs/                                worker.py · pruner.py · handlers.py
alembic/                             migrations
tests/                               mapped 1:1 to DoD boxes + six probes
site/index.html                      customer-site test page (second local port)
```

Rule enforced by review: swapping Postgres or a geo provider must not require
touching `services/` logic beyond the injected implementation. Providers get
strict httpx timeouts; mocks implement the same Protocol for tests.

## 8 · Non-goal & limitations

**Explicit non-goal:** *No visual form-builder / widget editor UI.* The admin
surface is a JSON API only. This capstone proves backend patterns — multi-
tenant CRUD, hardened public endpoints, resilience engineering — not frontend.

Carried limitations (also surfaced in README):

- Background jobs run in-process; multi-instance deployment would need a
  job-claiming mechanism (e.g. `SELECT ... FOR UPDATE SKIP LOCKED`) to avoid
  redundant pruning work.
- Fixed-window rate limiting permits ≤2× burst across window boundaries.
- Tenancy model is user-as-tenant; a `tenants` table + membership is the
  growth path if org-level tenancy is ever needed.

## 9 · Security notes

- Secrets only from env; `.env` git-ignored from commit zero;
  `.env.example` documents every variable.
- bcrypt password hashing; JWT HS256 with startup-time secret length check.
- CORS fail-closed: empty `allowed_origins` ⇒ no cross-origin access.
- Every query tenant-scoped at the repo layer, not the router layer.
- Raw SQL only where it buys atomicity (limiter upsert, job claim); everything
  else through SQLAlchemy Core/ORM constructs — no string interpolation.
