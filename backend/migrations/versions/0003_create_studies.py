"""create studies and upload_sessions tables

Revision ID: 0003_studies
Revises: 0002_patients_encounters
Create Date: 2026-11-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003_studies"
down_revision: Union[str, None] = "0002_patients_encounters"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_STUDY_STATUS = sa.Enum(
    "Uploading", "Processing", "Pending", "InReview", "Reported", "Failed",
    name="studystatus", native_enum=False, length=16,
)


def upgrade() -> None:
    op.create_table(
        "upload_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("filename", sa.String(length=300), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=True),
        sa.Column("total_size", sa.BigInteger(), nullable=False),
        sa.Column("received_bytes", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("temp_key", sa.String(length=400), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["encounter_id"], ["encounters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "studies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("status", _STUDY_STATUS, nullable=False),
        sa.Column("storage_key", sa.String(length=400), nullable=False),
        sa.Column("preview_key", sa.String(length=400), nullable=True),
        sa.Column("original_filename", sa.String(length=300), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("is_dicom", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("modality", sa.String(length=16), nullable=True),
        sa.Column("study_date", sa.String(length=16), nullable=True),
        sa.Column("body_part", sa.String(length=64), nullable=True),
        sa.Column("accession_number", sa.String(length=64), nullable=True),
        sa.Column("study_instance_uid", sa.String(length=128), nullable=True),
        sa.Column("series_instance_uid", sa.String(length=128), nullable=True),
        sa.Column("sop_instance_uid", sa.String(length=128), nullable=True),
        sa.Column("processing_error", sa.String(length=500), nullable=True),
        sa.Column("extra", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["encounter_id"], ["encounters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_studies_encounter_id"), "studies", ["encounter_id"])
    op.create_index(op.f("ix_studies_patient_id"), "studies", ["patient_id"])
    op.create_index(op.f("ix_studies_status"), "studies", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_studies_status"), table_name="studies")
    op.drop_index(op.f("ix_studies_patient_id"), table_name="studies")
    op.drop_index(op.f("ix_studies_encounter_id"), table_name="studies")
    op.drop_table("studies")
    op.drop_table("upload_sessions")
