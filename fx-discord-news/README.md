# FXニュース配信自動化システム

FXニュースを収集・分析し、初心者向けに要約して Discord へ自動配信するシステムです。

## 特徴

- 複数のFXニュースソースからRSS収集
- 通貨ペア・中央銀行・イベント種別の自動抽出
- インパクトスコアに基づくフィルタリング
- 初心者向けの分かりやすい日本語要約
- 「次の一手（考え方）」の教育的ガイド生成
- Discord Webhook経由でのEmbed配信
- 定時配信（朝6時・夜10時）＋速報配信

## セットアップ

### 1. 環境構築

```bash
# プロジェクトのクローン
git clone <repository_url>
cd fx-discord-news
```

#### 仮想環境の構築

Python 3.10以上が必要です。以下のいずれかの方法で仮想環境を構築してください：

##### 方法1: venv を使用（推奨）

```bash
# 仮想環境の作成
source venv/bin/activate

# 仮想環境の有効化
# Linux/macOS の場合:
source venv/bin/activate
# Windows の場合:
# venv\Scripts\activate

# 依存関係のインストール
pip install --upgrade pip
pip install -e .
# または
pip install -r requirements.txt
```

##### 方法2: pyenv + pyenv-virtualenv を使用

```bash
# Python 3.11.7 のインストール
pyenv install 3.11.7

# 仮想環境の作成
pyenv virtualenv 3.11.7 fx-discord-news

# 仮想環境の有効化（プロジェクトディレクトリで自動有効化）
pyenv local fx-discord-news

# 依存関係のインストール
pip install --upgrade pip
pip install -e .
```

##### 方法3: conda を使用

```bash
# 仮想環境の作成と有効化
conda create -n fx-discord-news python=3.11
conda activate fx-discord-news

# 依存関係のインストール
pip install --upgrade pip
pip install -e .
```

##### 仮想環境が正しく設定されているかの確認

```bash
# Pythonのバージョン確認
python --version  # 3.10以上であることを確認

# インストールされたパッケージの確認
pip list

# 必要なパッケージがインストールされているかテスト
python -c "import feedparser, requests, schedule; print('OK')"
```

### 2. 環境変数の設定

```bash
cp .env.example .env
```

`.env` ファイルを編集：

```env
DISCORD_WEBHOOK_BEGINNER=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_PRO=https://discord.com/api/webhooks/...
PROVIDER=anthropic  # または openai
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

### 3. 設定のカスタマイズ

`config.yaml` を編集して、以下を調整：

- `pairs_allowlist`: 監視する通貨ペアのリスト
- `impact_thresholds`: 速報・ダイジェストの閾値
- `schedule`: 配信時刻（JST）
- `feeds`: ニュースソースのRSS URL

## Discord Webhook の作成

1. Discord サーバーの設定 → 連携サービス → Webhook
2. 「新しいWebhook」をクリック
3. 名前を設定（例：FXニュース配信Bot）
4. チャンネルを選択
5. 「Webhook URLをコピー」して `.env` に設定

## 使用方法

### 基本コマンド

```bash
# 朝のダイジェスト配信（手動実行）
python -m src.cli digest --when morning

# 夜のダイジェスト配信（手動実行）
python -m src.cli digest --when night

# 特定ニュースの要約テスト
python -m src.cli summary --url https://example.com/news/article

# Discord送信テスト（ダミー記事）
python -m src.cli test-news

# スケジューラー起動（常駐）
python -m src.cli run-scheduler
```

### スケジューラーの自動起動

#### systemd を使用する場合

`/etc/systemd/system/fx-news.service`:

```ini
[Unit]
Description=FX News Discord Bot
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/fx-discord-news
Environment="PATH=/home/your-user/.pyenv/shims:/usr/bin"
ExecStart=/home/your-user/.pyenv/shims/python -m src.cli run-scheduler
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable fx-news
sudo systemctl start fx-news
```

#### PM2 を使用する場合

```bash
pm2 start "python -m src.cli run-scheduler" --name fx-news
pm2 save
pm2 startup
```

#### cron を使用する場合（簡易版）

```bash
crontab -e
```

```cron
0 6 * * * cd /path/to/fx-discord-news && /usr/bin/python -m src.cli digest --when morning
0 22 * * * cd /path/to/fx-discord-news && /usr/bin/python -m src.cli digest --when night
*/5 * * * * cd /path/to/fx-discord-news && /usr/bin/python -m src.cli check-breaking
```

## トラブルシューティング

### タイムゾーン関連

- システムのタイムゾーンが JST でない場合、`TZ=Asia/Tokyo` を環境変数に設定
- Docker 使用時は `TZ` 環境変数を明示的に指定

### API レート制限

- LLM API のレート制限に達した場合、`config.yaml` の配信頻度を調整
- エラー時は自動的にリトライ（最大3回、指数バックオフ）

### 重複配信の防止

- システムは URL とタイトルの類似度で重複を検知
- 24時間以内の同一記事は自動的にスキップ
- 手動でキャッシュをクリアする場合：`rm -rf .cache/`

### ログの確認

```bash
# ログファイルの確認
tail -f logs/fx-news.log

# エラーログのみ表示
grep ERROR logs/fx-news.log
```

## 注意事項

⚠️ **投資助言に関する免責事項**

- 本システムは教育目的のツールです
- 生成される内容は投資助言ではありません
- 投資判断は必ずご自身の責任で行ってください
- 具体的な売買価格やエントリーポイントの提示は行いません

## ライセンス

MIT License

## サポート

問題が発生した場合は、以下を確認してください：

1. `.env` ファイルの設定が正しいか
2. Discord Webhook URL が有効か
3. LLM API キーが有効か
4. ネットワーク接続が正常か
5. ログファイルにエラーが記録されていないか