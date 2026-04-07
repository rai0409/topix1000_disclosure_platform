# topix1000_disclosure_platform

An early-stage disclosure monitoring platform for the TOPIX 1000 universe.

The current primary track of this repository is **EDINET ingest / raw archive / database persistence**.  
**TDnet is implemented only as a skeleton** at this stage, and production-grade ingestion logic for TDnet is not included yet.

This repository is intended to serve as the foundation for a disclosure data ETL and monitoring platform, including:

- EDINET list API retrieval
- EDINET document retrieval (`original.zip`, `document.pdf`, `csv.zip`)
- raw file storage with path / hash tracking
- fetch job / request log / ingest log persistence
- database tables for downstream normalization and analytics
- FastAPI-based health and readiness endpoints

---

## Current status

### Implemented

#### EDINET ingest
- `fetch_list` CLI for EDINET list API retrieval
- `fetch_docs` CLI for EDINET document retrieval
- `backfill` CLI for date-range backfill
- `doc_id`-based fetch job management
- raw file persistence for:
  - `list_response.json`
  - `original.zip`
  - `document.pdf`
  - `csv.zip`
- invalid CSV response handling with:
  - `csv_error.json`

#### API / service
- `edinet_ingest` FastAPI app
- `tdnet_monitor` FastAPI skeleton
- `/healthz`
- `/readyz` (database connectivity check)

#### Database
- EDINET list response persistence
- EDINET fetch job persistence
- filing type mapping
- request / ingest / parse / normalize log table group
- raw EDINET CSV facts table (`edinet_facts_raw_csv`)

### Not implemented yet
- TDnet scraping / ingestion
- company master seed import
- TOPIX 1000 constituent import / maintenance
- company ↔ EDINET code mapping completion
- downstream serving API for disclosures
- alerting / notification workflow
- dashboard / UI

---

## Repository layout

```text
.
├── alembic/
├── apps/
│   ├── edinet_ingest/
│   └── tdnet_monitor/
├── packages/
│   └── common/
├── docs/
├── docker-compose.yml
├── pyproject.toml
├── .env.example
└── LICENSE
```

### apps

- `apps/edinet_ingest`
  - EDINET ingest service
  - CLI entrypoints
  - downloader implementation
  - tests
- `apps/tdnet_monitor`
  - TDnet monitor skeleton
  - health endpoints only at this stage

### packages/common

Shared components:
- settings
- DB engine / session
- ORM models
- common schemas
- logging utilities

---

## Tech stack

- Python `3.12.13`
- FastAPI
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- `uv`
- `httpx`
- `pandas`

---

## Environment

Create `.env` from `.env.example`.

```bash
cp .env.example .env
```

Example:

```env
APP_ENV=local
TZ=Asia/Tokyo
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:55432/topix1000_disclosure
RAW_STORAGE_ROOT=/home/rai/data/topix1000_disclosure/raw
EDINET_API_KEY=
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM=
GENERIC_WEBHOOK_URL=
LOG_LEVEL=INFO
APP_DEBUG=false
```

---

## Setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Start PostgreSQL

```bash
docker compose up -d
docker compose ps
```

If port `5432` is already in use:

```bash
POSTGRES_PORT=55432 docker compose up -d
```

### 3. Apply migrations

```bash
uv run alembic upgrade head
```

---

## Run services

Because this repository uses `packages/common/src` and app-local `src` layouts, set `PYTHONPATH` explicitly.

### EDINET ingest

```bash
PYTHONPATH=packages/common/src:apps/edinet_ingest/src \
uv run uvicorn edinet_ingest.main:app --host 0.0.0.0 --port 8000
```

### TDnet monitor skeleton

```bash
PYTHONPATH=packages/common/src:apps/tdnet_monitor/src \
uv run uvicorn tdnet_monitor.main:app --host 0.0.0.0 --port 8001
```

---

## Health checks

```bash
curl -s http://127.0.0.1:8000/healthz
curl -s http://127.0.0.1:8000/readyz

curl -s http://127.0.0.1:8001/healthz
curl -s http://127.0.0.1:8001/readyz
```

- `/healthz`: process liveness
- `/readyz`: database connectivity

---

## EDINET CLI

### Fetch list API for a date

```bash
PYTHONPATH=packages/common/src:apps/edinet_ingest/src \
uv run python -m edinet_ingest.cli.fetch_list --date 2026-03-20
```

### Fetch documents for a date

```bash
PYTHONPATH=packages/common/src:apps/edinet_ingest/src \
uv run python -m edinet_ingest.cli.fetch_docs --date 2026-03-20
```

### Backfill a date range

```bash
PYTHONPATH=packages/common/src:apps/edinet_ingest/src \
uv run python -m edinet_ingest.cli.backfill --from 2026-03-20 --to 2026-03-22
```

### Behavior when `EDINET_API_KEY` is missing

If `EDINET_API_KEY` is not set, the CLI exits with a clear error and status code `2`.

---

## Raw storage layout

Raw files are stored under `RAW_STORAGE_ROOT`.

Example layout:

```text
/home/rai/data/topix1000_disclosure/raw/edinet/{yyyy}/{mm}/{dd}/{doc_id}/
├── list_response.json
├── original.zip
├── document.pdf
├── csv.zip
└── csv_error.json   # only when the CSV response is invalid
```

The database stores metadata and file paths, while raw bodies remain on the filesystem.

---

## Database model overview

Current important tables include:

- `edinet_list_responses`
  - list API response metadata per `doc_id`
- `edinet_fetch_jobs`
  - per-document fetch execution state
- `filing_type_map`
  - filing type resolution map
- `edinet_facts_raw_csv`
  - normalized raw facts extracted from EDINET CSV
- `request_logs`
- `ingest_logs`
- `parse_logs`
- `normalize_logs`

This repository is designed so that ingest, normalization, and downstream serving can be developed incrementally on top of persisted raw data.

---

## Testing

```bash
uv run pytest
```

You can also run targeted tests as needed.

---

## Lint

```bash
uv run ruff check .
```

---

## Scope of the current phase

### In scope
- EDINET ingest foundation
- raw archive persistence
- DB-backed fetch job management
- readiness / health endpoints
- downstream normalization-ready data model foundation

### Out of scope for now
- TDnet production ingestion
- company / ticker universe import
- TOPIX 1000 master maintenance
- alert delivery
- UI / dashboard

---

## Notes

This repository is intentionally being built in phases.

The current phase focuses on making EDINET retrieval reproducible and operable:
- raw files are persisted
- job state is tracked
- failures are logged
- retry / backfill workflows are possible

## License

This project is licensed under the MIT License.  
See the [LICENSE](./LICENSE) file for details.

The next logical steps are:
1. harden the EDINET CSV normalization pipeline
2. complete company / EDINET / ticker mapping
3. add TOPIX 1000 universe management
4. implement TDnet ingestion
5. build the serving / alerting layer
