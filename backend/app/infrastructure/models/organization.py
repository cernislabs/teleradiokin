"""Organization (referring site) model.

A referring site/clinic. ReferringClinicians belong to one organization and only
see that organization's patients and studies; radiologists and admins read across
all organizations (the teleradiology model: remote readers serve every site).
"""
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.models.base import TimestampedBase


class Organization(TimestampedBase):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
