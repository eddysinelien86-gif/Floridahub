#!/usr/bin/env bash
# Puts a "Keystone Sites" icon on the Desktop that starts the studio app.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
FILE="$DESKTOP/keystone-sites.desktop"
# Remove icons from the old name so you don't get two.
rm -f "$DESKTOP/elio-studio.desktop" "$HOME/.config/autostart/elio-studio.desktop"
chmod +x "$DIR/start-studio.sh"
cat > "$FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Keystone Sites
Comment=Dashboard and demo agent for Keystone Sites
Exec="$DIR/start-studio.sh"
Icon=applications-internet
Terminal=false
Categories=Office;
EOF
chmod +x "$FILE"
gio set "$FILE" metadata::trusted true 2>/dev/null || true
echo "Added Keystone Sites to $DESKTOP"

# Start the studio quietly every time you log in, so the dashboard and agent are always ready.
AUTO="$HOME/.config/autostart"
mkdir -p "$AUTO"
cat > "$AUTO/keystone-sites.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Keystone Sites (background)
Exec="$DIR/start-studio.sh" --no-open
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
echo "Keystone Sites will now start automatically when you log in."
