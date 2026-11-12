#!/usr/bin/env bash
# Run all backend and frontend tests.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
(cd "$ROOT/backend" && .venv/bin/python -m pytest)
(cd "$ROOT/frontend" && npm test && npx tsc -b)
