#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DEBUG=True
export DATABASE_URL="file:$ROOT/.runtime/realworld.sqlite3"
mkdir -p "$ROOT/.runtime"
cd "$ROOT/upstream/backend"
case "${1:-run}" in
  migrate) exec "$ROOT/.venv-backend/bin/python" manage.py migrate ;;
  check) exec "$ROOT/.venv-backend/bin/python" manage.py check ;;
  run) exec "$ROOT/.venv-backend/bin/python" manage.py runserver 127.0.0.1:8000 --noreload ;;
  *) echo 'Usage: bash scripts/backend.sh [migrate|check|run]' >&2; exit 2 ;;
esac
