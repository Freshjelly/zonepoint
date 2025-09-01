# FX AnalyseAI

FXニュース分析・配信システムのMVP実装。RSSフィードから記事を収集し、簡易分析またはLLMによる要約を行い、Discord Webhookで配信します。

## 📁 プロジェクト構成

```
fx-analyseai/
├── fx_company_ai/           # メインアプリケーション
│   ├── src/                 # コアロジック（収集・分析・配信）
│   ├── config/              # 設定ファイル（rules.yml）
│   ├── model/               # LLM学習・推論スクリプト
│   ├── bot/                 # Discord Bot（オプション）
│   ├── data/                # 学習データ・DB
│   ├── docker/              # Docker環境
│   │   ├── Dockerfile.app
│   │   ├── docker-compose.yml
│   │   └── entry_alerts.sh
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md
└── Claude_Code_Prompt_FX_Company_AI.md  # プロンプト仕様書
```

## 🚀 クイックスタート

### 1. ローカル実行

```bash
# fx-analyseaiディレクトリから開始
cd fx_company_ai  # ⚠️ 重要: fx_company_aiサブディレクトリに移動

# 環境設定
cp .env.example .env
# .envを編集してDISCORD_WEBHOOK_URLを設定

# 仮想環境セットアップ
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# パッケージインストール
pip install -r requirements.txt

# 実行
python -m src.main          # 速報モード（重要度3.0以上）
MODE=digest python -m src.main  # ダイジェストモード
```

### 2. Docker実行（推奨）

```bash
cd fx_company_ai/docker

# ビルド
docker compose build

# 速報サービス起動（5分間隔）
docker compose up -d fx-alerts

# ログ確認
docker compose logs -f fx-alerts

# ダイジェスト実行（1回のみ）
docker compose run --rm fx-digest

# 停止
docker compose down
```

## ⚙️ 機能概要

### コア機能
- **RSS収集**: 主要FXニュースサイト・中央銀行のRSSフィードを監視
- **通貨検出**: ニュースから関連通貨ペアを自動検出
- **イベント分類**: 政策・インフレ・雇用統計等にカテゴライズ
- **センチメント分析**: タカ派/ハト派の判定
- **重要度スコアリング**: ニュースの市場影響度を算出
- **Discord配信**: Webhookでリアルタイム配信

### 動作モード
1. **速報モード** (`MODE=alerts`)
   - 5分間隔で新着ニュースをチェック
   - 重要度3.0以上のニュースを即座に配信
   - Docker: `fx-alerts`サービスで常時稼働

2. **ダイジェストモード** (`MODE=digest`)
   - 1日の主要ニュースをまとめて配信
   - 毎朝6:00 JST実行を推奨
   - Docker: `fx-digest`をcronで実行

## 🤖 LLM連携（オプション）

`.env`で`USE_LLM=true`に設定すると、OpenAI互換APIを使用した要約に切り替わります。

### vLLMサーバーの起動
```bash
# GPUマシンで実行
cd fx_company_ai/model
bash serve_vllm.sh
```

### 環境変数設定
```env
USE_LLM=true
LLM_BASE_URL=http://localhost:8000/v1
LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
```

## 📅 定期実行設定

### crontab例
```cron
# 速報（5分ごと）
*/5 * * * * cd /path/to/fx_company_ai && /usr/bin/python3 -m src.main

# 朝ダイジェスト（JST 6:00 = UTC 21:00）
0 21 * * * cd /path/to/fx_company_ai && MODE=digest /usr/bin/python3 -m src.main

# Docker版
0 6 * * * cd /path/to/fx_company_ai/docker && /usr/bin/docker compose run --rm fx-digest
```

## 📝 設定ファイル

### .env
```env
# Discord設定
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxx
DISCORD_BOT_TOKEN=（オプション）

# LLM設定
USE_LLM=false
LLM_BASE_URL=http://localhost:8000/v1
LLM_MODEL=Qwen/Qwen2.5-7B-Instruct

# アラート設定
ALERT_IMPACT_THRESHOLD=3.0
DIGEST_MAX_ITEMS=10
```

### config/rules.yml
- イベント検出ルール（政策・インフレ・雇用等）
- タカ派/ハト派判定用キーワード
- 通貨ペアマッピング

## 🔧 開発・カスタマイズ

### ディレクトリ構成
- `src/ingest.py`: RSS収集・重複チェック
- `src/classify.py`: 通貨検出・イベント分類
- `src/scoring.py`: センチメント・重要度算出
- `src/summarizer.py`: 要約生成（ルール/LLM切替）
- `src/publish.py`: Discord配信
- `src/main.py`: メインループ

### 学習データ追加
`data/train.jsonl`と`data/val.jsonl`にJSONL形式でデータを追加し、`model/train_lora.py`でファインチューニングが可能です。

## ⚠️ 注意事項

- 本システムの配信内容は投資助言ではありません
- ニュースの正確性・完全性は保証されません
- 実際の投資判断は自己責任で行ってください
- Discord Webhook URLは外部に漏らさないよう注意してください

## 📄 ライセンス

内部利用向けMVP実装

## 🆘 トラブルシューティング

### ImportError: feedparser
```bash
pip install feedparser
```

### Docker起動エラー
```bash
# 権限エラーの場合
sudo usermod -aG docker $USER
# 再ログイン後に再実行
```

### Discord配信されない
- `.env`の`DISCORD_WEBHOOK_URL`が正しく設定されているか確認
- ネットワーク接続を確認
- `docker compose logs fx-alerts`でエラーログを確認

---

詳細な仕様は `Claude_Code_Prompt_FX_Company_AI.md` を参照してください。