"""add edinet downloader tables

Revision ID: 20260326_0003
Revises: 20260322_0002
Create Date: 2026-03-26 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260326_0003"
down_revision = "20260322_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "edinet_list_responses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("doc_id", sa.String(length=32), nullable=False),
        sa.Column("edinet_code", sa.String(length=16), nullable=True),
        sa.Column("form_code", sa.String(length=32), nullable=True),
        sa.Column("doc_type_code", sa.String(length=32), nullable=True),
        sa.Column("filing_type_key", sa.String(length=64), nullable=True),
        sa.Column("response_path", sa.Text(), nullable=False),
        sa.Column("response_sha256", sa.String(length=128), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id", name="pk_edinet_list_responses"),
        sa.UniqueConstraint("doc_id", name="uq_edinet_list_responses_doc_id"),
    )
    op.create_index(
        "ix_edinet_list_responses_target_date",
        "edinet_list_responses",
        ["target_date"],
        unique=False,
    )
    op.create_index(
        "ix_edinet_list_responses_filing_type_key",
        "edinet_list_responses",
        ["filing_type_key"],
        unique=False,
    )

    op.create_table(
        "edinet_fetch_jobs",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("doc_id", sa.String(length=32), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("filing_type_key", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("zip_path", sa.Text(), nullable=True),
        sa.Column("pdf_path", sa.Text(), nullable=True),
        sa.Column("csv_zip_path", sa.Text(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("job_id", name="pk_edinet_fetch_jobs"),
        sa.UniqueConstraint("doc_id", name="uq_edinet_fetch_jobs_doc_id"),
    )
    op.create_index(
        "ix_edinet_fetch_jobs_target_date",
        "edinet_fetch_jobs",
        ["target_date"],
        unique=False,
    )
    op.create_index(
        "ix_edinet_fetch_jobs_status",
        "edinet_fetch_jobs",
        ["status"],
        unique=False,
    )

    op.create_table(
        "filing_type_map",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default=sa.text("'edinet'")),
        sa.Column("filing_type_key", sa.String(length=64), nullable=False),
        sa.Column("form_code", sa.String(length=32), nullable=True),
        sa.Column("doc_type_code", sa.String(length=32), nullable=True),
        sa.Column("filing_type_raw", sa.String(length=128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id", name="pk_filing_type_map"),
        sa.UniqueConstraint(
            "source_type",
            "filing_type_key",
            "form_code",
            "doc_type_code",
            name="uq_ftm_src_ftype_form_doc",
        ),
    )
    op.create_index(
        "ix_filing_type_map_source_type_filing_type_key",
        "filing_type_map",
        ["source_type", "filing_type_key"],
        unique=False,
    )
    op.create_index(
        "ix_filing_type_map_form_code_doc_type_code",
        "filing_type_map",
        ["form_code", "doc_type_code"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_filing_type_map_form_code_doc_type_code", table_name="filing_type_map")
    op.drop_index("ix_filing_type_map_source_type_filing_type_key", table_name="filing_type_map")
    op.drop_table("filing_type_map")

    op.drop_index("ix_edinet_fetch_jobs_status", table_name="edinet_fetch_jobs")
    op.drop_index("ix_edinet_fetch_jobs_target_date", table_name="edinet_fetch_jobs")
    op.drop_table("edinet_fetch_jobs")

    op.drop_index("ix_edinet_list_responses_filing_type_key", table_name="edinet_list_responses")
    op.drop_index("ix_edinet_list_responses_target_date", table_name="edinet_list_responses")
    op.drop_table("edinet_list_responses")
