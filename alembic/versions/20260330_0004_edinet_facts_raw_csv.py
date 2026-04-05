"""add edinet facts raw csv table

Revision ID: 20260330_0004
Revises: 20260326_0003
Create Date: 2026-03-30 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260330_0004"
down_revision = "20260326_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "edinet_facts_raw_csv",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("doc_id", sa.String(length=32), nullable=False),
        sa.Column("edinet_code", sa.String(length=16), nullable=True),
        sa.Column("source_csv_path", sa.Text(), nullable=False),
        sa.Column("element_id", sa.Text(), nullable=False),
        sa.Column("item_name_ja", sa.Text(), nullable=False),
        sa.Column("context_id", sa.Text(), nullable=False),
        sa.Column("relative_year_label", sa.String(length=64), nullable=False),
        sa.Column("consolidation_type", sa.String(length=32), nullable=False),
        sa.Column("period_type", sa.String(length=32), nullable=False),
        sa.Column("unit_id", sa.String(length=128), nullable=False),
        sa.Column("unit_label", sa.String(length=64), nullable=False),
        sa.Column("raw_value", sa.Text(), nullable=False),
        sa.Column("value_text", sa.Text(), nullable=False),
        sa.Column("value_numeric", sa.Numeric(precision=38, scale=10), nullable=True),
        sa.Column("is_numeric", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_current_year", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_prior_year", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_consolidated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id", name="pk_edinet_facts_raw_csv"),
    )
    op.create_index("ix_edinet_facts_raw_csv_doc_id", "edinet_facts_raw_csv", ["doc_id"], unique=False)
    op.create_index(
        "ix_edinet_facts_raw_csv_edinet_code",
        "edinet_facts_raw_csv",
        ["edinet_code"],
        unique=False,
    )
    op.create_index(
        "ix_edinet_facts_raw_csv_element_id",
        "edinet_facts_raw_csv",
        ["element_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_edinet_facts_raw_csv_element_id", table_name="edinet_facts_raw_csv")
    op.drop_index("ix_edinet_facts_raw_csv_edinet_code", table_name="edinet_facts_raw_csv")
    op.drop_index("ix_edinet_facts_raw_csv_doc_id", table_name="edinet_facts_raw_csv")
    op.drop_table("edinet_facts_raw_csv")
