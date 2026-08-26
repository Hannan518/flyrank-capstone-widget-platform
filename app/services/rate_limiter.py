import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.repositories import rate_limit_repo


class RateLimitedError(AppError):
    status_code = 429
    detail = "too many requests"

    def __init__(self, retry_after_seconds: int):
        super().__init__(
            headers={
                "Retry-After": str(retry_after_seconds),
                "Vary": "Origin",
            }
        )
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class RateVerdict:
    allowed: bool
    retry_after_seconds: int = 0


def window_start(now: datetime, window_seconds: int) -> datetime:
    slot = int(now.timestamp()) // window_seconds * window_seconds
    return datetime.fromtimestamp(slot, tz=timezone.utc)


def scope_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def enforce_submission_limits(
    session: AsyncSession, ip: str, widget_id: str
) -> RateVerdict:
    settings = get_settings()
    now = datetime.now(timezone.utc)

    ip_window = window_start(now, settings.rate_limit_ip_window_seconds)
    ip_scope = scope_hash(f"ip|{ip}|{widget_id}")
    ip_count = await rate_limit_repo.increment(session, ip_scope, ip_window)
    if ip_count > settings.rate_limit_ip_max:
        return _blocked(now, ip_window, settings.rate_limit_ip_window_seconds)

    widget_window = window_start(now, settings.rate_limit_widget_window_seconds)
    widget_scope = scope_hash(f"widget|{widget_id}")
    widget_count = await rate_limit_repo.increment(session, widget_scope, widget_window)
    if widget_count > settings.rate_limit_widget_max:
        return _blocked(now, widget_window, settings.rate_limit_widget_window_seconds)

    return RateVerdict(allowed=True)


async def enforce_auth_limits(session: AsyncSession, ip: str) -> RateVerdict:
    """Shared per-IP bucket across register + login (brute-force blunting)."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    window = window_start(now, settings.rate_limit_auth_window_seconds)
    scope = scope_hash(f"auth|{ip}")
    count = await rate_limit_repo.increment(session, scope, window)
    if count > settings.rate_limit_auth_max:
        return _blocked(now, window, settings.rate_limit_auth_window_seconds)
    return RateVerdict(allowed=True)


def _blocked(
    now: datetime, current_window_start: datetime, window_seconds: int
) -> RateVerdict:
    window_end = current_window_start + timedelta(seconds=window_seconds)
    retry_after = max(1, int((window_end - now).total_seconds()))
    return RateVerdict(allowed=False, retry_after_seconds=retry_after)
