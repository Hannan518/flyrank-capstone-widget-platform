from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories import user_repo


class EmailTakenError(AppError):
    status_code = 409
    detail = "email already registered"


class InvalidCredentialsError(AppError):
    status_code = 401
    detail = "invalid email or password"


async def register(
    session: AsyncSession, email: str, password: str
) -> User:
    normalized = email.strip().lower()
    if await user_repo.get_by_email(session, normalized) is not None:
        raise EmailTakenError()
    user = User(id=str(uuid4()), email=normalized, password_hash=hash_password(password))
    created = await user_repo.create(session, user)
    await session.commit()
    await session.refresh(created)
    return created


async def login(session: AsyncSession, email: str, password: str) -> str:
    normalized = email.strip().lower()
    user = await user_repo.get_by_email(session, normalized)
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError()
    return create_access_token(user.id)
