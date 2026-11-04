"""Authentication and user-management business logic."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.domain.auth import UserCreate
from app.domain.enums import UserRole
from app.infrastructure.models.user import User


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id) -> User | None:
    return await session.get(User, user_id)


async def authenticate(session: AsyncSession, email: str, password: str) -> User | None:
    """Return the user if credentials are valid and the account is active."""
    user = await get_user_by_email(session, email)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def create_user(session: AsyncSession, data: UserCreate) -> User:
    user = User(
        email=data.email.lower(),
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        role=data.role,
        is_active=True,
        organization_id=data.organization_id,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def issue_token(user: User) -> str:
    """Create a signed access token for an authenticated user."""
    roles: list[str] = [UserRole(user.role).value]
    return create_access_token(subject=str(user.id), roles=roles)
