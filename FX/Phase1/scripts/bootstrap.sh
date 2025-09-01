#!/bin/bash
#
# Bootstrap script for FX News System
# PEP668対応のvenv環境セットアップ
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🚀 FX News System ブートストラップ開始"
echo "プロジェクトディレクトリ: $PROJECT_DIR"

# Python3の確認
if ! command -v python3 &> /dev/null; then
    echo "❌ エラー: python3が見つかりません"
    echo "   Python 3.8以降をインストールしてください"
    exit 1
fi

echo "✅ Python $(python3 --version) を確認"

# プロジェクトディレクトリに移動
cd "$PROJECT_DIR"

# venv作成
echo "📦 仮想環境を作成中..."
if [ -d ".venv" ]; then
    echo "⚠️  既存の.venvディレクトリを検出。再作成します..."
    rm -rf .venv
fi

python3 -m venv .venv

# venv有効化
echo "🔧 仮想環境を有効化中..."
source .venv/bin/activate

# pip/wheelアップグレード
echo "📦 pip/wheelをアップグレード中..."
pip install --upgrade pip wheel

# 依存関係インストール
echo "📚 依存関係をインストール中..."
if [ -f requirements.txt ]; then
    # lxmlビルドエラー対策でタイムアウト延長
    if ! pip install -r requirements.txt --timeout 300; then
        echo ""
        echo "❌ 依存関係インストールでエラーが発生しました"
        echo ""
        echo "【lxml系ビルドエラーの場合の対処法】"
        echo "Ubuntu/Debian:"
        echo "  sudo apt-get update"
        echo "  sudo apt-get install libxml2-dev libxslt-dev python3-dev build-essential"
        echo ""
        echo "CentOS/RHEL:"
        echo "  sudo yum install libxml2-devel libxslt-devel python3-devel gcc gcc-c++"
        echo ""
        echo "対処後、再度実行してください: ./scripts/bootstrap.sh"
        exit 1
    fi
else
    echo "❌ エラー: requirements.txt が見つかりません"
    exit 1
fi

echo ""
echo "✅ ブートストラップ完了！"
echo ""
echo "次のステップ:"
echo "1. 設定確認: python scripts/healthcheck.py"
echo "2. 速報テスト: ./scripts/run_alerts.sh"
echo "3. ダイジェストテスト: ./scripts/run_digest_morning.sh"
echo ""
echo "venv有効化コマンド: source .venv/bin/activate"

exit 0