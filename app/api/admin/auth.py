from fastapi import APIRouter, status

from app.api.deps import ClientIpDep, SessionDep
from app.schemas.auth import RegisterRequest, TokenResponse, UserOut
from app.services import auth_service, rate_limiter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register", response_model=UserOut, status_code=status.HTTP_201_CREATED
)
async def register(
    data: RegisterRequest, session: SessionDep, ip: ClientIpDep
) -> UserOut:
    verdict = await rate_limiter.enforce_auth_limits(session, ip)
    if not verdict.allowed:
        raise rate_limiter.RateLimitedError(verdict.retry_after_seconds)
    await session.commit()
    user = await auth_service.register(session, data.email, data.password)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    data: RegisterRequest, session: SessionDep, ip: ClientIpDep
) -> TokenResponse:
    verdict = await rate_limiter.enforce_auth_limits(session, ip)
    if not verdict.allowed:
        raise rate_limiter.RateLimitedError(verdict.retry_after_seconds)
    await session.commit()
    token = await auth_service.login(session, data.email, data.password)
    return TokenResponse(access_token=token)
