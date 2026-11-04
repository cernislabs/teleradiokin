"""Auth-related request/response schemas (Pydantic v2)."""
import uuid

from pydantic import EmailStr, Field

from app.domain.enums import UserRole
from app.domain.schemas import AppModel


class LoginRequest(AppModel):
    email: EmailStr
    password: str = Field(min_length=1)


class Token(AppModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(AppModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    organization_id: uuid.UUID | None = None


class UserCreate(AppModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole
    organization_id: uuid.UUID | None = None
