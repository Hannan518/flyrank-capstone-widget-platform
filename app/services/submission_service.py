import hashlib
import logging
import re
import uuid as uuid_lib
import ipaddress
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError, FieldErrorsError
from app.models.submission import Submission
from app.repositories import job_repo, submission_repo
from app.services.geo.chain import GeoEnrichmentChain
from app.services.rate_limiter import RateVerdict, enforce_submission_limits

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

OutcomeType = Literal["created", "replayed", "honeypot"]


@dataclass(frozen=True)
class SubmitOutcome:
    outcome: OutcomeType
    submission: Submission | None = None


class OriginNotAllowedError(AppError):
    status_code = 403
    detail = "disallowed origin"


class RateLimitedError(AppError):
    status_code = 429
    detail = "rate limit exceeded"

    def __init__(self, retry_after_seconds: int):
        super().__init__()
        self.headers = {"Retry-After": str(retry_after_seconds)}


def resolve_lookup_ip(ip: str) -> str:
    settings = get_settings()
    if settings.app_env != "dev":
        return ip
    try:
        parsed = ipaddress.ip_address(ip)
    except ValueError:
        return ip
    if parsed.is_private or parsed.is_loopback or parsed.is_reserved:
        return settings.dev_public_ip
    return ip


async def submit(
    session: AsyncSession,
    *,
    widget,
    fields: dict[str, str],
    honeypot: str,
    idempotency_key: str | None,
    ip: str,
    user_agent: str | None,
    origin: str,
    geo_chain: GeoEnrichmentChain,
) -> SubmitOutcome:
    _validate_fields(widget.fields, fields)

    if honeypot.strip():
        logger.info(
            "spam_honeypot widget=%s ip_hash=%s",
            widget.id,
            hashlib.sha256(ip.encode()).hexdigest()[:12],
        )
        return SubmitOutcome(outcome="honeypot")

    verdict: RateVerdict = await enforce_submission_limits(session, ip, widget.id)
    if not verdict.allowed:
        raise RateLimitedError(verdict.retry_after_seconds)
    await session.commit()

    if idempotency_key is not None:
        replayed = await submission_repo.get_by_widget_and_key(
            session, widget.id, idempotency_key
        )
        if replayed is not None:
            logger.info("idempotent replay widget=%s", widget.id)
            return SubmitOutcome(outcome="replayed", submission=replayed)

    lookup_ip = resolve_lookup_ip(ip)
    geo = await geo_chain.enrich(lookup_ip)

    submission_id = str(uuid_lib.uuid4())
    inserted_id = await submission_repo.insert_idempotent(
        session,
        submission_id=submission_id,
        widget_id=widget.id,
        tenant_id=widget.owner_id,
        payload=fields,
        idempotency_key=idempotency_key,
        ip_address=ip,
        user_agent=user_agent,
        country=geo.country_code if geo else None,
        city=geo.city if geo else None,
        region=geo.region if geo else None,
        latitude=geo.latitude if geo else None,
        longitude=geo.longitude if geo else None,
    )

    if inserted_id is None:
        existing = await submission_repo.get_by_widget_and_key(
            session, widget.id, idempotency_key or ""
        )
        logger.info("idempotent race resolved; returning winner")
        await session.commit()
        return SubmitOutcome(outcome="replayed", submission=existing)

    recipient = _first_email(fields, widget.fields)
    if recipient:
        await job_repo.enqueue(
            session,
            job_type="confirmation_email",
            payload={
                "to": recipient,
                "widget_title": widget.title,
                "submitted_at": datetime.now(timezone.utc).isoformat(),
            },
            submission_id=submission_id,
        )
    else:
        logger.debug("no email field on widget %s; skipping confirmation", widget.id)

    await session.commit()
    stored = await submission_repo.get_by_id(session, inserted_id)
    return SubmitOutcome(outcome="created", submission=stored)


def _validate_fields(field_defs: list[dict], provided: dict[str, str]) -> None:
    errors: list[dict[str, str]] = []
    allowed_names = {d["name"] for d in field_defs}
    for name in sorted(set(provided) - allowed_names):
        errors.append({"field": name, "message": "unknown field"})
    for d in field_defs:
        value = (provided.get(d["name"]) or "").strip()
        if d.get("required") and not value:
            errors.append({"field": d["name"], "message": "required field missing"})
            continue
        if value and d["type"] == "email" and not _EMAIL_RE.match(value):
            errors.append({"field": d["name"], "message": "invalid email address"})
    if errors:
        raise FieldErrorsError(errors)


def _first_email(values: dict[str, str], field_defs: list[dict]) -> str | None:
    for d in field_defs:
        if d["type"] == "email":
            candidate = (values.get(d["name"]) or "").strip()
            if candidate:
                return candidate
    return None
