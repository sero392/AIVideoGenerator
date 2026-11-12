#!/usr/bin/env bash
# One-time local setup: backend virtualenv (Python 3.11+) and frontend packages.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

PYTHON="${PYTHON:-}"
if [[ -z "$PYTHON" ]]; then
  for candidate in python3.13 python3.12 python3.11; do
    if command -v "$candidate" >/dev/null 2>&1; then PYTHON="$candidate"; break; fi
  done
fi

cd "$ROOT/backend"
if [[ -n "$PYTHON" ]]; then
  "$PYTHON" -m venv .venv
  .venv/bin/pip install -r requirements.txt
elif command -v uv >/dev/null 2>&1; then
  uv venv --python 3.11 .venv
  uv pip install --python .venv/bin/python -r requirements.txt
else
  echo "Python 3.11+ not found. Install it (python.org) or install uv and re-run." >&2
  exit 1
fi
[[ -f .env ]] || cp .env.example .env

cd "$ROOT/frontend"
npm install
echo "Setup complete. Start with scripts/dev-backend.sh and scripts/dev-frontend.sh"
