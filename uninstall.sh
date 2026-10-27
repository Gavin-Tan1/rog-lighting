#!/usr/bin/env bash
set -uo pipefail

APP_ID=io.github.Gavin_Tan1.RogLighting

pkill -u "$(id -u)" -f "rog-lighting\"? daemon" 2>/dev/null
cd "$HOME"
rm -rf "$HOME/.local/share/rog-lighting" "$HOME/.config/rog-lighting"
rm -f "$HOME/.local/share/applications/$APP_ID.desktop" \
      "$HOME/.local/share/icons/hicolor/scalable/apps/$APP_ID.svg" \
      "$HOME/.config/autostart/rog-lighting-daemon.desktop"

if [ -f /etc/udev/rules.d/70-rog-lighting.rules ]; then
  echo "Removing udev rule (needs sudo)"
  sudo rm -f /etc/udev/rules.d/70-rog-lighting.rules
  sudo udevadm control --reload-rules
  sudo udevadm trigger --subsystem-match=hidraw --action=change
fi
echo "Uninstalled."
