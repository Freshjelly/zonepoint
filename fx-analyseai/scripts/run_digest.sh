#!/usr/bin/env bash
set -e
ROOT="/home/hyuga/zonepoint/fx-analyseai"
export PYTHONPATH="$ROOT"
cd "$ROOT"
MODE=digest "$ROOT/.venv/bin/python" -m src.main
