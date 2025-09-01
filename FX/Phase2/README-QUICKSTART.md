# Zoom → Auto Minutes MVP - Quick Start Guide

## 概要
Zoom録画完了後に自動で議事録を生成し、Google Docsに保存、Discord通知を行うシステム

### 処理方式の選択
3つの処理方式から選択できます：

1. **Webhook方式** - 従来のZoom Webhookを使用（パブリックURLが必要）
2. **Pull方式** - 定期的にZoom APIをポーリング（パブリックURL不要）
3. **Gmail方式** - Gmailでの録画完了通知をトリガーにPull処理を実行

## セットアップ手順

### 1. 環境準備

```bash
# Python 3.9+ が必要
python --version

# venv モジュールがあるか確認
sudo apt install python3-venv -y

# venv を作成
python3 -m venv .venv

# 有効化
source .venv/bin/activate

# 以降はこの環境で pip install
pip install requests

# 依存パッケージインストール
pip install -r requirements.txt

# 環境変数設定
cp .env.example .env
# .env をエディタで開き、必要な値を設定
```

### 2. Zoom Marketplace App設定

#### すべての方式で必要な設定
1. [Zoom Marketplace](https://marketplace.zoom.us/) にアクセス
2. "Build App" → "Server-to-Server OAuth" を選択
3. App Credentials から以下を取得：
   - Account ID
   - Client ID
   - Client Secret

#### Webhook方式の場合の追加設定
4. Event Subscriptions を追加：
   - Subscription name: 任意
   - Event notification endpoint URL: `https://your-domain.com/zoom/webhook`
   - Add events で `recording.completed` を選択
   - Secret Token を生成・保存

#### Pull/Gmail方式の場合
Webhook設定は不要ですが、以下のスコープが必要：
- `recording:read:admin` または `recording:read`
- `user:read:admin` または `user:read`

### 3. Google Service Account設定

```bash
# Google Cloud Console で実行
1. プロジェクトを作成/選択
2. APIs & Services → Enable APIs:
   - Google Docs API
   - Google Drive API

3. Service Account を作成:
   - IAMと管理 → サービスアカウント → 作成
   - JSON キーをダウンロード
   - service-account.json として保存

4. (オプション) G Suite ドメインの場合:
   - Domain-wide delegation を有効化
```

### 4. Discord Webhook設定

1. Discord サーバー設定 → 連携サービス → ウェブフック
2. 新しいウェブフックを作成
3. Webhook URL をコピーして .env に設定

### 5. Gmail方式の場合の追加設定

Gmail方式を使用する場合は追加でGmail APIの設定が必要です：

#### 5.1 Google Cloud Console設定
```bash
1. Google Cloud Console でプロジェクトを選択
2. APIs & Services → Enable APIs:
   - Gmail API を有効化

3. OAuth 2.0 クライアントID を作成:
   - 認証情報 → 認証情報を作成 → OAuth クライアントID
   - アプリケーション種類: デスクトップ アプリケーション
   - JSON をダウンロードして gmail_credentials.json として保存
```

#### 5.2 初回認証
```bash
# Gmail OAuth認証を実行（初回のみ）
python gmail_ingest.py --auth

# ブラウザが開くので Google アカウントでログイン
# 認証後、gmail_token.json が自動生成される
```

### 6. アプリケーション起動

#### Webhook方式の場合
```bash
# .env で INGESTION_MODE=webhook に設定

# 開発環境
uvicorn app:app --reload --port 8000

# 本番環境
uvicorn app:app --host 0.0.0.0 --port 8000
```

#### Pull方式の場合
```bash
# .env で INGESTION_MODE=pull に設定

# 単発実行（Cron用）
python pull_worker.py --once

# 常駐実行（デーモン）
python pull_worker.py --daemon

# Web サーバーも起動（ヘルスチェック用）
uvicorn app:app --host 0.0.0.0 --port 8000
```

#### Gmail方式の場合
```bash
# .env で INGESTION_MODE=gmail に設定

# 単発実行
python gmail_ingest.py

# 常駐実行（デーモン）
python gmail_ingest.py --daemon

# Web サーバーも起動（ヘルスチェック用）
uvicorn app:app --host 0.0.0.0 --port 8000
```

## テスト手順

### 1. ヘルスチェック

```bash
curl http://localhost:8000/health
# Expected: {"ok": true}
```

### 2. Pull方式のテスト

```bash
# 直近6時間の録画をチェック
python pull_worker.py --once

# ログ確認
# 成功例:
# 2024-01-15 10:30:00 - Found 2 recordings in lookback period
# 2024-01-15 10:30:05 - Processing meeting: Weekly Standup
# 2024-01-15 10:30:15 - Successfully processed meeting: Weekly Standup

# 設定確認
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('ZOOM_USER_ID:', os.getenv('ZOOM_USER_ID'))
print('PULL_LOOKBACK_MINUTES:', os.getenv('PULL_LOOKBACK_MINUTES'))
"
```

### 3. Gmail方式のテスト

```bash
# 初回認証テスト
python gmail_ingest.py --auth

# Gmail監視テスト
python gmail_ingest.py

# ログ確認
# 成功例:
# 2024-01-15 10:30:00 - Searching Gmail with query: from:no-reply@zoom.us...
# 2024-01-15 10:30:02 - Found 1 matching emails
# 2024-01-15 10:30:03 - Processing trigger for: Team Meeting
# 2024-01-15 10:30:10 - Processed 1 meetings from email trigger
```

### 4. Webhook方式のURL Validation テスト

```bash
# Zoom の初回検証をシミュレート
curl -X POST http://localhost:8000/zoom/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "event": "endpoint.url_validation",
    "payload": {
      "plainToken": "test123456789"
    }
  }'
```

### 5. Webhook方式のRecording Completed イベントテスト

```python
# test_webhook.py
import hmac
import hashlib
import json
import time
import requests

# .env の値を使用
WEBHOOK_SECRET = "your_webhook_secret_token"
WEBHOOK_URL = "http://localhost:8000/zoom/webhook"

# テストペイロード
payload = {
    "event": "recording.completed",
    "payload": {
        "account_id": "test_account",
        "object": {
            "uuid": "test_meeting_uuid_123",
            "id": 123456789,
            "topic": "テスト会議",
            "type": 2,
            "start_time": "2024-01-15T10:00:00Z",
            "duration": 60,
            "recording_files": [
                {
                    "file_type": "TRANSCRIPT",
                    "download_url": "https://zoom.us/rec/download/test_vtt"
                }
            ]
        }
    }
}

# 署名生成
timestamp = str(int(time.time()))
body = json.dumps(payload)
message = f"v0:{timestamp}:{body}"
signature = "v0=" + hmac.new(
    WEBHOOK_SECRET.encode(),
    message.encode(),
    hashlib.sha256
).hexdigest()

# リクエスト送信
response = requests.post(
    WEBHOOK_URL,
    data=body,
    headers={
        "Content-Type": "application/json",
        "x-zm-signature": signature,
        "x-zm-request-timestamp": timestamp
    }
)

print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
```

### 6. 署名検証失敗テスト

```bash
# 無効な署名でリクエスト
curl -X POST http://localhost:8000/zoom/webhook \
  -H "Content-Type: application/json" \
  -H "x-zm-signature: invalid_signature" \
  -H "x-zm-request-timestamp: 1234567890" \
  -d '{"event": "recording.completed"}'
  
# Expected: 401 Unauthorized
```

### 7. ngrok を使用した実環境テスト（Webhook方式）

```bash
# ngrok インストール
# https://ngrok.com/download

# トンネル開始
ngrok http 8000

# 表示されたURL (https://xxx.ngrok.io) を Zoom Webhook に設定
# 実際の録画完了イベントをテスト
```

## 本番運用

### Cron設定例（Pull方式）

```bash
# crontab -e で以下を追加

# 5分毎にPull実行
*/5 * * * * cd /path/to/zoom-minutes && /usr/bin/python3 pull_worker.py --once >> /var/log/zoom-pull.log 2>&1

# 10分毎にPull実行（軽い負荷）
*/10 * * * * cd /path/to/zoom-minutes && source .venv/bin/activate && python pull_worker.py --once >> /var/log/zoom-pull.log 2>&1

# 毎時0分にログローテーション
0 * * * * logrotate /etc/logrotate.d/zoom-pull

# ログローテーション設定ファイル例（/etc/logrotate.d/zoom-pull）
/var/log/zoom-pull.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    create 0644 ubuntu ubuntu
}
```

### systemd設定例（デーモン方式）

#### Pull方式のsystemdサービス
```bash
# /etc/systemd/system/zoom-pull.service
[Unit]
Description=Zoom Recording Pull Worker
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/zoom-minutes
Environment=PATH=/home/ubuntu/zoom-minutes/.venv/bin
ExecStart=/home/ubuntu/zoom-minutes/.venv/bin/python pull_worker.py --daemon
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target

# サービス有効化
sudo systemctl enable zoom-pull.service
sudo systemctl start zoom-pull.service

# ログ確認
sudo journalctl -u zoom-pull -f
```

#### Gmail方式のsystemdサービス
```bash
# /etc/systemd/system/zoom-gmail.service
[Unit]
Description=Gmail-triggered Zoom Recording Ingestion
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/zoom-minutes
Environment=PATH=/home/ubuntu/zoom-minutes/.venv/bin
ExecStart=/home/ubuntu/zoom-minutes/.venv/bin/python gmail_ingest.py --daemon
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target

# サービス有効化
sudo systemctl enable zoom-gmail.service
sudo systemctl start zoom-gmail.service
```

#### Webサーバーのsystemdサービス（全方式共通）
```bash
# /etc/systemd/system/zoom-web.service
[Unit]
Description=Zoom Minutes Web Server
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/zoom-minutes
Environment=PATH=/home/ubuntu/zoom-minutes/.venv/bin
ExecStart=/home/ubuntu/zoom-minutes/.venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target

# サービス有効化
sudo systemctl enable zoom-web.service
sudo systemctl start zoom-web.service
```

### Docker構成例

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# システム依存関係
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python依存関係
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーション
COPY . .

# 実行用ユーザー
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# 環境変数
ENV PYTHONPATH=/app

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# デフォルトコマンド
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  zoom-minutes-web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - INGESTION_MODE=webhook
    volumes:
      - .env:/app/.env
      - ./service-account.json:/app/service-account.json
    restart: unless-stopped

  zoom-minutes-pull:
    build: .
    command: python pull_worker.py --daemon
    environment:
      - INGESTION_MODE=pull
    volumes:
      - .env:/app/.env
      - ./service-account.json:/app/service-account.json
      - ./state:/app/state
    restart: unless-stopped

  zoom-minutes-gmail:
    build: .
    command: python gmail_ingest.py --daemon
    environment:
      - INGESTION_MODE=gmail
    volumes:
      - .env:/app/.env
      - ./service-account.json:/app/service-account.json
      - ./gmail_credentials.json:/app/gmail_credentials.json
      - ./gmail_token.json:/app/gmail_token.json
      - ./state:/app/state
    restart: unless-stopped
```

### パフォーマンス調整

#### Pull方式
```bash
# .env での調整
PULL_LOOKBACK_MINUTES=180    # 短縮で負荷軽減
PULL_INTERVAL_SECONDS=600    # 間隔延長で負荷軽減

# 複数ユーザー対応
ZOOM_USER_ID=user1@company.com,user2@company.com
```

#### Gmail方式
```bash
# .env での調整
GMAIL_QUERY=from:no-reply@zoom.us subject:"Cloud Recording" newer_than:3d
GMAIL_POLL_INTERVAL_SECONDS=600    # 間隔延長
```

## よくある落とし穴と解決策

### 1. UUID Double Encoding 問題
**問題**: Zoom の meeting UUID に `/` が含まれる場合、API呼び出しが失敗
**解決**: `quote(quote(uuid, safe=''), safe='')` でダブルエンコード

### 2. OAuth トークン付与忘れ
**問題**: 録画ファイルダウンロード時に 401 エラー
**解決**: `download_url` に `?access_token=<token>` を必ず付与

### 3. Google ドメイン共有制限
**問題**: 組織外ユーザーがドキュメントにアクセスできない
**解決**: 
- G Suite 管理コンソールで外部共有を許可
- または `MINUTES_SHARE_ANYONE=false` に設定

### 4. VTT パースエラー
**問題**: Zoom の VTT フォーマットが標準と異なる
**解決**: `utils_vtt.py` のフォールバック処理で対応

### 5. Webhook タイムアウト
**問題**: 3秒以内に応答しないと Zoom が再送信
**解決**: 
- URL validation は即座に返答
- 重い処理は非同期タスクキューに移行（本番環境推奨）

### 6. ffmpeg 依存
**問題**: Whisper使用時に ffmpeg が必要
**解決**: 
```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# または Whisper機能を無効化（VTTのみ使用）
```

**注意**: Whisper音声文字起こし機能はMVPでは未実装です（VTT字幕のみ対応）。将来のバージョンで実装予定。

### 7. タイムゾーン問題
**問題**: 議事録の日付が UTC になる
**解決**: `.env` の `TIMEZONE` を正しく設定（例: `Asia/Tokyo`）

## 実運用メモ

### パフォーマンス最適化
- 大規模会議（2時間超）の処理にはタスクキュー（Celery等）導入推奨
- LLM処理のタイムアウトを調整（現在60秒）
- 依存ライブラリの最新バージョン対応（httpx 0.27+, openai 1.35+）

### セキュリティ強化
- Webhook エンドポイントに rate limiting 追加
- Service Account の権限を最小限に
- ログから機密情報をマスク

### 機能拡張アイデア
1. **Discord 埋め込み拡張**：
   ```python
   embed = {
       "title": doc_title,
       "url": doc_url,
       "fields": [
           {"name": "参加者", "value": "10名"},
           {"name": "時間", "value": "60分"}
       ]
   }
   ```

2. **複数イベント対応**：
   - `meeting.ended`: リアルタイム処理
   - `transcript_completed`: より高品質な文字起こし

3. **ToDo 連携拡張**：
   - Notion Database への自動登録
   - Asana/Trello タスク作成
   - Slack での担当者メンション

### 監視・運用
```bash
# ログ監視
tail -f app.log | grep ERROR

# メトリクス追加例
from prometheus_client import Counter, Histogram

webhook_received = Counter('zoom_webhook_received', 'Webhooks received')
processing_time = Histogram('minutes_processing_seconds', 'Processing time')
```

### トラブルシューティングコマンド

```bash
# Zoom API 接続テスト
python -c "
import asyncio
from app import get_zoom_access_token
print(asyncio.run(get_zoom_access_token()))
"

# Zoom User Recordings テスト（Pull方式）
python -c "
import asyncio
import os
from dotenv import load_dotenv
from pull_worker import get_user_recordings, get_zoom_access_token
load_dotenv()

async def test():
    token = await get_zoom_access_token()
    user_id = os.getenv('ZOOM_USER_ID', 'me')
    data = await get_user_recordings(token, user_id, '2024-01-01', '2024-12-31')
    print(f'Found {len(data.get(\"meetings\", []))} meetings for user {user_id}')

asyncio.run(test())
"

# Gmail認証テスト
python -c "
from gmail_ingest import GmailMonitor
try:
    monitor = GmailMonitor()
    print('Gmail Auth OK')
except Exception as e:
    print(f'Gmail Auth Failed: {e}')
"

# Gmail検索テスト
python -c "
from gmail_ingest import GmailMonitor
monitor = GmailMonitor()
emails = monitor.search_recording_emails()
print(f'Found {len(emails)} recording emails')
"

# 状態ファイル確認
python -c "
import json
from pathlib import Path
state_file = Path('./state/processed.json')
if state_file.exists():
    with open(state_file) as f:
        data = json.load(f)
        print(f'Processed meetings: {len(data.get(\"meetings\", []))}')
        print(f'Processed emails: {len(data.get(\"emails\", []))}')
else:
    print('No state file found')
"

# Google認証テスト
python -c "
from google.oauth2 import service_account
creds = service_account.Credentials.from_service_account_file(
    'service-account.json',
    scopes=['https://www.googleapis.com/auth/documents']
)
print('Auth OK' if creds else 'Auth Failed')
"

# Discord Webhook テスト
curl -X POST $DISCORD_WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{"content": "Test message from Zoom Minutes MVP"}'

# 処理モード確認
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
mode = os.getenv('INGESTION_MODE', 'webhook')
print(f'Current mode: {mode}')
if mode == 'pull':
    print(f'User: {os.getenv(\"ZOOM_USER_ID\", \"me\")}')
    print(f'Lookback: {os.getenv(\"PULL_LOOKBACK_MINUTES\", \"360\")} minutes')
elif mode == 'gmail':
    print(f'Query: {os.getenv(\"GMAIL_QUERY\", \"default\")}')
"
```

## サポート
問題が発生した場合は、以下を確認：
1. すべての環境変数が正しく設定されているか
2. 必要な API が有効化されているか
3. ネットワーク接続とファイアウォール設定
4. ログファイルのエラーメッセージ