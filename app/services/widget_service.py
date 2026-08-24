from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.widget import Widget
from app.repositories import widget_repo
from app.schemas.widget import WidgetCreate, WidgetUpdate


async def create_widget(
    session: AsyncSession, owner_id: str, data: WidgetCreate
) -> Widget:
    widget = Widget(id=str(uuid4()), owner_id=owner_id, **data.model_dump())
    created = await widget_repo.create(session, widget)
    await session.commit()
    await session.refresh(created)
    return created


async def get_widget(session: AsyncSession, widget_id: str, owner_id: str) -> Widget | None:
    return await widget_repo.get_for_owner(session, widget_id, owner_id)


async def list_widgets(session: AsyncSession, owner_id: str) -> list[Widget]:
    return await widget_repo.list_for_owner(session, owner_id)


async def update_widget(
    session: AsyncSession, widget: Widget, data: WidgetUpdate
) -> Widget:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(widget, key, value)
    await session.flush()
    await session.commit()
    await session.refresh(widget)
    return widget


async def delete_widget(session: AsyncSession, widget: Widget) -> None:
    await widget_repo.delete(session, widget)
    await session.commit()
