from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import SessionDep
from app.repositories import widget_repo
from app.schemas.widget import WIDGET_BUNDLE_VERSION

_STATIC_DIR = Path(__file__).resolve().parents[2] / "static"
_BUNDLE_PATH = _STATIC_DIR / f"widget.v{WIDGET_BUNDLE_VERSION}.js"
_JS_BYTES = _BUNDLE_PATH.read_bytes()

_IMMUTABLE = "public, max-age=31536000, immutable"
_LATEST = "public, max-age=60"

router = APIRouter(tags=["bundle"])


@router.get(f"/widget.v{WIDGET_BUNDLE_VERSION}.js", include_in_schema=False)
async def bundle_versioned(id: str, session: SessionDep) -> Response:
    await _require_widget(session, id)
    return _serve(_IMMUTABLE)


@router.get("/widget.js", include_in_schema=False)
async def bundle_latest(id: str, session: SessionDep) -> Response:
    await _require_widget(session, id)
    return _serve(_LATEST)


def _serve(cache_control: str) -> Response:
    return Response(
        content=_JS_BYTES,
        media_type="application/javascript; charset=utf-8",
        headers={"Cache-Control": cache_control},
    )


async def _require_widget(session, widget_id: str) -> None:
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
