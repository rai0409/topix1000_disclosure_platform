from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class CompanyMasterSchema(BaseModel):
    company_id: UUID
    sec_code: str | None
    company_name_raw: str
    company_name_normalized: str
    market_code: str | None
    sector_code: str | None
    universe_name: str
    universe_snapshot_date: date | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
