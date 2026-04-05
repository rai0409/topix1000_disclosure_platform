# Data Contract (Phase 1)

## company_master 系テーブルの意味
- `company_master`: 企業の正規マスタ。TOPIX 1000 universe に属する企業識別子と基本属性を保持。
- `company_market_attributes`: 市場区分・TOPIX バケット等の時点属性を保持。`(company_id, as_of_date)` で履歴を一意化。
- `company_edinet_links`: 企業と EDINET コードの対応履歴。`valid_from`/`valid_to` で期間管理。

## source_archives テーブルの意味
- EDINET/TDnet をまたいだ raw archive metadata の共通管理テーブル。
- raw binary は DB に保存せず、`storage_path` と検証情報 (`sha256`, `file_size`) のみ保持。

## filing_sources / filings / filing_documents / xbrl_* テーブルの責務
- `filing_sources`: ingest 入力となった ZIP の出所管理。archive type と ZIP path/sha256 を保持。
- `filings`: 1件の開示情報ヘッダ。提出者名の raw/normalized、EDINET code、提出日等を保持。
- `filing_documents`: ZIP 内の PublicDoc/AuditDoc/その他ファイルの一覧と metadata。
- `xbrl_contexts`: XBRL context（期間・entity identifier）を保持。
- `xbrl_context_dimensions`: context に紐づく dimension/member を保持。
- `xbrl_units`: unit 定義（measure）を保持。
- `xbrl_facts`: fact 本体。context/unit 参照、concept 情報、raw 値と Decimal 正規化値を保持。

## Phase 2 downloader テーブルの責務
- `edinet_list_responses`: EDINET list documents API の結果を doc_id 単位で保持。`target_date`, `doc_id`, `form_code`, `doc_type_code`, raw JSON path を管理。
- `edinet_fetch_jobs`: doc_id 単位の取得ジョブ状態。`status`, `attempts`, `zip/pdf/csv` の保存 path、エラーメッセージを保持し、冪等実行の判定に使う。
- `filing_type_map`: EDINET の `form_code`/`doc_type_code` と内部 filing type key の対応表。対象書類フィルタの基準データ。

## raw_value_text と normalized_value_decimal の違い
- `raw_value_text`: XBRL fact の元文字列表現を可能な限り保持する列。変換前の監査用。
- `normalized_value_decimal`: `Decimal` に安全変換できた値のみを保持する列。`NUMERIC(38,10)`。
- 数値化不能な fact は `normalized_value_decimal` を `NULL` にし、文字列値は `raw_text_value` に保持。

## log テーブルの意味
- `request_log`: 外部要求やバッチ要求の実行ログ。
- `ingest_log`: source から raw を取得する ingest 処理ログ。
- `parse_log`: raw 解析処理ログ。
- `normalize_log`: canonical schema への正規化処理ログ。

## env var の責務
- `APP_ENV`: 実行環境識別（local/stg/prod 等）。
- `TZ`: サービスのタイムゾーン。
- `DATABASE_URL`: PostgreSQL 接続先。
- `RAW_STORAGE_ROOT`: raw archive の永続保存ルート。
- `EDINET_API_KEY`: EDINET API 利用キー（将来 ingest 実装で使用）。
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`: メール通知用設定。
- `GENERIC_WEBHOOK_URL`: 汎用 Webhook 通知先。
- `LOG_LEVEL`: ログレベル。
- `APP_DEBUG`: FastAPI debug フラグ。
