# FX YouTube Analytics 📊

**YouTube × FX界隈の週次動向を即判断するための"軽量だけど本格"分析ツール**

業界全体の視聴回数変動と自チャンネルの動向を比較分析し、パフォーマンスが業界要因かコンテンツ要因かを判定するツールです。

## 🎯 目的・機能

**核心的質問への回答**:
- FX界隈（業界全体）の視聴回数が先週比でどう動いたか？
- 自チャンネルの落ち込み/伸びは業界要因かコンテンツ要因か？

**判定ロジック**:
- 🌊 **業界要因**: 全体 < -10% かつ Z-Score > -1.0 → 全体要因濃厚
- 🎯 **コンテンツ要因**: 全体 -5%~+5% かつ Z-Score < -1.0 → コンテンツ要因濃厚  
- 🏆 **勝ち**: Z-Score > +1.0 → 業界平均を大幅上回り
- 🔄 **複合**: その他 → 複合的要因

## 🚀 クイックスタート

### 1. 環境セットアップ

```bash
# リポジトリをクローン
git clone <your-repo>
cd fx-youtube-insights

# 依存関係をインストール
make install
# または
pip install -r requirements.txt

# 設定ファイルを作成
cp .env.example .env
```

### 2. 環境変数設定

`.env`ファイルを編集:

```env
# YouTube Data API v3 キー (必須)
YOUTUBE_API_KEY=your_youtube_api_key_here

# Discord Webhook URL (オプション)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN

# タイムゾーン (固定)
TZ=Asia/Tokyo
```

**YouTube API キー取得方法**:
1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクト作成
2. YouTube Data API v3 を有効化
3. 認証情報 → APIキー を作成

**Discord Webhook URL取得方法**:
1. Discordサーバー → サーバー設定 → 連携サービス → Webhook
2. 新しいWebhookを作成
3. WebhookのURLをコピー

### 3. 監視チャンネル設定

`config/seed_channels.csv`を編集:

```csv
channel_id,title
UCxxxxxxxxxxxxxx,実際のチャンネル名1
UCyyyyyyyyyyyyyy,実際のチャンネル名2
UCzzzzzzzzzzzzzz,実際のチャンネル名3
```

チャンネルIDの確認方法:
- YouTubeチャンネルページのURL: `https://www.youtube.com/channel/UCxxxxxxxxxxxxxx`
- または`https://www.youtube.com/@チャンネル名`の場合、ページソースで`"externalId"`を検索

### 4. 起動方法

**開発環境（ダミーデータ）**:
```bash
make dev-setup  # ダミーデータでセットアップ
make run        # ダッシュボード起動
```

**本番環境**:
```bash
make snapshot   # データ収集
make rollup     # 週次集計
make run        # ダッシュボード起動
```

ダッシュボードは http://localhost:8501 でアクセス可能

## 📋 使用方法

### データ収集・分析

```bash
# 1回限りの収集
make snapshot

# 週次メトリクス計算
make rollup

# Discord レポート送信
make discord

# 完全パイプライン実行
make full-pipeline
```

### 個別スクリプト実行

```bash
# データ収集
python scripts/run_snapshot.py

# 週次集計
python scripts/run_rollup.py

# Discord投稿
python scripts/post_weekly_digest.py

# Discord接続テスト
python scripts/post_weekly_digest.py --test
```

### ダッシュボード機能

**メイン画面**:
- 📊 **KPI カード**: 業界総視聴増分、週次増減率、トレンド、分析動画数
- 📈 **比較グラフ**: 業界平均線 vs チャンネル別パフォーマンス
- 🏆 **トップ動画テーブル**: 今週増分TOP20（タイトル/チャンネル/増分/増減率）

**サイドパネル**:
- 🎯 **要因分析**: チャンネル選択→判定結果表示
- 📺 **チャンネル一覧**: 全チャンネルのZ-Score付きパフォーマンス

## ⚙️ 設定カスタマイズ

### 分析設定（`config/app.yaml`）

```yaml
# 分析パラメータ
analysis:
  industry_delta_threshold: 10.0  # 業界要因判定のしきい値(%)
  zscore_threshold: 1.0           # Z-Score判定のしきい値
  min_videos_for_stats: 10        # 統計に必要な最小動画数
  top_n_videos: 20                # レポート表示動画数

# YouTube API設定
youtube:
  search_limit_per_run: 50        # 1回の検索結果上限
  search_days: 14                 # 検索対象期間（日）
```

### 検索キーワード（`config/keywords_ja.txt`）

```
FX
為替
ドル円
USDJPY
ポンド円
# 追加したいキーワードを行ごとに記述
```

## 🤖 自動化（GitHub Actions）

GitHub Actionsで完全自動化:

