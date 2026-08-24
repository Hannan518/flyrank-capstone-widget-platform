from datetime import datetime, timedelta, timezone

from app.core.db import session_factory
from app.jobs.outbox_worker import OutboxWorker, Pruner
from app.repositories import job_repo
from app.services.mailers import ConsoleMailer


class FailingMailer:
    name = "failing"

    async def send_confirmation(self, to_email: str, widget_title: str) -> None:
        raise RuntimeError("smtp down")


class OkMailer(ConsoleMailer):
    name = "ok"


async def _seed_job(payload=None):
    async with session_factory() as session:
        job = await job_repo.enqueue(
            session,
            job_type="confirmation_email",
            payload=payload or {"to": "v@example.com", "widget_title": "T"},
        )
        await session.commit()
        return job.id


async def test_successful_job_marked_done():
    from sqlalchemy import text

    job_id = await _seed_job()
    worker = OutboxWorker(session_factory, OkMailer())

    handled = await worker._claim_and_process_one()

    assert handled is True
    async with session_factory() as session:
        row = (
            await session.execute(
                text("SELECT status FROM jobs WHERE id=:id"), {"id": job_id}
            )
        ).scalar_one()
    assert row == "done"


async def test_failing_job_is_retried_with_backoff():
    from sqlalchemy import text

    job_id = await _seed_job()
    worker = OutboxWorker(session_factory, FailingMailer())

    handled = await worker._claim_and_process_one()

    assert handled is True
    async with session_factory() as session:
        row = (
            await session.execute(
                text(
                    "SELECT status, attempts, last_error, next_attempt_at FROM jobs "
                    "WHERE id=:id"
                ),
                {"id": job_id},
            )
        ).one()
    assert row.status == "pending"
    assert row.attempts == 1
    assert "smtp down" in row.last_error
    assert row.next_attempt_at > datetime.now(timezone.utc)


async def test_terminal_failure_marks_failed_permanent():
    from sqlalchemy import text

    async with session_factory() as session:
        job = await job_repo.enqueue(
            session,
            job_type="confirmation_email",
            payload={"to": "v@example.com", "widget_title": "T"},
        )
        job.attempts = 4
        await session.commit()
        job_id = job.id

    worker = OutboxWorker(session_factory, FailingMailer())
    await worker._claim_and_process_one()

    async with session_factory() as session:
        row = (
            await session.execute(
                text("SELECT status FROM jobs WHERE id=:id"), {"id": job_id}
            )
        ).scalar_one()
    assert row == "failed_permanent"


async def test_pruner_sweeps_expired_windows_and_done_jobs():
    from sqlalchemy import text

    old_window_start = datetime.now(timezone.utc) - timedelta(hours=3)
    async with session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO rate_limits (scope_key, window_start, count) "
                "VALUES (:k, :w, 3)"
            ),
            {"k": "a" * 64, "w": old_window_start},
        )
        await session.execute(
            text("SELECT setval(pg_get_serial_sequence('jobs','id'), 1, false)")
        )
        done_job = await job_repo.enqueue(
            session, job_type="confirmation_email", payload={}
        )
        await session.execute(
            text(
                "UPDATE jobs SET status='done', "
                "updated_at = now() - interval '10 days' WHERE id=:id"
            ),
            {"id": done_job.id},
        )
        await session.commit()

    pruner = Pruner(
        session_factory,
        interval_seconds=60,
        rate_limit_retention_seconds=7200,
        job_retention_days=7,
    )
    stats = await pruner.sweep_once()

    assert stats["rate_limits"] >= 1
    assert stats["jobs"] >= 1
