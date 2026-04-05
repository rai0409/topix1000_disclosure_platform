from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Index, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from common.db.base import Base


class EdinetFactRawCsv(Base):
    __tablename__ = "edinet_facts_raw_csv"
    __table_args__ = (
        Index("ix_edinet_facts_raw_csv_doc_id", "doc_id"),
        Index("ix_edinet_facts_raw_csv_edinet_code", "edinet_code"),
        Index("ix_edinet_facts_raw_csv_element_id", "element_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    doc_id: Mapped[str] = mapped_column(String(32), nullable=False)
    edinet_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source_csv_path: Mapped[str] = mapped_column(Text, nullable=False)
    element_id: Mapped[str] = mapped_column(Text, nullable=False)
    item_name_ja: Mapped[str] = mapped_column(Text, nullable=False)
    context_id: Mapped[str] = mapped_column(Text, nullable=False)
    relative_year_label: Mapped[str] = mapped_column(String(64), nullable=False)
    consolidation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    period_type: Mapped[str] = mapped_column(String(32), nullable=False)
    unit_id: Mapped[str] = mapped_column(String(128), nullable=False)
    unit_label: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_value: Mapped[str] = mapped_column(Text, nullable=False)
    value_text: Mapped[str] = mapped_column(Text, nullable=False)
    value_numeric: Mapped[Decimal | None] = mapped_column(Numeric(38, 10), nullable=True)
    is_numeric: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    is_current_year: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    is_prior_year: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    is_consolidated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
