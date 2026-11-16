#!/usr/bin/env bash
# Floridahub bot launcher — works on Termux (Android), Raspberry Pi, or any Linux.
# Usage: bash start.sh
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR/backend"

# Pick whichever Python is available.
PY="$(command -v python3 || command -v python || true)"
if [ -z "$PY" ]; then
  echo "Python is not installed. On Termux run:  pkg install python -y"
  exit 1
fi

PORT="${MARKETHUB_PORT:-8000}"
echo "========================================"
echo "  Floridahub trend bot starting..."
echo "  Open this on the phone's browser:"
echo "      http://localhost:$PORT"
echo "  (Ctrl+C to stop)"
echo "========================================"
MARKETHUB_PORT="$PORT" "$PY" markethub_server.py
