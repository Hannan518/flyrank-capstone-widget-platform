from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job


@dataclass(frozen=True)
class ClaimedJob:
    id: int
    type: str
    payload: dict[str, Any]
    attempts: int
    max_attempts: int


_CLAIM = text(
    """
    UPDATE jobs
    SET status = 'processing',
        claimed_at = now(),
        attempts = attempts + 1,
        updated_at = now()
    WHERE id = (
        SELECT id FROM jobs
        WHERE status = 'pending' AND next_attempt_at <= now()
        ORDER BY next_attempt_at
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    )
    RETURNING id, type, payload, attempts, max_attempts
    """
)


async def enqueue(
    session: AsyncSession,
    *,
    job_type: str,
    payload: dict[str, Any],
    submission_id: str | None = None,
) -> Job:
    job = Job(type=job_type, payload=payload, submission_id=submission_id)
    session.add(job)
    await session.flush()
    return job


async def claim_next(session: AsyncSession) -> ClaimedJob | None:
    result = await session.execute(_CLAIM)
    row = result.mappings().first()
    if row is None:
        return None
    return ClaimedJob(
        id=int(row["id"]),
        type=str(row["type"]),
        payload=dict(row["payload"]),
        attempts=int(row["attempts"]),
        max_attempts=int(row["max_attempts"]),
    )


async def mark_done(session: AsyncSession, job_id: int) -> None:
    await session.execute(
        text(
            "UPDATE jobs SET status='done', updated_at=now(), last_error=NULL "
            "WHERE id=:id"
        ),
        {"id": job_id},
    )


async def mark_retry(
    session: AsyncSession,
    job_id: int,
    next_attempt_at: datetime,
    last_error: str,
) -> None:
    await session.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(status="pending", next_attempt_at=next_attempt_at, last_error=last_error[:2000])
    )


async def mark_failed_permanent(
    session: AsyncSession, job_id: int, last_error: str
) -> None:
    await session.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(status="failed_permanent", last_error=last_error[:2000])
    )


async def prune_done(session: AsyncSession, cutoff: datetime) -> int:
    result = await session.execute(
        text(
            "DELETE FROM jobs WHERE status='done' AND updated_at < :cutoff"
        ),
        {"cutoff": cutoff},
    )
    return result.rowcount or 0


def backoff_seconds(attempts: int) -> int:
    return min(60 * (2**attempts), 3600)


def next_run_after_failure(attempts: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds(attempts))
