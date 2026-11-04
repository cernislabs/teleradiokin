"""create patients and encounters tables

Revision ID: 0002_patients_encounters
Revises: 0001_create_users
Create Date: 2026-11-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_patients_encounters"
down_revision: Union[str, None] = "0001_create_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "patients",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mrn", sa.String(length=64), nullable=False),
        sa.Column("family_name", sa.String(length=120), nullable=False),
        sa.Column("given_name", sa.String(length=120), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column(
            "sex",
            sa.Enum("male", "female", "other", "unknown",
                    name="administrativegender", native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("consent_acknowledged", sa.Boolean(), nullable=False),
        sa.Column("consent_acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extra", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_patients_mrn"), "patients", ["mrn"], unique=True)

    op.create_table(
        "encounters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("referring_clinician_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("planned", "in-progress", "finished", "cancelled",
                    name="encounterstatus", native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.Column("extra", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["referring_clinician_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_encounters_patient_id"), "encounters", ["patient_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_encounters_patient_id"), table_name="encounters")
    op.drop_table("encounters")
    op.drop_index(op.f("ix_patients_mrn"), table_name="patients")
    op.drop_table("patients")
