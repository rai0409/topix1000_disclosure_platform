"""initial schema

Revision ID: 20260322_0001
Revises:
Create Date: 2026-03-22 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260322_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_master",
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sec_code", sa.String(length=10), nullable=True),
        sa.Column("company_name_raw", sa.Text(), nullable=False),
        sa.Column("company_name_normalized", sa.Text(), nullable=False),
        sa.Column("market_code", sa.String(length=32), nullable=True),
        sa.Column("sector_code", sa.String(length=32), nullable=True),
        sa.Column("universe_name", sa.String(length=64), nullable=False),
        sa.Column("universe_snapshot_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("company_id", name="pk_company_master"),
        sa.UniqueConstraint("sec_code", name="uq_company_master_sec_code"),
    )
    op.create_index(
        "ix_company_master_company_name_normalized",
        "company_master",
        ["company_name_normalized"],
        unique=False,
    )
    op.create_index(
        "ix_company_master_universe_name_is_active",
        "company_master",
        ["universe_name", "is_active"],
        unique=False,
    )

    op.create_table(
        "company_market_attributes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("market_segment", sa.String(length=64), nullable=True),
        sa.Column("scale_category", sa.String(length=64), nullable=True),
        sa.Column("topix_bucket", sa.String(length=64), nullable=True),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["company_master.company_id"], name="fk_company_market_attributes_company_id_company_master"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_company_market_attributes"),
        sa.UniqueConstraint(
            "company_id",
            "as_of_date",
            name="uq_company_market_attributes_company_id_as_of_date",
        ),
    )
    op.create_index(
        "ix_company_market_attributes_topix_bucket",
        "company_market_attributes",
        ["topix_bucket"],
        unique=False,
    )

    op.create_table(
        "company_edinet_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("edinet_code", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["company_master.company_id"], name="fk_company_edinet_links_company_id_company_master"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_company_edinet_links"),
        sa.UniqueConstraint("edinet_code", "valid_to", name="uq_company_edinet_links_edinet_code_valid_to"),
    )
    op.create_index("ix_company_edinet_links_company_id", "company_edinet_links", ["company_id"], unique=False)
    op.create_index("ix_company_edinet_links_edinet_code", "company_edinet_links", ["edinet_code"], unique=False)

    op.create_table(
        "source_archives",
        sa.Column("archive_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_key", sa.Text(), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.String(length=128), nullable=True),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("archive_id", name="pk_source_archives"),
        sa.UniqueConstraint(
            "source_type",
            "source_key",
            "storage_path",
            name="uq_source_archives_source_type_source_key_storage_path",
        ),
    )

    op.create_table(
        "request_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_name", sa.String(length=64), nullable=False),
        sa.Column("request_type", sa.String(length=64), nullable=False),
        sa.Column("target", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_request_log"),
    )

    op.create_table(
        "ingest_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_name", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_key", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("raw_path", sa.Text(), nullable=True),
        sa.Column("sha256", sa.String(length=128), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_ingest_log"),
    )

    op.create_table(
        "parse_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_name", sa.String(length=64), nullable=False),
        sa.Column("parser_name", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_parse_log"),
    )

    op.create_table(
        "normalize_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_name", sa.String(length=64), nullable=False),
        sa.Column("normalize_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_normalize_log"),
    )


def downgrade() -> None:
    op.drop_table("normalize_log")
    op.drop_table("parse_log")
    op.drop_table("ingest_log")
    op.drop_table("request_log")
    op.drop_table("source_archives")
    op.drop_index("ix_company_edinet_links_edinet_code", table_name="company_edinet_links")
    op.drop_index("ix_company_edinet_links_company_id", table_name="company_edinet_links")
    op.drop_table("company_edinet_links")
    op.drop_index("ix_company_market_attributes_topix_bucket", table_name="company_market_attributes")
    op.drop_table("company_market_attributes")
    op.drop_index("ix_company_master_universe_name_is_active", table_name="company_master")
    op.drop_index("ix_company_master_company_name_normalized", table_name="company_master")
    op.drop_table("company_master")
