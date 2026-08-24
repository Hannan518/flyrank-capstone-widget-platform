# BUILDLOG — AI usage log

Honest record of where AI helped, where it was wrong, and what I changed.
Honesty is graded; perfection is not.

## 2026-08-24 — Kickoff & planning

- Read the capstone brief and built the phased plan interactively with an AI
  assistant (opencode). The plan, not the code, is the deliverable of this
  entry: phase gates, stack choice, and repo rules came out of that session.
- Key design decisions were stress-tested against the AI's first proposal and
  revised twice before locking:
  - Idempotency keys: client-generated UUID v4 from `widget.js` (the AI's
    initial plan had the DB constraint but no key source — closed in review).
  - Rate limiting: moved from in-memory token bucket to Postgres-backed
    fixed-window counters after the multi-worker flaw was pointed out.
  - Added a second background job (scheduled pruning) after the unbounded-
    growth gap was identified in review.
- Scaffolding files written with AI assistance; every line reviewed by me
  before committing. Nothing is committed unread.

Design rationale and full decision records will live in `docs/design.md`
(Phase 1) rather than duplicated here.
