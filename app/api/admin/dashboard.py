from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import SessionDep, UserIdDep
from app.repositories import dashboard_repo
from app.schemas.dashboard import (
    StatsOut,
    SubmissionOut,
    SubmissionsPage,
)
from app.services import widget_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/submissions", response_model=SubmissionsPage)
async def list_submissions(
    session: SessionDep,
    owner_id: UserIdDep,
    widget_id: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> SubmissionsPage:
    if widget_id is not None:
        _require_uuid(widget_id)
        owned = await widget_service.get_widget(session, widget_id, owner_id)
        if owned is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="widget not found"
            )

    before_created_at, before_id = _decode_cursor(cursor)

    rows = await dashboard_repo.page_for_tenant(
        session,
        str(owner_id),
        widget_id=widget_id,
        before_created_at=before_created_at,
        before_id=before_id,
        limit=limit + 1,
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = _encode_cursor(rows[-1]) if has_more and rows else None
    return SubmissionsPage(
        items=[SubmissionOut.from_row(r) for r in rows],
        next_cursor=next_cursor,
    )


@router.get("/stats", response_model=StatsOut)
async def get_stats(
    session: SessionDep,
    owner_id: UserIdDep,
    days: int = Query(default=30, ge=1, le=90),
) -> StatsOut:
    data = await dashboard_repo.stats_for_tenant(session, str(owner_id), days)
    return StatsOut(**data)


def _require_uuid(value: str) -> None:
    from uuid import UUID

    try:
        UUID(value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="widget not found"
        )


def _encode_cursor(row) -> str:
    token = f"{row.created_at.isoformat()}|{row.id}"
    return urlsafe_b64encode(token.encode()).decode()


def _decode_cursor(cursor: str | None) -> tuple[datetime | None, str | None]:
    if cursor is None:
        return None, None
    try:
        raw = urlsafe_b64decode(cursor.encode()).decode()
        created_raw, row_id = raw.rsplit("|", 1)
        return datetime.fromisoformat(created_raw), row_id
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="bad cursor"
        )
