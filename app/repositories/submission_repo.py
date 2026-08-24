from datetime import datetime

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.submission import Submission


async def get_by_id(session: AsyncSession, submission_id: str) -> Submission | None:
    result = await session.execute(
        select(Submission).where(Submission.id == submission_id)
    )
    return result.scalar_one_or_none()


async def get_by_widget_and_key(
    session: AsyncSession, widget_id: str, idempotency_key: str
) -> Submission | None:
    result = await session.execute(
        select(Submission).where(
            Submission.widget_id == widget_id,
            Submission.idempotency_key == idempotency_key,
        )
    )
    return result.scalar_one_or_none()


async def insert_idempotent(
    session: AsyncSession,
    *,
    submission_id: str,
    widget_id: str,
    tenant_id: str,
    payload: dict,
    idempotency_key: str | None,
    ip_address: str,
    user_agent: str | None,
    country: str | None,
    city: str | None,
    region: str | None,
    latitude: float | None,
    longitude: float | None,
) -> str | None:
    values = dict(
        id=submission_id,
        widget_id=widget_id,
        tenant_id=tenant_id,
        payload=payload,
        ip_address=ip_address,
        user_agent=user_agent,
        country=country,
        city=city,
        region=region,
        latitude=latitude,
        longitude=longitude,
        idempotency_key=idempotency_key,
    )
    if idempotency_key is None:
        session.add(Submission(**values))
        await session.flush()
        return submission_id

    stmt = (
        pg_insert(Submission)
        .values(**values)
        .on_conflict_do_nothing(
            index_elements=["widget_id", "idempotency_key"],
            index_where=text("idempotency_key IS NOT NULL"),
        )
        .returning(Submission.id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
