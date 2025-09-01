#!/usr/bin/env bash
# /home/hyuga/zonepoint/fx-analyseai/scripts/reset_seen.sh
set -euo pipefail
cd "$(dirname "$0")/.."
rm -f data/seen_urls.sqlite
echo "✅ reset data/seen_urls.sqlite"