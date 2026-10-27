#!/usr/bin/env bash
set -euo pipefail

APP_ID=io.github.Gavin_Tan1.RogLighting
SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.local/share/rog-lighting"
APPS="$HOME/.local/share/applications"
ICONS="$HOME/.local/share/icons/hicolor/scalable/apps"
RULE=/etc/udev/rules.d/70-rog-lighting.rules

echo "Copying app to $DEST"
mkdir -p "$DEST/rog_lighting" "$APPS" "$ICONS"
install -m 755 "$SRC/rog-lighting" "$SRC/uninstall.sh" "$DEST/"
install -m 644 "$SRC"/rog_lighting/*.py "$DEST/rog_lighting/"
install -m 644 "$SRC/rog-lighting.svg" "$ICONS/$APP_ID.svg"

cat > "$APPS/$APP_ID.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=ROG Lighting
Comment=Keyboard backlight and Slash lighting
Exec=/usr/bin/python3 "$DEST/rog-lighting"
Icon=$APP_ID
Categories=Settings;HardwareSettings;
Keywords=keyboard;backlight;rgb;aura;slash;asus;rog;
StartupNotify=true
DESKTOP

AUTOSTART="$HOME/.config/autostart/rog-lighting-daemon.desktop"
if [ -f "$AUTOSTART" ]; then
  sed -i "s|^Exec=.*|Exec=/usr/bin/python3 \"$DEST/rog-lighting\" daemon|" "$AUTOSTART"
fi

if ! cmp -s "$SRC/70-rog-lighting.rules" "$RULE" 2>/dev/null; then
  echo "Installing udev rule to $RULE (needs sudo)"
  sudo install -m 644 "$SRC/70-rog-lighting.rules" "$RULE"
  sudo udevadm control --reload-rules
  sudo udevadm trigger --subsystem-match=hidraw --action=change
  sleep 1
fi

echo
/usr/bin/python3 "$DEST/rog-lighting" status
echo
echo "Done. Open \"ROG Lighting\" from your app menu."
