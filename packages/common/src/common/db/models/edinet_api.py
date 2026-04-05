from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from common.db.base import Base


class EdinetListResponse(Base):
    __tablename__ = "edinet_list_responses"
    __table_args__ = (
        UniqueConstraint("doc_id"),
        Index("ix_edinet_list_responses_target_date", "target_date"),
        Index("ix_edinet_list_responses_filing_type_key", "filing_type_key"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    doc_id: Mapped[str] = mapped_column(String(32), nullable=False)
    edinet_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    form_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    doc_type_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    filing_type_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    response_path: Mapped[str] = mapped_column(Text, nullable=False)
    response_sha256: Mapped[str | None] = mapped_column(String(128), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class EdinetFetchJob(Base):
    __tablename__ = "edinet_fetch_jobs"
    __table_args__ = (
        UniqueConstraint("doc_id"),
        Index("ix_edinet_fetch_jobs_target_date", "target_date"),
        Index("ix_edinet_fetch_jobs_status", "status"),
    )

    job_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    doc_id: Mapped[str] = mapped_column(String(32), nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    filing_type_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    zip_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    csv_zip_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class FilingTypeMap(Base):
    __tablename__ = "filing_type_map"
    __table_args__ = (
        UniqueConstraint("source_type", "filing_type_key", "form_code", "doc_type_code"),
        Index("ix_filing_type_map_source_type_filing_type_key", "source_type", "filing_type_key"),
        Index("ix_filing_type_map_form_code_doc_type_code", "form_code", "doc_type_code"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    source_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="edinet", server_default=text("'edinet'")
    )
    filing_type_key: Mapped[str] = mapped_column(String(64), nullable=False)
    form_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    doc_type_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    filing_type_raw: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
