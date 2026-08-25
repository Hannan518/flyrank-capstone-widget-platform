from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.submission import Submission
from app.models.widget import Widget


async def page_for_tenant(
    session: AsyncSession,
    tenant_id: str,
    *,
    widget_id: str | None = None,
    before_created_at: datetime | None = None,
    before_id: str | None = None,
    limit: int,
) -> list[Submission]:
    conditions = [Submission.tenant_id == tenant_id]
    if widget_id is not None:
        conditions.append(Submission.widget_id == widget_id)
    if before_created_at is not None:
        conditions.append(
            tuple_(Submission.created_at, Submission.id)
            < (before_created_at, before_id)
        )
    stmt = (
        select(Submission)
        .where(and_(*conditions))
        .order_by(Submission.created_at.desc(), Submission.id.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def stats_for_tenant(
    session: AsyncSession, tenant_id: str, days: int
) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    scope = and_(Submission.tenant_id == tenant_id, Submission.created_at >= since)

    total = (
        await session.execute(select(func.count()).select_from(Submission).where(scope))
    ).scalar_one()

    per_widget_rows = (
        await session.execute(
            select(
                Submission.widget_id,
                Widget.title,
                func.count().label("count"),
            )
            .join(Widget, Widget.id == Submission.widget_id)
            .where(scope)
            .group_by(Submission.widget_id, Widget.title)
            .order_by(func.count().desc())
        )
    ).all()

    day_bucket = func.date_trunc("day", Submission.created_at)
    timeseries_rows = (
        await session.execute(
            select(day_bucket.label("day"), func.count().label("count"))
            .where(scope)
            .group_by(day_bucket)
            .order_by(day_bucket)
        )
    ).all()

    geo_rows = (
        await session.execute(
            select(Submission.country, func.count().label("count"))
            .where(and_(scope, Submission.country.is_not(None)))
            .group_by(Submission.country)
            .order_by(func.count().desc())
            .limit(10)
        )
    ).all()

    return {
        "total": total,
        "per_widget": [
            {"widget_id": r.widget_id, "title": r.title, "count": r.count}
            for r in per_widget_rows
        ],
        "timeseries": [
            {"day": r.day.date() if hasattr(r.day, "date") else r.day, "count": r.count}
            for r in timeseries_rows
        ],
        "geo": [{"country": r.country, "count": r.count} for r in geo_rows],
    }
