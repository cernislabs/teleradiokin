"""create audit_events table

Revision ID: 0005_audit
Revises: 0004_reports
Create Date: 2026-11-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005_audit"
down_revision: Union[str, None] = "0004_reports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("actor_email", sa.String(length=320), nullable=False),
        sa.Column(
            "actor_role",
            sa.Enum("Admin", "ReferringClinician", "Radiologist", name="userrole", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column(
            "action",
            sa.Enum("login", "view", "create", "update", "finalize", "download", name="auditaction", native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column(
            "entity_type",
            sa.Enum("session", "patient", "study", "report", name="auditentity", native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_events_actor_id"), "audit_events", ["actor_id"])
    op.create_index(op.f("ix_audit_events_entity_type"), "audit_events", ["entity_type"])
    op.create_index(op.f("ix_audit_events_entity_id"), "audit_events", ["entity_id"])
    op.create_index(op.f("ix_audit_events_created_at"), "audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_events_created_at"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_entity_id"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_entity_type"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_actor_id"), table_name="audit_events")
    op.drop_table("audit_events")
