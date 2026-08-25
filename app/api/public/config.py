from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.deps import SessionDep
from app.repositories import widget_repo
from app.schemas.dashboard import WidgetConfig

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/widgets/{widget_id}/config")
async def get_widget_config(
    widget_id: str, request: Request, session: SessionDep
) -> Response:
    from uuid import UUID

    try:
        UUID(widget_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="widget not found"
        )

    widget = await widget_repo.get_by_id(session, widget_id)
    if widget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="widget not found"
        )

    body = WidgetConfig(
        type=widget.type,
        title=widget.title,
        description=widget.description,
        fields=list(widget.fields),
        button_text=widget.button_text,
        display_options=dict(widget.display_options),
    )

    headers = {
        "Cache-Control": "public, max-age=30",
        "Vary": "Origin",
    }
    origin = _normalize_origin(request.headers.get("origin"))
    if origin:
        allowed = {o.rstrip("/").lower() for o in widget.allowed_origins}
        if origin in allowed:
            headers["Access-Control-Allow-Origin"] = origin
    content = body.model_dump_json()
    return Response(
        content=content,
        media_type="application/json",
        headers=headers,
    )


def _normalize_origin(origin: str | None) -> str | None:
    if not origin:
        return None
    return origin.strip().rstrip("/").lower()
