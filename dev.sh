#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

# Setup (skipped if already done)
[ -d "$ROOT/backend/.venv" ] || python3 -m venv "$ROOT/backend/.venv"
"$ROOT/backend/.venv/bin/pip" install -q -r "$ROOT/requirements.txt"
[ -f "$ROOT/backend/.env" ] || cp "$ROOT/backend/.env.example" "$ROOT/backend/.env"
[ -f "$ROOT/backend/netracare.db" ] || (cd "$ROOT/backend" && .venv/bin/python -m app.loader)
[ -d "$ROOT/frontend/node_modules" ] || (cd "$ROOT/frontend" && npm install)

# Run both (Ctrl+C stops both)
trap 'kill 0 2>/dev/null' INT TERM EXIT
(cd "$ROOT/backend" && .venv/bin/uvicorn app.main:app --reload --port 8000) &
(cd "$ROOT/frontend" && npm run dev -- --port 5173) &
wait
