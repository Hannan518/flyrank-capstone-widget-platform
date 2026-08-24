from fastapi import APIRouter, HTTPException, status

from app.api.deps import SessionDep, UserIdDep
from app.schemas.widget import WidgetCreate, WidgetOut, WidgetUpdate
from app.services import widget_service

router = APIRouter(prefix="/widgets", tags=["widgets"])


@router.post("", response_model=WidgetOut, status_code=status.HTTP_201_CREATED)
async def create_widget(
    data: WidgetCreate, session: SessionDep, owner_id: UserIdDep
) -> WidgetOut:
    widget = await widget_service.create_widget(session, owner_id, data)
    return WidgetOut.from_widget(widget)


@router.get("", response_model=list[WidgetOut])
async def list_widgets(session: SessionDep, owner_id: UserIdDep) -> list[WidgetOut]:
    widgets = await widget_service.list_widgets(session, owner_id)
    return [WidgetOut.from_widget(w) for w in widgets]


@router.get("/{widget_id}", response_model=WidgetOut)
async def get_widget(
    widget_id: str, session: SessionDep, owner_id: UserIdDep
) -> WidgetOut:
    widget = await _require_widget(session, widget_id, owner_id)
    return WidgetOut.from_widget(widget)


@router.patch("/{widget_id}", response_model=WidgetOut)
async def update_widget(
    widget_id: str,
    data: WidgetUpdate,
    session: SessionDep,
    owner_id: UserIdDep,
) -> WidgetOut:
    widget = await _require_widget(session, widget_id, owner_id)
    updated = await widget_service.update_widget(session, widget, data)
    return WidgetOut.from_widget(updated)


@router.delete("/{widget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_widget(
    widget_id: str, session: SessionDep, owner_id: UserIdDep
) -> None:
    widget = await _require_widget(session, widget_id, owner_id)
    await widget_service.delete_widget(session, widget)


async def _require_widget(session, widget_id: str, owner_id: str):
    from uuid import UUID

    try:
        UUID(widget_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="widget not found")
    widget = await widget_service.get_widget(session, widget_id, owner_id)
    if widget is None:
        raise HTTPException(status_code=404, detail="widget not found")
    return widget
