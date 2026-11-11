#!/usr/bin/env bash
# Make Insulation Lead Finders launch automatically on boot:
# starts the backend + public tunnel, then opens the dashboard fullscreen.
# Run once:  ./install-autostart.sh

DIR="$(cd "$(dirname "$0")" && pwd)"
AUTO="$HOME/.config/autostart"
mkdir -p "$AUTO"

# Pick whichever Chromium command exists on this Pi
BROWSER=chromium-browser
command -v chromium-browser >/dev/null 2>&1 || BROWSER=chromium

cat > "$AUTO/insulation-leadfinders.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Insulation Lead Finders
Exec=bash -c "$DIR/start.sh; sleep 6; $BROWSER --kiosk --noerrdialogs --disable-infobars --disable-session-crashed-bubble http://localhost:8000"
X-GNOME-Autostart-enabled=true
EOF

echo "Installed: $AUTO/insulation-leadfinders.desktop"
echo "On the next reboot, the Pi starts the backend + tunnel and opens the dashboard fullscreen."
echo "To undo:   rm $AUTO/insulation-leadfinders.desktop"
