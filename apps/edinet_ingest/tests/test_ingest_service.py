from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from common.db.base import Base
from common.db.models import Filing, FilingDocument, FilingSource, XbrlContext, XbrlFact, XbrlUnit
from common.db.session import reset_engine_cache
from common.settings import get_settings
from edinet_ingest.ingest.service import ingest_zip_archive
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker


def test_ingest_zip_persists_records(sample_zip_path, tmp_path) -> None:
    db_path = tmp_path / "ingest.sqlite3"
    database_url = f"sqlite+pysqlite:///{db_path}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    summary = ingest_zip_archive(sample_zip_path, session_factory=session_factory)

    assert summary.main_xbrl_path.startswith("PublicDoc/")
    assert summary.contexts_count > 0
    assert summary.units_count > 0
    assert summary.facts_count > 0

    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(FilingSource)) == 1
        assert session.scalar(select(func.count()).select_from(Filing)) == 1
        assert session.scalar(select(func.count()).select_from(FilingDocument)) > 0
        assert session.scalar(select(func.count()).select_from(XbrlContext)) >= 1
        assert session.scalar(select(func.count()).select_from(XbrlUnit)) >= 1
        assert session.scalar(select(func.count()).select_from(XbrlFact)) >= 1
        assert session.scalar(
            select(func.count()).select_from(XbrlFact).where(XbrlFact.normalized_value_decimal.is_not(None))
        ) >= 1
        assert session.scalar(
            select(func.count()).select_from(XbrlFact).where(XbrlFact.raw_text_value.is_not(None))
        ) >= 1


def test_ingest_after_alembic_upgrade(sample_zip_path, monkeypatch) -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not set")

    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    reset_engine_cache()

    root_dir = Path(__file__).resolve().parents[3]
    alembic_cfg = Config(str(root_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(root_dir / "alembic"))
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(database_url)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    summary = ingest_zip_archive(sample_zip_path, session_factory=session_factory)
    assert summary.facts_count > 0
