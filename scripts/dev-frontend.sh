#!/usr/bin/env bash
# Start the Vite dev server on http://localhost:5173 (proxies /api to :8000)
set -euo pipefail
cd "$(dirname "$0")/../frontend"
exec npm run dev -- --host 127.0.0.1 --port "${PORT:-5173}" --strictPort
