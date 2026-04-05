from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from common.db.base import Base


class CompanyMaster(Base):
    __tablename__ = "company_master"
    __table_args__ = (
        Index("ix_company_master_company_name_normalized", "company_name_normalized"),
        Index("ix_company_master_universe_name_is_active", "universe_name", "is_active"),
    )

    company_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    sec_code: Mapped[str | None] = mapped_column(String(10), nullable=True, unique=True)
    company_name_raw: Mapped[str] = mapped_column(Text, nullable=False)
    company_name_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    market_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sector_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    universe_name: Mapped[str] = mapped_column(String(64), nullable=False)
    universe_snapshot_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CompanyMarketAttribute(Base):
    __tablename__ = "company_market_attributes"
    __table_args__ = (
        UniqueConstraint("company_id", "as_of_date"),
        Index("ix_company_market_attributes_topix_bucket", "topix_bucket"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("company_master.company_id"), nullable=False
    )
    market_segment: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scale_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    topix_bucket: Mapped[str | None] = mapped_column(String(64), nullable=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CompanyEdinetLink(Base):
    __tablename__ = "company_edinet_links"
    __table_args__ = (
        UniqueConstraint("edinet_code", "valid_to"),
        Index("ix_company_edinet_links_company_id", "company_id"),
        Index("ix_company_edinet_links_edinet_code", "edinet_code"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("company_master.company_id"), nullable=False
    )
    edinet_code: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
