from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from common.db.base import Base


class FilingSource(Base):
    __tablename__ = "filing_sources"
    __table_args__ = (
        UniqueConstraint("source_type", "original_zip_path"),
    )

    source_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    source_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="edinet", server_default=text("'edinet'")
    )
    archive_type: Mapped[str] = mapped_column(String(64), nullable=False)
    original_zip_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_zip_sha256: Mapped[str | None] = mapped_column(String(128), nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Filing(Base):
    __tablename__ = "filings"
    __table_args__ = (
        Index("ix_filings_edinet_code", "edinet_code"),
        Index("ix_filings_submit_date", "submit_date"),
    )

    filing_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("filing_sources.source_id"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="edinet", server_default=text("'edinet'")
    )
    doc_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    edinet_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    filer_name_raw: Mapped[str] = mapped_column(Text, nullable=False)
    filer_name_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    corporate_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    filing_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    filing_type_raw: Mapped[str | None] = mapped_column(String(128), nullable=True)
    submit_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class FilingDocument(Base):
    __tablename__ = "filing_documents"
    __table_args__ = (
        Index("ix_filing_documents_filing_id_doc_role", "filing_id", "doc_role"),
    )

    document_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    filing_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("filings.filing_id"), nullable=False)
    doc_role: Mapped[str] = mapped_column(String(64), nullable=False)
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(128), nullable=True)


class XbrlContext(Base):
    __tablename__ = "xbrl_contexts"
    __table_args__ = (
        UniqueConstraint("filing_id", "context_ref"),
        Index("ix_xbrl_contexts_filing_id_period_kind", "filing_id", "period_kind"),
    )

    context_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    filing_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("filings.filing_id"), nullable=False)
    context_ref: Mapped[str] = mapped_column(Text, nullable=False)
    entity_identifier: Mapped[str | None] = mapped_column(Text, nullable=True)
    period_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    instant_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class XbrlContextDimension(Base):
    __tablename__ = "xbrl_context_dimensions"
    __table_args__ = (
        Index("ix_xbrl_context_dimensions_context_id", "context_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    context_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("xbrl_contexts.context_id"), nullable=False
    )
    dimension_qname: Mapped[str] = mapped_column(Text, nullable=False)
    member_qname: Mapped[str] = mapped_column(Text, nullable=False)


class XbrlUnit(Base):
    __tablename__ = "xbrl_units"
    __table_args__ = (
        UniqueConstraint("filing_id", "unit_ref", "measure_text"),
        Index("ix_xbrl_units_filing_id", "filing_id"),
    )

    unit_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    filing_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("filings.filing_id"), nullable=False)
    unit_ref: Mapped[str] = mapped_column(Text, nullable=False)
    measure_text: Mapped[str] = mapped_column(Text, nullable=False)


class XbrlFact(Base):
    __tablename__ = "xbrl_facts"
    __table_args__ = (
        Index("ix_xbrl_facts_filing_id_concept_name", "filing_id", "concept_name"),
        Index("ix_xbrl_facts_filing_id_concept_qname", "filing_id", "concept_qname"),
        Index("ix_xbrl_facts_context_id", "context_id"),
    )

    fact_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    filing_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("filings.filing_id"), nullable=False)
    context_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("xbrl_contexts.context_id"), nullable=False
    )
    unit_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("xbrl_units.unit_id"), nullable=True)
    namespace_uri: Mapped[str] = mapped_column(Text, nullable=False)
    concept_name: Mapped[str] = mapped_column(Text, nullable=False)
    concept_qname: Mapped[str] = mapped_column(Text, nullable=False)
    decimals: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_nil: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    raw_value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_value_decimal: Mapped[Decimal | None] = mapped_column(Numeric(38, 10), nullable=True)
    raw_text_value: Mapped[str | None] = mapped_column(Text, nullable=True)
