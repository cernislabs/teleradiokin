"""Reusable FastAPI dependencies for authentication and authorization."""
import uuid
from collections.abc import Awaitable, Callable
from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import JWTError, decode_token
from app.domain.enums import UserRole
from app.infrastructure.database import get_session
from app.infrastructure.models.user import User
from app.infrastructure.storage import LocalFilesystemStorage, StudyStorage
from app.services.auth import get_user_by_id


@lru_cache
def _storage_for(root: str) -> LocalFilesystemStorage:
    return LocalFilesystemStorage(root)


def get_storage() -> StudyStorage:
    """Provide the configured study storage backend (filesystem for the MVP)."""
    return _storage_for(get_settings().storage_root_path)

_bearer = HTTPBearer(auto_error=True, description="JWT access token")

_credentials_error = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    try:
        payload = decode_token(credentials.credentials)
        subject = payload.get("sub")
        if subject is None:
            raise _credentials_error
        user_id = uuid.UUID(subject)
    except (JWTError, ValueError, TypeError):
        raise _credentials_error

    user = await get_user_by_id(session, user_id)
    if user is None or not user.is_active:
        raise _credentials_error
    return user


def require_roles(*roles: UserRole) -> Callable[..., Awaitable[User]]:
    """Dependency factory enforcing that the current user has one of `roles`."""
    allowed = set(roles)

    async def _checker(user: User = Depends(get_current_user)) -> User:
        if UserRole(user.role) not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role for this operation",
            )
        return user

    return _checker
