# FX News System - ワンコマンド自動運用

FXニュース記事の本文抽出→日本語要約→Discord通知を完全自動化。

**ワンコマンド運用**: `./scripts/fxnewsctl install:all` を1回実行するだけで、venv構築・設定・cron/systemd導入まで完了。

## 🚀 超簡単セットアップ

### 1. ワンコマンドセットアップ
```bash
# 全自動セットアップ（venv + feeds + .env雛形 + cron/systemd選択導入）
./scripts/fxnewsctl install:all
```

### 2. Discord Webhook設定
```bash
# .envファイルをコピー・編集
cp .env.example .env
# → DISCORD_WEBHOOK* にWebhook URLを設定
```

### 3. 動作確認
```bash
# ヘルスチェック
./scripts/fxnewsctl health

# システム状態確認
./scripts/fxnewsctl status

# 手動テスト実行
./scripts/fxnewsctl run:alerts
```

## 🎯 自動運用

**速報**: 5分おきに巡回、重要度スコア≥3で即時Discord通知  
**朝ダイジェスト**: 毎日6:00 JST（前日6:00→当日6:00）  
**1日ダイジェスト**: 毎日23:30 JST（当日0:00→現在）

OS再起動後も自動で継続動作します。

## 📊 fxnewsctl コマンド

### セットアップ系
```bash
./scripts/fxnewsctl install:all      # 完全自動セットアップ
./scripts/fxnewsctl install:cron     # cron設定のみ
./scripts/fxnewsctl install:systemd  # systemd設定のみ
./scripts/fxnewsctl enable:systemd   # systemdタイマー有効化
./scripts/fxnewsctl disable:systemd  # systemdタイマー無効化
```

### 運用・確認系
```bash
./scripts/fxnewsctl status           # システム状態一覧
./scripts/fxnewsctl health           # ヘルスチェック実行
./scripts/fxnewsctl logs alerts     # 速報ログ表示
./scripts/fxnewsctl logs digest-morning  # 朝ダイジェストログ
./scripts/fxnewsctl logs digest-day      # 1日ダイジェストログ
```

### 手動実行系
```bash
./scripts/fxnewsctl run:alerts          # 速報チェック
./scripts/fxnewsctl run:digest-morning  # 朝ダイジェスト
./scripts/fxnewsctl run:digest-day      # 1日ダイジェスト
```

## 📋 システム仕様

### RSSフィード管理
- **feeds.txt**: 1行1URL、`#`コメント・空行対応
- **初期設定**: 日銀・金融庁・財務省・FRB・BOE・BIS・FXStreet
- **拡張可能**: ユーザーが自由に追加・削除

### スコアリング・通知
- **キーワード判定**: 強(+2)・中(+1)・主要タグ(+1)
- **即時通知**: 合計3点以上
- **スパム制御**: 1時間3件上限、超過はバッチ化
- **重複防止**: ファイルロック(`--lock`)で多重起動防止

### 時間窓管理
- **morning**: 前日6:00→当日6:00（朝ダイジェスト用）
- **day**: 当日0:00→現在（1日ダイジェスト用）
- **JST固定**: Asia/Tokyo タイムゾーン

## 🔧 技術詳細

### 依存関係
- **Python**: 3.8以降（3.12.3で開発・テスト）
- **主要パッケージ**: requests, feedparser, readability-lxml, beautifulsoup4, langdetect, tldextract, python-dotenv, lxml

### API連携（オプション）
- **OpenAI**: 高品質日本語要約（gpt-4o-mini）
- **DeepL**: 翻訳品質向上

### 自動化方式
- **cron**: シンプル・軽量（推奨）
- **systemd**: 高度制御・ログ詳細

## 🛠 トラブルシューティング

### lxml ビルドエラー
```bash
# Ubuntu/Debian
sudo apt-get install libxml2-dev libxslt-dev python3-dev build-essential

# CentOS/RHEL  
sudo yum install libxml2-devel libxslt-devel python3-devel gcc gcc-c++
```

### 設定確認
```bash
./scripts/fxnewsctl status    # 全体状況確認
./scripts/fxnewsctl health    # 詳細ヘルスチェック
```

### ログ確認
```bash
./scripts/fxnewsctl logs alerts           # 速報ログ
./scripts/fxnewsctl logs digest-morning   # 朝ダイジェストログ
./scripts/fxnewsctl logs digest-day       # 1日ダイジェストログ
```

## 📁 ディレクトリ構成

```
/home/hyuga/zonepoint/FX/Phase1/
├── scripts/
│   ├── fxnewsctl              # 一元管理コマンド
│   ├── bootstrap.sh           # venv構築
│   ├── healthcheck.py         # ヘルスチェック  
│   ├── run_alerts.sh          # 速報実行
│   ├── run_digest_morning.sh  # 朝ダイジェスト実行
│   └── run_digest_day.sh      # 1日ダイジェスト実行
├── logs/                      # ログ出力先
├── feeds.txt                  # RSS管理
├── .env                       # 環境変数（要設定）
├── .env.example               # 環境変数テンプレート
├── fx_news.py                 # メインスクリプト
├── requirements.txt           # Python依存関係
└── seen_news.db               # SQLite DB（自動作成）
```

## 🎯 コマンドサンプル

### 初回セットアップ（3ステップ）
```bash
1. ./scripts/fxnewsctl install:all    # 自動セットアップ
2. cp .env.example .env               # Webhook設定
3. ./scripts/fxnewsctl run:alerts     # 動作テスト
```

### 日常運用
```bash
# 状況確認
./scripts/fxnewsctl status

# ログ確認  
./scripts/fxnewsctl logs alerts

# 手動実行
./scripts/fxnewsctl run:digest-morning
```

---

## 💡 3行で運用開始

1. `./scripts/fxnewsctl install:all` - セットアップ
2. `cp .env.example .env` - Webhook設定  
3. `./scripts/fxnewsctl status` - 確認

以後はOS再起動後も自動で速報・ダイジェストが動き続けます。