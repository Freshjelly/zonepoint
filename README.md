# 🎯 ZonePoint - FX Analysis & Trading Intelligence Platform

## 📖 概要

ZonePointは、FX取引に関する情報を自動収集・分析し、Discord経由で配信する統合プラットフォームです。

### 🔧 主要機能

- **FX Analysis AI** - 企業ニュースとFX市場の関係を分析
- **Discord News** - RSS/経済カレンダーからのニュース配信
- **YouTube Insights** - YouTube動画からのFX関連情報抽出
- **Multi-Phase Integration** - 段階的なデータ処理パイプライン

## 🚀 Docker開発環境のセットアップ

### 前提条件

- Docker Desktop または Docker Engine
- Docker Compose
- Git

### クイックスタート

1. **リポジトリのクローン**
```bash
git clone https://github.com/Freshjelly/zonepoint.git
cd zonepoint
```

2. **開発環境のセットアップ**
```bash
./scripts/dev-setup.sh
```

3. **環境変数の設定**
各プロジェクトの `.env` ファイルを編集してAPIキーを設定：
- `fx-analyseai/.env`
- `fx-discord-news/.env`
- `fx-youtube-insights/.env`

4. **開発環境の起動**
```bash
./scripts/dev-commands.sh start
```

5. **コンテナに接続**
```bash
./scripts/dev-commands.sh shell
```

### 🔧 開発コマンド

```bash
# 基本操作
./scripts/dev-commands.sh start          # 開発環境開始
./scripts/dev-commands.sh stop           # 全サービス停止
./scripts/dev-commands.sh shell          # コンテナに接続
./scripts/dev-commands.sh logs           # ログ表示

# 各サービスの起動
./scripts/dev-commands.sh fx-ai          # FX Analysis AI
./scripts/dev-commands.sh fx-news        # Discord News
./scripts/dev-commands.sh fx-youtube     # YouTube Insights
./scripts/dev-commands.sh digest         # ダイジェスト実行

# メンテナンス
./scripts/dev-commands.sh build          # 環境再構築
./scripts/dev-commands.sh clean          # クリーンアップ
./scripts/dev-commands.sh status         # ステータス確認
```

### 🌐 アクセス可能なポート

- **8000**: 汎用Webサービス
- **8080**: 代替Webポート
- **8501**: Streamlit (YouTube Insights)
- **5000**: Flask/FastAPI サービス

## 📁 プロジェクト構成

```
zonepoint/
├── fx-analyseai/          # FX企業ニュース分析
├── fx-discord-news/       # Discord ニュース配信
├── fx-youtube-insights/   # YouTube分析
├── FX/                    # レガシーコード
│   ├── Phase1/           # 初期実装
│   ├── Phase2/           # 改良版
│   └── Phase3/           # 最新版
├── docker-compose.yml     # Docker構成
├── Dockerfile.dev         # 開発環境用Dockerfile
└── scripts/              # セットアップスクリプト
```

## 🔑 必要な環境変数

### FX Analysis AI
```bash
OPENAI_API_KEY=your_api_key
ANTHROPIC_API_KEY=your_api_key
DISCORD_WEBHOOK_URL=your_webhook_url
```

### Discord News
```bash
DISCORD_WEBHOOK_BEGINNER=your_webhook_url
DISCORD_WEBHOOK_PRO=your_webhook_url
OPENAI_API_KEY=your_api_key
ANTHROPIC_API_KEY=your_api_key
```

### YouTube Insights
```bash
YOUTUBE_API_KEY=your_api_key
DISCORD_WEBHOOK_URL=your_webhook_url
```

## 🛠 開発ワークフロー

### 1. 新機能の開発
```bash
# 開発環境起動
./scripts/dev-commands.sh start

# コンテナに接続
./scripts/dev-commands.sh shell

# プロジェクトディレクトリに移動
cd fx-analyseai  # または他のプロジェクト

# 開発・テスト
python -m src.main
```

### 2. ダイジェスト機能のテスト
```bash
# ドライランモードでテスト
./scripts/dev-commands.sh digest
```

### 3. Webアプリケーションの開発
```bash
# YouTube Insights (Streamlit)
./scripts/dev-commands.sh fx-youtube

# ブラウザでhttp://localhost:8501にアクセス
```

## 🔍 ログとデバッグ

```bash
# 全サービスのログ
./scripts/dev-commands.sh logs

# 特定のサービスのログ
./scripts/dev-commands.sh logs fx-analyseai

# コンテナ内でのデバッグ
./scripts/dev-commands.sh shell
tail -f /workspace/logs/*.log
```

## 📊 各プロジェクトの詳細

### FX Analysis AI (`fx-analyseai/`)
企業ニュースを収集し、FX市場への影響を分析してDiscordに配信

### Discord News (`fx-discord-news/`)
RSSフィードと経済カレンダーから情報を収集し、重要度スコアリング後にDiscord配信

### YouTube Insights (`fx-youtube-insights/`)
YouTubeからFX関連動画を分析し、トレンドや重要情報を抽出

## 🤝 コントリビューション

1. フィーチャーブランチを作成
2. Docker環境で開発・テスト
3. コミットしてプルリクエスト作成

## 📄 ライセンス

このプロジェクトは開発中です。