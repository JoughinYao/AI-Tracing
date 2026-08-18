#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WEB_DIR="$PROJECT_ROOT/apps/web"

cd "$WEB_DIR"

if [ ! -d node_modules ]; then
  npm install
fi

exec npm run dev -- --host 0.0.0.0 --port "${WEB_PORT:-5174}"
