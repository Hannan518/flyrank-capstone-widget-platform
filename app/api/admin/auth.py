from fastapi import APIRouter, status

from app.api.deps import SessionDep
from app.schemas.auth import RegisterRequest, TokenResponse, UserOut
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register", response_model=UserOut, status_code=status.HTTP_201_CREATED
)
async def register(data: RegisterRequest, session: SessionDep) -> UserOut:
    user = await auth_service.register(session, data.email, data.password)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(data: RegisterRequest, session: SessionDep) -> TokenResponse:
    token = await auth_service.login(session, data.email, data.password)
    return TokenResponse(access_token=token)
