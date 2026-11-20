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
