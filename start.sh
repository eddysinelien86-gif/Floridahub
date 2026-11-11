#!/usr/bin/env bash
# Insulation Lead Finders — start everything with one command.
#
#   1) Copy backend/secrets.env.example to backend/secrets.env and set your
#      password (and optional API key) there. That file is NOT committed.
#   2) Run:  ./start.sh
#
# Starts the backend and (if cloudflared is installed) a public tunnel, both in
# the background so closing the terminal won't kill them.

# Repo root = the folder this script lives in (works wherever it's cloned)
DIR="$(cd "$(dirname "$0")" && pwd)"

# Load secrets if present (MARKETHUB_PASSWORD, ANTHROPIC_API_KEY, MARKETHUB_*).
if [ -f "$DIR/backend/secrets.env" ]; then
  set -a
  . "$DIR/backend/secrets.env"
  set +a
  echo "Loaded settings from backend/secrets.env"
else
  echo "NOTE: no backend/secrets.env found — running without a password/API key."
  echo "      Copy backend/secrets.env.example to backend/secrets.env to set them."
fi

# Stop anything already running
pkill -f markethub_server 2>/dev/null
pkill -f "cloudflared tunnel" 2>/dev/null
sleep 1

# Start the backend in the background
cd "$DIR/backend" || exit 1
nohup python3 markethub_server.py > "$HOME/backend.log" 2>&1 &
sleep 3
echo "=== Backend ==="
curl -s -o /dev/null -w "localhost:8000 -> %{http_code} (401 = password-locked, 200 = open)\n" localhost:8000/

# Start the public tunnel if cloudflared is installed
if command -v cloudflared >/dev/null 2>&1; then
  if [ -f "$HOME/.cloudflared/config.yml" ]; then
    # Permanent named tunnel (your own domain)
    nohup cloudflared tunnel run > "$HOME/tunnel.log" 2>&1 &
    echo "=== Permanent tunnel started ==="
    [ -n "$MARKETHUB_PUBLIC_URL" ] && echo "Public form: ${MARKETHUB_PUBLIC_URL%/}/lead"
  else
    # Fallback: free random quick tunnel
    nohup cloudflared tunnel --url http://localhost:8000 > "$HOME/tunnel.log" 2>&1 &
    sleep 10
    echo "=== Public URL (share this + /lead) ==="
    grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$HOME/tunnel.log" | tail -1
  fi
else
  echo "(cloudflared not installed — public tunnel skipped)"
fi

echo ""
echo "Dashboard:  http://localhost:8000   (login: ${MARKETHUB_USER:-admin} / your password)"
echo "To stop:    pkill -f markethub_server; pkill -f cloudflared"
