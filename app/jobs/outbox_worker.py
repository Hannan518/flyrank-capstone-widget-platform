import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories import job_repo, rate_limit_repo
from app.services.mailers import Mailer

logger = logging.getLogger(__name__)


class OutboxWorker:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        mailer: Mailer,
        poll_interval_seconds: float = 2.0,
        batch_size: int = 10,
    ):
        self._session_factory = session_factory
        self._mailer = mailer
        self._poll_interval = poll_interval_seconds
        self._batch_size = batch_size
        self._running = False

    async def run_forever(self) -> None:
        self._running = True
        logger.info(
            "outbox worker started (mailer=%s, poll=%.1fs)",
            self._mailer.name,
            self._poll_interval,
        )
        try:
            while self._running:
                processed = await self.poll_once()
                if processed == 0:
                    await asyncio.sleep(self._poll_interval)
        except asyncio.CancelledError:
            logger.info("outbox worker cancelled")
            raise
        finally:
            self._running = False

    def stop(self) -> None:
        self._running = False

    async def poll_once(self) -> int:
        processed = 0
        for _ in range(self._batch_size):
            handled = await self._claim_and_process_one()
            if not handled:
                break
            processed += 1
        return processed

    async def _claim_and_process_one(self) -> bool:
        async with self._session_factory() as session:
            job = await job_repo.claim_next(session)
            if job is None:
                return False
            try:
                await self._dispatch(session, job)
            except Exception as exc:
                await self._handle_failure(session, job, exc)
            else:
                await job_repo.mark_done(session, job.id)
                logger.info("job %s (%s) done", job.id, job.type)
            await session.commit()
        return True

    async def _dispatch(
        self, session: AsyncSession, job: job_repo.ClaimedJob
    ) -> None:
        if job.type == "confirmation_email":
            await self._mailer.send_confirmation(
                str(job.payload["to"]), str(job.payload["widget_title"])
            )
        else:
            raise ValueError(f"no handler for job type {job.type!r}")

    async def _handle_failure(
        self,
        session: AsyncSession,
        job: job_repo.ClaimedJob,
        exc: Exception,
    ) -> None:
        error_text = f"{type(exc).__name__}: {exc}"
        if job.attempts >= job.max_attempts:
            await job_repo.mark_failed_permanent(session, job.id, error_text)
            logger.critical(
                "JOB ALERT: job %s (%s) failed permanently after %d attempts: %s",
                job.id,
                job.type,
                job.attempts,
                error_text,
            )
        else:
            next_at = job_repo.next_run_after_failure(job.attempts)
            await job_repo.mark_retry(session, job.id, next_at, error_text)
            logger.warning(
                "job %s (%s) failed (%d/%d), retrying at %s: %s",
                job.id,
                job.type,
                job.attempts,
                job.max_attempts,
                next_at.isoformat(),
                error_text,
            )


class Pruner:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        interval_seconds: float,
        rate_limit_retention_seconds: int,
        job_retention_days: int,
    ):
        self._session_factory = session_factory
        self._interval = interval_seconds
        self._rate_retention = rate_limit_retention_seconds
        self._job_retention_days = job_retention_days

    async def run_forever(self) -> None:
        logger.info("pruner started (interval=%.0fs)", self._interval)
        while True:
            try:
                await self.sweep_once()
            except asyncio.CancelledError:
                logger.info("pruner cancelled")
                raise
            except Exception:
                logger.exception("JOB ALERT: pruner sweep failed; will retry next tick")
            await asyncio.sleep(self._interval)

    async def sweep_once(self) -> dict[str, int]:
        now = datetime.now(timezone.utc)
        async with self._session_factory() as session:
            rate_rows = await rate_limit_repo.prune_expired(
                session, now - timedelta(seconds=self._rate_retention)
            )
            done_jobs = await job_repo.prune_done(
                session, now - timedelta(days=self._job_retention_days)
            )
            await session.commit()
        logger.info(
            "pruned %d expired rate-limit rows and %d completed jobs",
            rate_rows,
            done_jobs,
        )
        return {"rate_limits": rate_rows, "jobs": done_jobs}
