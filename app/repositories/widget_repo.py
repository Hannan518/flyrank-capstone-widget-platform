from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.widget import Widget


async def create(session: AsyncSession, widget: Widget) -> Widget:
    session.add(widget)
    await session.flush()
    return widget


async def get_for_owner(
    session: AsyncSession, widget_id: str, owner_id: str
) -> Widget | None:
    result = await session.execute(
        select(Widget).where(Widget.id == widget_id, Widget.owner_id == owner_id)
    )
    return result.scalar_one_or_none()


async def list_for_owner(session: AsyncSession, owner_id: str) -> list[Widget]:
    result = await session.execute(
        select(Widget)
        .where(Widget.owner_id == owner_id)
        .order_by(Widget.created_at.desc())
    )
    return list(result.scalars().all())


async def delete(session: AsyncSession, widget: Widget) -> None:
    await session.delete(widget)
    await session.flush()
