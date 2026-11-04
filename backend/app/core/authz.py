"""Object-level access policy (who may see which records).

Teleradiology model: a ``ReferringClinician`` is scoped to their own
organization (referring site) and may only see that site's patients, studies,
and reports. ``Radiologist`` and ``Admin`` are cross-site — the remote readers
serve every site — so they see everything.

Routers derive an :class:`AccessScope` from the current user and pass it to the
service layer, which uses it to filter list queries and to authorize single-record
reads. A denied single-record read is reported as 404 (not 403) so IDs cannot be
probed for existence across sites.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.domain.enums import UserRole

_CROSS_SITE_ROLES = {UserRole.RADIOLOGIST, UserRole.ADMIN}


@dataclass(frozen=True, slots=True)
class AccessScope:
    """The set of records a request is allowed to touch."""

    cross_site: bool
    organization_id: uuid.UUID | None

    @classmethod
    def for_user(cls, user) -> "AccessScope":
        if UserRole(user.role) in _CROSS_SITE_ROLES:
            return cls(cross_site=True, organization_id=None)
        return cls(cross_site=False, organization_id=user.organization_id)

    def allows_org(self, organization_id: uuid.UUID | None) -> bool:
        """True if a record owned by ``organization_id`` is visible to this scope."""
        return self.cross_site or self.organization_id == organization_id
