#!/usr/bin/env bash
# Make Insulation Lead Finders start automatically when the Pi boots.
#
#   ./install-autostart.sh            backend + public tunnel only (screen stays free)
#   ./install-autostart.sh screen     also open the dashboard full-screen on the Pi
#   ./install-autostart.sh off        stop starting anything at boot
#
# Run once. Running it again with a different word switches the mode.

DIR="$(cd "$(dirname "$0")" && pwd)"
MODE="${1:-backend}"
DESKTOP="$HOME/.config/autostart/insulation-leadfinders.desktop"
MARK="# leadfinders-autostart"

case "$MODE" in
  backend|screen|off) ;;
  *) echo "Unknown option '$MODE'. Use: backend, screen, or off."; exit 1 ;;
esac

# Start from a clean slate so the two modes never both run.
rm -f "$DESKTOP"
KEEP="$(crontab -l 2>/dev/null | grep -vF "$MARK")"   # your other scheduled jobs, untouched
printf '%s\n' "$KEEP" | sed '/^$/d' | crontab -

if [ "$MODE" = "off" ]; then
  echo "Autostart removed. Start by hand with:  $DIR/start.sh"
  exit 0
fi

if [ "$MODE" = "backend" ]; then
  # Runs at boot even if nobody logs in to the desktop.
  { printf '%s\n' "$KEEP"; echo "@reboot sleep 20; \"$DIR/start.sh\" >/dev/null 2>&1 $MARK"; } | sed '/^$/d' | crontab -
  echo "Installed: the backend and public tunnel now start about 20 seconds after every boot."
  echo "The Pi's screen is left alone. To undo:  $0 off"
  exit 0
fi

# screen mode: start everything, then open the dashboard fullscreen.
mkdir -p "$(dirname "$DESKTOP")"
BROWSER=chromium-browser
command -v chromium-browser >/dev/null 2>&1 || BROWSER=chromium

cat > "$DESKTOP" <<ENTRY
[Desktop Entry]
Type=Application
Name=Insulation Lead Finders
Exec=bash -c "$DIR/start.sh; sleep 6; $BROWSER --kiosk --noerrdialogs --disable-infobars --disable-session-crashed-bubble http://localhost:8000"
X-GNOME-Autostart-enabled=true
ENTRY

echo "Installed: $DESKTOP"
echo "On the next reboot, the Pi starts the backend + tunnel and opens the dashboard fullscreen."
echo "To undo:  $0 off"
