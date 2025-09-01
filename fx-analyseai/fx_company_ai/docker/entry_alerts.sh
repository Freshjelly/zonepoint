#!/usr/bin/env bash
set -euo pipefail

INTERVAL_SECONDS="${INTERVAL_SECONDS:-300}"
echo "[fx-alerts] Start loop (interval=${INTERVAL_SECONDS}s, TZ=${TZ:-Asia/Tokyo})"

while true; do
  # MODEは .env / compose 側で alerts に設定される想定
  python -m src.main || echo "[fx-alerts] run failed (continuing)"
  sleep "${INTERVAL_SECONDS}"
done