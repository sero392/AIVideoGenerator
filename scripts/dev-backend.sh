#!/usr/bin/env bash
# Start FastAPI with auto-reload on http://localhost:8000 (docs: /docs)
set -euo pipefail
cd "$(dirname "$0")/../backend"
exec .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port "${PORT:-8000}"
