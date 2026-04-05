"""add edinet filing and xbrl tables

Revision ID: 20260322_0002
Revises: 20260322_0001
Create Date: 2026-03-22 00:10:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260322_0002"
down_revision = "20260322_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "filing_sources",
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default=sa.text("'edinet'")),
        sa.Column("archive_type", sa.String(length=64), nullable=False),
        sa.Column("original_zip_path", sa.Text(), nullable=False),
        sa.Column("original_zip_sha256", sa.String(length=128), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("source_id", name="pk_filing_sources"),
        sa.UniqueConstraint("source_type", "original_zip_path", name="uq_filing_sources_source_type_original_zip_path"),
    )

    op.create_table(
        "filings",
        sa.Column("filing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default=sa.text("'edinet'")),
        sa.Column("doc_id", sa.String(length=32), nullable=True),
        sa.Column("edinet_code", sa.String(length=16), nullable=True),
        sa.Column("filer_name_raw", sa.Text(), nullable=False),
        sa.Column("filer_name_normalized", sa.Text(), nullable=False),
        sa.Column("corporate_number", sa.String(length=32), nullable=True),
        sa.Column("filing_title", sa.Text(), nullable=True),
        sa.Column("filing_type_raw", sa.String(length=128), nullable=True),
        sa.Column("submit_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["source_id"], ["filing_sources.source_id"], name="fk_filings_source_id_filing_sources"),
        sa.PrimaryKeyConstraint("filing_id", name="pk_filings"),
    )
    op.create_index("ix_filings_edinet_code", "filings", ["edinet_code"], unique=False)
    op.create_index("ix_filings_submit_date", "filings", ["submit_date"], unique=False)

    op.create_table(
        "filing_documents",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("doc_role", sa.String(length=64), nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(
            ["filing_id"], ["filings.filing_id"], name="fk_filing_documents_filing_id_filings"
        ),
        sa.PrimaryKeyConstraint("document_id", name="pk_filing_documents"),
    )
    op.create_index(
        "ix_filing_documents_filing_id_doc_role",
        "filing_documents",
        ["filing_id", "doc_role"],
        unique=False,
    )

    op.create_table(
        "xbrl_contexts",
        sa.Column("context_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("context_ref", sa.Text(), nullable=False),
        sa.Column("entity_identifier", sa.Text(), nullable=True),
        sa.Column("period_kind", sa.String(length=32), nullable=False),
        sa.Column("instant_date", sa.Date(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["filing_id"], ["filings.filing_id"], name="fk_xbrl_contexts_filing_id_filings"),
        sa.PrimaryKeyConstraint("context_id", name="pk_xbrl_contexts"),
        sa.UniqueConstraint("filing_id", "context_ref", name="uq_xbrl_contexts_filing_id_context_ref"),
    )
    op.create_index(
        "ix_xbrl_contexts_filing_id_period_kind",
        "xbrl_contexts",
        ["filing_id", "period_kind"],
        unique=False,
    )

    op.create_table(
        "xbrl_context_dimensions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("context_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dimension_qname", sa.Text(), nullable=False),
        sa.Column("member_qname", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["context_id"], ["xbrl_contexts.context_id"], name="fk_xbrl_context_dimensions_context_id_xbrl_contexts"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_xbrl_context_dimensions"),
    )
    op.create_index(
        "ix_xbrl_context_dimensions_context_id",
        "xbrl_context_dimensions",
        ["context_id"],
        unique=False,
    )

    op.create_table(
        "xbrl_units",
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("unit_ref", sa.Text(), nullable=False),
        sa.Column("measure_text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["filing_id"], ["filings.filing_id"], name="fk_xbrl_units_filing_id_filings"),
        sa.PrimaryKeyConstraint("unit_id", name="pk_xbrl_units"),
        sa.UniqueConstraint("filing_id", "unit_ref", "measure_text", name="uq_xbrl_units_filing_id_unit_ref_measure_text"),
    )
    op.create_index("ix_xbrl_units_filing_id", "xbrl_units", ["filing_id"], unique=False)

    op.create_table(
        "xbrl_facts",
        sa.Column("fact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("context_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("namespace_uri", sa.Text(), nullable=False),
        sa.Column("concept_name", sa.Text(), nullable=False),
        sa.Column("concept_qname", sa.Text(), nullable=False),
        sa.Column("decimals", sa.Text(), nullable=True),
        sa.Column("is_nil", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("raw_value_text", sa.Text(), nullable=True),
        sa.Column("normalized_value_decimal", sa.Numeric(precision=38, scale=10), nullable=True),
        sa.Column("raw_text_value", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["context_id"], ["xbrl_contexts.context_id"], name="fk_xbrl_facts_context_id_xbrl_contexts"),
        sa.ForeignKeyConstraint(["filing_id"], ["filings.filing_id"], name="fk_xbrl_facts_filing_id_filings"),
        sa.ForeignKeyConstraint(["unit_id"], ["xbrl_units.unit_id"], name="fk_xbrl_facts_unit_id_xbrl_units"),
        sa.PrimaryKeyConstraint("fact_id", name="pk_xbrl_facts"),
    )
    op.create_index(
        "ix_xbrl_facts_filing_id_concept_name",
        "xbrl_facts",
        ["filing_id", "concept_name"],
        unique=False,
    )
    op.create_index(
        "ix_xbrl_facts_filing_id_concept_qname",
        "xbrl_facts",
        ["filing_id", "concept_qname"],
        unique=False,
    )
    op.create_index("ix_xbrl_facts_context_id", "xbrl_facts", ["context_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_xbrl_facts_context_id", table_name="xbrl_facts")
    op.drop_index("ix_xbrl_facts_filing_id_concept_qname", table_name="xbrl_facts")
    op.drop_index("ix_xbrl_facts_filing_id_concept_name", table_name="xbrl_facts")
    op.drop_table("xbrl_facts")
    op.drop_index("ix_xbrl_units_filing_id", table_name="xbrl_units")
    op.drop_table("xbrl_units")
    op.drop_index("ix_xbrl_context_dimensions_context_id", table_name="xbrl_context_dimensions")
    op.drop_table("xbrl_context_dimensions")
    op.drop_index("ix_xbrl_contexts_filing_id_period_kind", table_name="xbrl_contexts")
    op.drop_table("xbrl_contexts")
    op.drop_index("ix_filing_documents_filing_id_doc_role", table_name="filing_documents")
    op.drop_table("filing_documents")
    op.drop_index("ix_filings_submit_date", table_name="filings")
    op.drop_index("ix_filings_edinet_code", table_name="filings")
    op.drop_table("filings")
    op.drop_table("filing_sources")
