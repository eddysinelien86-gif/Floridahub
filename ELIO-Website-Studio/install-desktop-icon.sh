#!/usr/bin/env bash
# Puts an "ELIO Studio" icon on the Desktop that starts the studio app.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
FILE="$DESKTOP/elio-studio.desktop"
chmod +x "$DIR/start-studio.sh"
cat > "$FILE" <<EOF
[Desktop Entry]
Type=Application
Name=ELIO Studio
Comment=Dashboard and demo agent for ELIO Website Studio
Exec="$DIR/start-studio.sh"
Icon=applications-internet
Terminal=false
Categories=Office;
EOF
chmod +x "$FILE"
gio set "$FILE" metadata::trusted true 2>/dev/null || true
echo "Added ELIO Studio to $DESKTOP"

# Start the studio quietly every time you log in, so the dashboard and agent are always ready.
AUTO="$HOME/.config/autostart"
mkdir -p "$AUTO"
cat > "$AUTO/elio-studio.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=ELIO Studio (background)
Exec="$DIR/start-studio.sh" --no-open
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
echo "ELIO Studio will now start automatically when you log in."
