# EDINET Disclosure Ingestion Pipeline for Japanese Financial Data Workflows

A Python ETL foundation for ingesting, storing, and serving Japanese disclosure data for downstream monitoring and analysis.

## What this solves

Financial disclosure workflows are often slowed down by raw archive handling, inconsistent filing artifacts, and manual ingestion steps.

This repository focuses on building a repeatable EDINET-first ingestion path with raw persistence, database logging, and service readiness checks.

## Current focus

The current primary track is EDINET ingest, raw archive storage, and database persistence.

TDnet support exists only as an early skeleton and is not yet production-ready.

## What it does

- retrieves EDINET list API responses
- downloads filing artifacts such as `original.zip`, `document.pdf`, and `csv.zip`
- stores raw files with path and hash tracking
- persists fetch jobs and ingest logs
- provides database tables for downstream normalization and analytics
- exposes FastAPI health and readiness endpoints

## Repository layout

```text
.
├── alembic/
├── apps/
│   ├── edinet_ingest/
│   └── tdnet_monitor/
├── docs/
├── packages/
│   └── common/
├── .env.example
├── .gitignore
├── .python-version
├── LICENSE
├── README.md
├── alembic.ini
├── docker-compose.yml
├── pyproject.toml
├── ruff.toml
└── uv.lock
```

## Quick start

```bash
uv sync
docker compose up -d
uv run alembic upgrade head
```

## Stack

Python, FastAPI, SQLAlchemy, Alembic, PostgreSQL, uv, httpx, pandas

## License

This repository is source-available for personal study, research, and evaluation.  
Commercial use requires prior written permission and a separate paid license.  
See `LICENSE` for details.
