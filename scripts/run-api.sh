#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
API_DIR="$PROJECT_ROOT/apps/api"
PYTHON_BIN="$API_DIR/venv/bin/python"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "Python venv not found: $PYTHON_BIN"
  echo "Run first:"
  echo "  cd $API_DIR"
  echo "  python3 -m venv venv"
  echo "  ./venv/bin/pip install -r requirements.txt"
  exit 1
fi

cd "$API_DIR"
exec "$PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port "${API_PORT:-8100}"
