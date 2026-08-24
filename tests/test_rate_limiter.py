import asyncio

from app.core.db import session_factory
from app.repositories import rate_limit_repo
from app.services.rate_limiter import enforce_submission_limits, window_start
from datetime import datetime, timedelta, timezone


async def test_blocks_after_ip_limit_and_reports_retry_after():
    widget_id = "11111111-1111-1111-1111-111111111111"
    ip = "203.0.113.9"

    verdicts = []
    for _ in range(6):
        async with session_factory() as session:
            verdicts.append(await enforce_submission_limits(session, ip, widget_id))
            await session.commit()

    assert all(v.allowed for v in verdicts[:5])
    final = verdicts[5]
    assert not final.allowed
    assert 1 <= final.retry_after_seconds <= 60


async def test_limits_are_scoped_per_widget_and_ip():
    widget_a = "22222222-2222-2222-2222-222222222222"
    widget_b = "33333333-3333-3333-3333-333333333333"

    async with session_factory() as session:
        first = await enforce_submission_limits(session, "198.51.100.1", widget_a)
        await session.commit()
    async with session_factory() as session:
        other_widget = await enforce_submission_limits(
            session, "198.51.100.1", widget_b
        )
        await session.commit()
    async with session_factory() as session:
        other_ip = await enforce_submission_limits(session, "198.51.100.2", widget_a)
        await session.commit()

    assert first.allowed and other_widget.allowed and other_ip.allowed


async def test_window_start_aligns_to_epoch_slots():
    now = datetime(2026, 8, 24, 12, 0, 37, tzinfo=timezone.utc)
    aligned = window_start(now, 60)
    assert aligned.second == 0
    assert aligned.minute == 0
    assert aligned.tzinfo is not None


async def test_prune_removes_only_expired_rows():
    old_start = datetime.now(timezone.utc) - timedelta(hours=2)
    fresh_start = window_start(datetime.now(timezone.utc), 60)
    async with session_factory() as session:
        await rate_limit_repo.increment(session, "a" * 64, old_start)
        await rate_limit_repo.increment(session, "b" * 64, fresh_start)
        removed = await rate_limit_repo.prune_expired(
            session, datetime.now(timezone.utc) - timedelta(hours=1)
        )
        await session.commit()
    assert removed == 1
