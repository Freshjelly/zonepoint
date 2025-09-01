#!/bin/bash
#
# FX News 速報実行スクリプト
# 重要度スコア>=3で即時Discord通知
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

# venv確認・有効化
if [ ! -d ".venv" ]; then
    echo "❌ .venvが見つかりません。bootstrap.shを実行してください"
    exit 1
fi

source .venv/bin/activate

# 実行
echo "🚨 FX News 速報モード実行"
echo "時刻: $(date '+%Y-%m-%d %H:%M:%S')"

python fx_news.py \
    --mode fetch-alert \
    --max-items 40 \
    --tz Asia/Tokyo \
    --feeds-file feeds.txt \
    --lock /tmp/fxnews_alerts.lock \
    "$@"

echo "✅ 速報チェック完了"