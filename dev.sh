#!/usr/bin/env bash
# Start the PanPay backend (FastAPI) and frontend (Vite) together for local dev.
# Requires Postgres reachable at the DATABASE_URL in backend/.env.
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

cleanup() { kill 0 2>/dev/null; }
trap cleanup EXIT INT TERM

echo "▶ backend  : http://localhost:8000  (docs at /docs)"
echo "▶ frontend : http://localhost:5173"
echo

( cd "$ROOT/backend" && . .venv/bin/activate && alembic upgrade head && uvicorn app.main:app --reload --port 8000 ) &
( cd "$ROOT/frontend" && npm run dev ) &

wait
