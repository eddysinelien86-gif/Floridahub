#!/usr/bin/env bash
# Insulation Lead Finders — pull the latest code from GitHub and restart.
#
#   ./update.sh            update the branch this Pi is already on
#   ./update.sh <branch>   switch to another branch, then update
#
# Your settings (backend/secrets.env) and saved data are not touched.

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1

BRANCH="${1:-$(git rev-parse --abbrev-ref HEAD)}"
BEFORE="$(git rev-parse HEAD)"

echo "=== Getting the latest '$BRANCH' from GitHub ==="
if ! git fetch origin "$BRANCH"; then
  echo "Could not reach GitHub. Nothing was changed."
  exit 1
fi

if [ "$BRANCH" != "$(git rev-parse --abbrev-ref HEAD)" ]; then
  if ! git checkout "$BRANCH"; then
    echo "Could not switch to '$BRANCH' (see the message above). Nothing was changed."
    exit 1
  fi
fi

if ! git merge -q --ff-only "origin/$BRANCH"; then
  echo "This Pi has its own edits that clash with the update. Nothing was changed."
  echo "Run 'git status' and send the output to get help."
  exit 1
fi

AFTER="$(git rev-parse HEAD)"
if [ "$BEFORE" = "$AFTER" ]; then
  echo "Already up to date."
else
  echo "=== What changed ==="
  git log --oneline "$BEFORE..$AFTER"
  # Install new Python packages only when the list changed.
  if ! git diff --quiet "$BEFORE" "$AFTER" -- backend/requirements.txt; then
    echo "=== Installing new Python packages ==="
    pip install -r backend/requirements.txt --break-system-packages 2>/dev/null \
      || pip install -r backend/requirements.txt
  fi
fi

echo "=== Restarting the dashboard backend ==="
"$DIR/start.sh"

# If the dashboard is open full-screen on the Pi's display, reload it.
if pgrep -f -- "--kiosk" >/dev/null 2>&1; then
  BROWSER=chromium-browser
  command -v chromium-browser >/dev/null 2>&1 || BROWSER=chromium
  pkill -f -- "--kiosk"
  sleep 2
  DISPLAY="${DISPLAY:-:0}" WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}" \
    XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}" \
    nohup "$BROWSER" --kiosk --noerrdialogs --disable-infobars \
    --disable-session-crashed-bubble http://localhost:8000 >/dev/null 2>&1 &
  echo "Reloaded the full-screen dashboard."
fi

echo "Done."
