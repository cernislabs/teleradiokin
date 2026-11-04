"""create reports table

Revision ID: 0004_reports
Revises: 0003_studies
Create Date: 2026-11-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_reports"
down_revision: Union[str, None] = "0003_studies"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("study_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("Draft", "Final", name="reportstatus", native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("findings", sa.Text(), nullable=False),
        sa.Column("impression", sa.Text(), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["study_id"], ["studies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reports_study_id"), "reports", ["study_id"], unique=True)
    op.create_index(op.f("ix_reports_patient_id"), "reports", ["patient_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_reports_patient_id"), table_name="reports")
    op.drop_index(op.f("ix_reports_study_id"), table_name="reports")
    op.drop_table("reports")
