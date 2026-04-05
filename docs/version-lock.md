# Version Lock Policy

## 固定理由
- **Python 3.12.13**: 実行環境差異を避け、型ヒント・async 周辺の挙動を統一するため。
- **PostgreSQL 17.9**: DDL/制約挙動を環境間で一致させるため。
- **主要ライブラリの patch pin**: ingest・DB・API 層の依存差分を最小化し、再現性を高めるため。

## Patch Pin 一覧
- fastapi==0.129.2
- sqlalchemy==2.0.48
- alembic==1.18.4
- pydantic==2.12.5
- pydantic-settings==2.11.0
- psycopg[binary]==3.3.3
- lxml==6.0.0
- uvicorn[standard]==0.42.0
- httpx==0.28.1
- pandas==2.2.3
- python-dotenv==1.1.0
- tenacity==9.1.2
- pytest==8.3.5
- pytest-asyncio==0.26.0
- ruff==0.13.2
