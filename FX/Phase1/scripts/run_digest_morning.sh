#!/bin/bash
#
# FX News 朝ダイジェスト実行スクリプト  
# 前日6:00→当日6:00のダイジェスト
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
echo "🌅 FX News 朝ダイジェスト実行"
echo "時刻: $(date '+%Y-%m-%d %H:%M:%S')"

python fx_news.py \
    --mode digest \
    --digest-kind morning \
    --max-digest-items 30 \
    --tz Asia/Tokyo \
    --feeds-file feeds.txt \
    --lock /tmp/fxnews_digest_morning.lock \
    "$@"

echo "✅ 朝ダイジェスト完了"