**スケジュール**:
- 📅 **毎日 02:00, 14:00 JST**: データ収集
- 📅 **毎週月曜 09:00 JST**: 週次レポートをDiscordに配信

**必要なシークレット設定**:
1. GitHub Repository → Settings → Secrets and variables → Actions
2. 以下のシークレットを追加:
   - `YOUTUBE_API_KEY`: YouTube API キー
   - `DISCORD_WEBHOOK_URL`: Discord Webhook URL

**手動実行**:
- Actions タブ → 「FX YouTube Analytics Pipeline」→ 「Run workflow」
- 実行アクション: `snapshot`, `rollup`, `discord`, `full-pipeline`

## 📁 プロジェクト構成

```
fx-youtube-insights/
├─ README.md                    # このファイル
├─ requirements.txt             # Python依存関係
├─ .env.example                 # 環境変数テンプレート
├─ Makefile                     # タスク自動化
├─ config/
│  ├─ app.yaml                  # アプリケーション設定
│  ├─ seed_channels.csv         # 監視チャンネル一覧
│  └─ keywords_ja.txt           # 検索キーワード
├─ data/
│  └─ analytics.duckdb          # DuckDB データベース
├─ etl/                         # データ処理
│  ├─ schema.py                 # DB スキーマ・マイグレーション
│  ├─ youtube_client.py         # YouTube API クライアント
│  ├─ snapshot.py               # データ収集
│  └─ rollup.py                 # 週次集計・Z-Score計算
├─ app/
│  └─ streamlit_app.py          # Streamlit ダッシュボード
├─ bots/
│  └─ discord_report.py         # Discord 週次レポート
├─ scripts/                     # 実行スクリプト
│  ├─ run_snapshot.py
│  ├─ run_rollup.py
│  └─ post_weekly_digest.py
├─ logs/                        # ログファイル
└─ .github/workflows/
   └─ pipeline.yml              # GitHub Actions自動化
```

## 🔧 データベース仕様

**DuckDB テーブル**:

```sql
-- チャンネル情報
channels(channel_id, title, custom_url, published_at)

-- チャンネル統計スナップショット  
channel_stats(channel_id, snapshot_date, view_count, subscriber_count, video_count)

-- 動画情報
videos(video_id, channel_id, title, published_at, duration)

-- 動画統計スナップショット
video_stats(video_id, snapshot_date, view_count, like_count, comment_count)

-- 週次メトリクス（集計結果）
weekly_metrics(scope, entity_id, week_start, views_delta_week, delta_pct, zscore)
```

**指標計算**:
- `views_delta_week`: 週内視聴増分 = 週末視聴数 - 週初視聴数  
- `delta_pct`: 先週比% = (今週増分 - 先週増分) / 先週増分 * 100
- `zscore`: (自チャンネル増減率 - 業界中央値) / 業界標準偏差

## 🛠️ トラブルシューティング

### よくある問題

**1. APIキーエラー**:
```bash
# エラー: No YouTube API key provided
# 解決: .env ファイルにYOUTUBE_API_KEY を設定
```

**2. データが表示されない**:
```bash
# 開発用ダミーデータで確認
make dev-setup
make run
```

**3. Discord通知が来ない**:
```bash
# Webhook接続テスト
make discord-test
```

**4. GitHub Actions失敗**:
- Repository Secrets が正しく設定されているか確認
- Actions タブのログを確認

### ログ確認

```bash
# 最新のログを確認
tail -f logs/snapshot.log
tail -f logs/rollup.log  
tail -f logs/discord.log
```

### データベースリセット

```bash
# 全データを削除（要注意）
make reset-db
```

## 🌟 高度な使用方法

### カスタム分析

```python
# Python スクリプトで直接分析
from etl.rollup import WeeklyRollup

rollup = WeeklyRollup()
metrics = rollup.calculate_weekly_metrics()

# 特定チャンネルの判定
judgement = rollup.get_channel_judgement('UCxxxxxxxxxx')
print(judgement['message'])  # 判定結果
```

### Discord カスタマイズ

`bots/discord_report.py`の`_create_embed()`メソッドを編集してレポート形式をカスタマイズ

### 分析期間の変更

`config/app.yaml`の`youtube.search_days`を変更（デフォルト: 14日）

## 📞 サポート・貢献

**課題報告**: GitHubのIssuesで報告してください

**機能追加**: Pull Requestを歓迎します

**設定支援**: READMEの手順に従っても動作しない場合はIssueで相談してください

## 📄 ライセンス

MIT License - 詳細は LICENSE ファイルを参照

---

**Powered by Claude Code** 🤖 | **Built with Streamlit, DuckDB, YouTube API** 

業界動向を把握し、コンテンツ戦略の精度向上にお役立てください！