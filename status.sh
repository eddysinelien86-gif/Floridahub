#!/usr/bin/env bash
# Show what's running for Insulation Lead Finders.

echo "=== Processes ==="
if pgrep -f markethub_server >/dev/null; then
  echo "backend   : RUNNING  (pid $(pgrep -f markethub_server | tr '\n' ' '))"
else
  echo "backend   : stopped"
fi
if pgrep -f "cloudflared tunnel" >/dev/null; then
  echo "tunnel    : RUNNING  (pid $(pgrep -f 'cloudflared tunnel' | tr '\n' ' '))"
else
  echo "tunnel    : stopped"
fi

echo ""
echo "=== Backend ==="
code=$(curl -s -o /dev/null -w "%{http_code}" localhost:8000/ 2>/dev/null)
if [ "$code" = "000" ] || [ -z "$code" ]; then
  echo "localhost:8000 : not responding"
else
  echo "localhost:8000 : up (HTTP $code)"
fi

echo ""
echo "=== Public URL (share this + /lead) ==="
grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$HOME/tunnel.log" 2>/dev/null | tail -1 || echo "(no tunnel URL found)"

echo ""
echo "Dashboard on the Pi : http://localhost:8000"
echo "Start everything    : cd ~/Floridahub && ./start.sh"
echo "Stop everything     : pkill -f markethub_server; pkill -f cloudflared"
