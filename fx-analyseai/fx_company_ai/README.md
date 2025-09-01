# fx_analyse_ai (MVP)

FXニュースを収集 → 簡易分析（ルール） → Discordへ配信。将来は自社LLM（vLLM等）で要約に切替。

## 主要機能
- **速報配信**: 高インパクトなニュースを即座に通知
- **朝ダイジェスト**: 日次サマリーを定時配信
- **重複防止**: 同一ニュースの重複配信を防止
- **構造化ログ**: JSON形式での詳細ログ出力
- **自動リトライ**: Discord API障害時の指数バックオフ

## セットアップ

⚠️ **重要**: このREADMEは`fx_company_ai/`ディレクトリ内での実行を前提としています。

```bash
# 現在のディレクトリを確認
pwd  # /path/to/fx_analyse_ai/fx_company_ai であることを確認

cp .env.example .env
# .env を編集（DISCORD_WEBHOOK_URL を設定 / 最初は USE_LLM=false 推奨）
# DRY_RUN=true に設定すると実際の送信をスキップしログ出力のみ

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## 実行
```bash
# 速報（アラート） - DRY_RUN有効でテスト
DRY_RUN=true python -m src.main

# 朝ダイジェスト - DRY_RUN有効でテスト
DRY_RUN=true MODE=digest python -m src.main

# 本番送信時は DRY_RUN=false または環境変数なし
python -m src.main
MODE=digest python -m src.main
```

## cron 例
```cron
# JSTサーバでの設定例（JST時刻そのまま）
*/5 * * * * cd /path/fx_analyse_ai/fx_company_ai && /usr/bin/python3 -m src.main
0 6 * * * cd /path/fx_analyse_ai/fx_company_ai && MODE=digest /usr/bin/python3 -m src.main

# UTCサーバでの設定例（JST 6:00 = UTC 21:00前日）
*/5 * * * * cd /path/fx_analyse_ai/fx_company_ai && /usr/bin/python3 -m src.main
0 21 * * * cd /path/fx_analyse_ai/fx_company_ai && MODE=digest /usr/bin/python3 -m src.main
```

## DRY_RUN について
- `DRY_RUN=true`: Discord送信をスキップし、送信予定のペイロードをJSON形式でログ出力
- `DRY_RUN=false` または未設定: 実際にDiscordへ送信
- テスト時は必ず `DRY_RUN=true` に設定してください

## LLMを使う（任意）
- vLLMで Qwen/Qwen2.5-7B-Instruct を起動（model/serve_vllm.sh）
- `.env` で `USE_LLM=true`, `LLM_BASE_URL` を設定

## 注意
本配信は投資助言ではありません。情報の正確性は保証されません。

## Dockerでの実行

### セットアップ
```bash
# 環境変数の設定
cp .env.example .env
# .envファイルを編集してDISCORD_WEBHOOK_URLを設定
```

### Docker Compose実行
```bash
# docker/ディレクトリから実行
cd docker

# 速報サービス起動（常駐）
docker compose up -d fx-alerts

# 速報サービスのログ確認
docker compose logs -f fx-alerts

# ダイジェスト実行（1回実行）
docker compose run --rm fx-digest

# サービス停止
docker compose down
```

### Cron設定（朝ダイジェスト）
```bash
# crontabに追加（JST 6:00に実行）
0 21 * * * /path/to/fx_company_ai/docker/cron_digest.sh >> /var/log/fx_digest.log 2>&1
```

### 速報ループ（5分おき）
```bash
# .env に DISCORD_WEBHOOK_URL を設定してから
docker compose up -d fx-alerts
# ログ確認
docker compose logs -f fx-alerts
```

### 朝ダイジェスト（1回実行）
```bash
# 1回だけ走らせる
docker compose run --rm fx-digest
```

### （推奨）ホストのcronに登録（JST 6:00）
```cron
# JSTサーバの場合（JST 6:00）
0 6 * * * cd /path/to/fx_analyse_ai/fx_company_ai/docker && /usr/bin/docker compose run --rm fx-digest

# UTCサーバの場合（JST 6:00 = UTC 21:00前日）
0 21 * * * cd /path/to/fx_analyse_ai/fx_company_ai/docker && /usr/bin/docker compose run --rm fx-digest
```

### 停止・削除
```bash
docker compose down
```