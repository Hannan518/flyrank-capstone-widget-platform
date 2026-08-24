import logging

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.deps import SessionDep
from app.api.public.deps import ClientIpDep, GeoChainDep
from app.core.config import get_settings
from app.repositories import widget_repo
from app.schemas.submission import SubmissionRequest
from app.services import submission_service
from app.services.submission_service import SubmitOutcome

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/public", tags=["public"])


def _normalize_origin(origin: str | None) -> str | None:
    if not origin:
        return None
    return origin.strip().rstrip("/").lower()


@router.options("/submissions")
async def submissions_preflight(request: Request) -> Response:
    origin = request.headers.get("origin")
    request_method = request.headers.get("access-control-request-method", "")
    if _normalize_origin(origin) and request_method.upper() == "POST":
        return Response(
            status_code=204,
            headers={
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Methods": "POST",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Max-Age": "600",
                "Vary": "Origin",
            },
        )
    return Response(status_code=403)


@router.post("/submissions", status_code=status.HTTP_201_CREATED)
async def create_submission(
    request: Request,
    data: SubmissionRequest,
    session: SessionDep,
    ip: ClientIpDep,
    geo_chain: GeoChainDep,
) -> Response:
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit():
        if int(content_length) > get_settings().submission_max_body_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="payload too large",
            )

    widget = await widget_repo.get_by_id(session, str(data.widget_id))
    if widget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="widget not found"
        )

    origin = _normalize_origin(request.headers.get("origin"))
    allowed = {o.rstrip("/").lower() for o in widget.allowed_origins}
    if origin is None or origin not in allowed:
        raise submission_service.OriginNotAllowedError()

    outcome: SubmitOutcome = await submission_service.submit(
        session,
        widget=widget,
        fields=data.fields,
        honeypot=data.website,
        idempotency_key=data.idempotency_key,
        ip=ip,
        user_agent=request.headers.get("user-agent"),
        origin=origin,
        geo_chain=geo_chain,
    )

    if outcome.outcome == "honeypot":
        return Response(
            status_code=status.HTTP_202_ACCEPTED,
            content='{"message":"received"}',
            media_type="application/json",
        )
    if outcome.outcome == "replayed":
        return Response(
            status_code=status.HTTP_200_OK,
            content=f'{{"id":"{outcome.submission.id}"}}',
            media_type="application/json",
            headers={
                "Access-Control-Allow-Origin": request.headers.get("origin", ""),
                "X-Idempotent-Replay": "true",
                "Vary": "Origin",
            },
        )
    return Response(
        status_code=status.HTTP_201_CREATED,
        content=f'{{"id":"{outcome.submission.id}"}}',
        media_type="application/json",
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin", ""),
            "Vary": "Origin",
        },
    )
