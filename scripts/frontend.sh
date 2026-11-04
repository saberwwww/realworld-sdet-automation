#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export VITE_API_URL=http://127.0.0.1:8000/api
cd "$ROOT/upstream/frontend"
exec npm run serve
