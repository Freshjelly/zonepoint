#!/usr/bin/env bash
set -euo pipefail

# Move to docker directory
cd "$(dirname "$0")"

# Load environment if .env exists
if [ -f "../.env" ]; then
    export $(grep -v '^#' ../.env | xargs)
fi

# Run digest and capture exit code
if docker compose -f compose.yml run --rm fx-digest; then
    echo "[$(date)] fx-digest completed successfully"
    exit 0
else
    EXIT_CODE=$?
    echo "[$(date)] fx-digest failed with exit code: $EXIT_CODE"
    
    # Send notification to Discord if webhook is configured
    if [[ -n "${DISCORD_WEBHOOK_URL:-}" ]]; then
        curl -sS -H "Content-Type: application/json" -X POST \
            -d "{\"content\":\"[fx-digest] 実行に失敗しました (exit code: $EXIT_CODE) :warning:\"}" \
            "$DISCORD_WEBHOOK_URL" || true
    fi
    
    exit $EXIT_CODE
fi