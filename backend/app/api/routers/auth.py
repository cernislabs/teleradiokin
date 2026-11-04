"""Authentication endpoints: login, token refresh, current user."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.domain.auth import LoginRequest, Token, UserRead
from app.infrastructure.database import get_session
from app.infrastructure.models.user import User
from app.services.auth import authenticate, issue_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=Token)
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> Token:
    user = await authenticate(session, payload.email, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    return Token(access_token=issue_token(user))


@router.post("/refresh", response_model=Token)
async def refresh(current_user: User = Depends(get_current_user)) -> Token:
    """Exchange a valid token for a fresh one (sliding session)."""
    return Token(access_token=issue_token(current_user))


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
