#!/usr/bin/env bash
# Starts the Keystone Sites studio app (dashboard + demo agent) and opens it in your browser.
# --no-open starts it in the background only (used at login).
cd "$(dirname "$0")"
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
export PATH="$HOME/.local/bin:$PATH"
URL="http://localhost:4321"

running() { node -e "fetch('$URL/api/state').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))" 2>/dev/null; }

if ! running; then
  nohup node studio-server.js >> studio.log 2>&1 &
  for _ in 1 2 3 4 5 6 7 8 9 10; do running && break; sleep 0.5; done
fi
[ "$1" = "--no-open" ] || xdg-open "$URL" >/dev/null 2>&1 || echo "Open $URL in your browser."
