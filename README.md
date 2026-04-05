# topix1000_disclosure_platform

TOPIX 1000 を対象 universe とする開示監視基盤の monorepo scaffold です。  
この phase は **EDINET 先行** で、**TDnet は skeleton のみ** 実装しています。

## 必要バージョン
- Ubuntu 24.04 LTS
- Python 3.12.13
- PostgreSQL 17.9
- uv

## 初期セットアップ
1. `.env` を作成
```bash
cp .env.example .env
```

2. 依存インストール
```bash
uv sync
```

3. PostgreSQL 起動
```bash
docker compose up -d
docker compose ps
```

※ `5432` が競合する場合は `POSTGRES_PORT=55432 docker compose up -d` を利用してください。

4. マイグレーション適用
```bash
uv run alembic upgrade head
```

## アプリ起動
`common` と各 app の `src` layout を使うため、起動時は `PYTHONPATH` を指定します。

### edinet_ingest
```bash
PYTHONPATH=packages/common/src:apps/edinet_ingest/src uv run uvicorn edinet_ingest.main:app --host 0.0.0.0 --port 8000
```

### tdnet_monitor
```bash
PYTHONPATH=packages/common/src:apps/tdnet_monitor/src uv run uvicorn tdnet_monitor.main:app --host 0.0.0.0 --port 8001
```

## ヘルスチェック
```bash
curl -s http://127.0.0.1:8000/healthz
curl -s http://127.0.0.1:8000/readyz

curl -s http://127.0.0.1:8001/healthz
curl -s http://127.0.0.1:8001/readyz
```

- `/healthz`: プロセス生存確認 (200)
- `/readyz`: DB 接続確認成功時に 200

## raw storage path の説明
- raw ZIP/PDF/HTML は `RAW_STORAGE_ROOT`（例: `/home/rai/data/topix1000_disclosure/raw`）配下に保存する前提です。
- DB には raw 本体は保存せず、`source_archives` に metadata（パス・ハッシュ・サイズ・取得時刻）だけ保存します。

## 開発補助
### テスト
```bash
uv run pytest
```

### lint
```bash
uv run ruff check .
```

## この phase の非対象
- TDnet scraping 実装
- company seed import

## EDINET sample ZIP ingest (Phase 1)
この phase は **ローカル ZIP ingest のみ** 実装しています。EDINET API へのアクセスは行いません。

### sample ZIP 配置先
- 固定 fixture path:
  - `apps/edinet_ingest/tests/fixtures/Xbrl_Search_20250709_185613.zip`
- `pytest` fixture はこの固定パスを直接参照し、自動生成は行いません。

### Windows 側元ファイルを WSL fixture にコピーする例
```bash
mkdir -p apps/edinet_ingest/tests/fixtures
cp /mnt/c/Users/raira/Desktop/project/Group1-report/1414/Xbrl_Search_20250709_185613.zip \
  apps/edinet_ingest/tests/fixtures/Xbrl_Search_20250709_185613.zip
```

### manifest を確認する
```bash
PYTHONPATH=packages/common/src:apps/edinet_ingest/src \
  uv run python -m edinet_ingest.cli.dump_manifest \
  --zip apps/edinet_ingest/tests/fixtures/Xbrl_Search_20250709_185613.zip
```

ファイルに出力する場合:
```bash
PYTHONPATH=packages/common/src:apps/edinet_ingest/src \
  uv run python -m edinet_ingest.cli.dump_manifest \
  --zip apps/edinet_ingest/tests/fixtures/Xbrl_Search_20250709_185613.zip \
  --output /tmp/edinet_manifest.json
```

### sample ZIP を DB へ ingest する
```bash
PYTHONPATH=packages/common/src:apps/edinet_ingest/src \
  uv run python -m edinet_ingest.cli.ingest_zip \
  --zip apps/edinet_ingest/tests/fixtures/Xbrl_Search_20250709_185613.zip
```

### fixture ingest テストを実行する
```bash
uv run pytest apps/edinet_ingest/tests/test_manifest_and_parsers.py
uv run pytest apps/edinet_ingest/tests/test_ingest_service.py
```

## EDINET API downloader (Phase 2)
Phase 2 では EDINET API v2 の downloader 基盤（list/fetch URL/params/response handling、raw 保存、doc_id 冪等化）を実装しています。  
実 API 疎通は必須ではなく、mocked response テストで検証できます。

### CLI
```bash
PYTHONPATH=packages/common/src:apps/edinet_ingest/src \
  uv run python -m edinet_ingest.cli.fetch_list --date 2026-03-20

PYTHONPATH=packages/common/src:apps/edinet_ingest/src \
  uv run python -m edinet_ingest.cli.fetch_docs --date 2026-03-20

PYTHONPATH=packages/common/src:apps/edinet_ingest/src \
  uv run python -m edinet_ingest.cli.backfill --from 2026-03-20 --to 2026-03-22
```

### API キー未設定時の挙動
- `EDINET_API_KEY` が未設定のまま実 API 呼び出しを行うと、CLI は明確なエラーを返し終了コード `2` で終了します。
- mocked transport を使ったテストでは実 API キー不要で検証できます。

### raw 保存レイアウト
- `/home/rai/data/topix1000_disclosure/raw/edinet/{yyyy}/{mm}/{dd}/{doc_id}/list_response.json`
- `/home/rai/data/topix1000_disclosure/raw/edinet/{yyyy}/{mm}/{dd}/{doc_id}/original.zip`
- `/home/rai/data/topix1000_disclosure/raw/edinet/{yyyy}/{mm}/{dd}/{doc_id}/document.pdf`
- `/home/rai/data/topix1000_disclosure/raw/edinet/{yyyy}/{mm}/{dd}/{doc_id}/csv.zip`

### mocked downloader テスト
```bash
uv run pytest apps/edinet_ingest/tests/test_downloader_client.py
uv run pytest apps/edinet_ingest/tests/test_downloader_services.py
uv run pytest apps/edinet_ingest/tests/test_downloader_cli.py
```
