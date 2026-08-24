from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def increment(
    session: AsyncSession, scope_key: str, window_start: datetime
) -> int:
    result = await session.execute(
        text(
            """
            INSERT INTO rate_limits (scope_key, window_start, count)
            VALUES (:scope_key, :window_start, 1)
            ON CONFLICT (scope_key, window_start)
            DO UPDATE SET count = rate_limits.count + 1
            RETURNING count
            """
        ),
        {"scope_key": scope_key, "window_start": window_start},
    )
    return int(result.scalar_one())


async def prune_expired(session: AsyncSession, cutoff: datetime) -> int:
    result = await session.execute(
        text("DELETE FROM rate_limits WHERE window_start < :cutoff"),
        {"cutoff": cutoff},
    )
    return result.rowcount or 0


async def count_rows(session: AsyncSession) -> int:
    result = await session.execute(text("SELECT COUNT(*) FROM rate_limits"))
    return int(result.scalar_one())
