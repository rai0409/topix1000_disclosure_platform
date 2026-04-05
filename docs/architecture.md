# Architecture (Phase 1 Scaffold)

## この phase で EDINET を先に実装する理由
- TOPIX 1000 監視の初期価値を最短で出すため、まず EDINET を先行実装対象にする。
- EDINET は有報・四半期報告などの一次開示を早期に取り込めるため、監視基盤の根幹機能を検証しやすい。

## 将来 TDnet XBRL ZIP ingest を追加する前提
- `apps/tdnet_monitor` は skeleton のみを先行配置し、後続 phase で TDnet ingest adapter を追加する。
- raw archive の永続化は `source_archives` を source 非依存で設計しているため、EDINET/TDnet の共通運用が可能。

## source-specific ingest と canonical schema を分離する理由
- source adapter は EDINET/TDnet 固有の収集仕様を閉じ込める。
- アプリ利用側は `packages/common/schemas` を通じた canonical schema に依存し、source 差分の影響を受けにくくする。
- 将来 source が増えても、ingest 側の変更を app-facing contract に波及させない。

## raw は filesystem、DB は metadata のみ
- raw ZIP/PDF/HTML は HDD 前提の filesystem (`RAW_STORAGE_ROOT`) に永続保存する。
- DB は raw 実体ではなく、`source_archives` で保存先・ハッシュ・取得時刻などの metadata のみ管理する。
- PostgreSQL は SSD 前提で、検索性と一貫性が必要な正規化データとログに専念させる。
