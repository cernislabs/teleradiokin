"""add organizations and organization scoping

Revision ID: 0006_orgs
Revises: 0005_audit
Create Date: 2026-11-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_orgs"
down_revision: Union[str, None] = "0005_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.add_column("users", sa.Column("organization_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_users_organization_id"), "users", ["organization_id"])
    op.create_foreign_key(
        "fk_users_organization_id", "users", "organizations",
        ["organization_id"], ["id"], ondelete="SET NULL",
    )

    op.add_column("patients", sa.Column("organization_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_patients_organization_id"), "patients", ["organization_id"])
    op.create_foreign_key(
        "fk_patients_organization_id", "patients", "organizations",
        ["organization_id"], ["id"], ondelete="SET NULL",
    )

    op.create_index(
        "ix_audit_entity_history", "audit_events",
        ["entity_type", "entity_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_entity_history", table_name="audit_events")

    op.drop_constraint("fk_patients_organization_id", "patients", type_="foreignkey")
    op.drop_index(op.f("ix_patients_organization_id"), table_name="patients")
    op.drop_column("patients", "organization_id")

    op.drop_constraint("fk_users_organization_id", "users", type_="foreignkey")
    op.drop_index(op.f("ix_users_organization_id"), table_name="users")
    op.drop_column("users", "organization_id")

    op.drop_table("organizations")
