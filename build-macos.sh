#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m pip install --upgrade pyinstaller pynput
rm -rf build dist RightHandQuestMacOverlay.spec assets/AppIcon.iconset assets/right-hand-quest.icns
mkdir -p assets/AppIcon.iconset
for size in 16 32 128 256 512; do
  sips -z "$size" "$size" assets/right-hand-quest.png --out "assets/AppIcon.iconset/icon_${size}x${size}.png" >/dev/null
  double=$((size*2)); sips -z "$double" "$double" assets/right-hand-quest.png --out "assets/AppIcon.iconset/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns assets/AppIcon.iconset -o assets/right-hand-quest.icns
python3 -m PyInstaller --noconfirm --clean --windowed --name RightHandQuestMacOverlay \
  --icon assets/right-hand-quest.icns --add-data "assets/right-hand-quest.png:assets" key-overlay-macos.py
 ditto -c -k --sequesterRsrc --keepParent dist/RightHandQuestMacOverlay.app dist/RightHandQuestMacOverlay-macOS.zip
echo "Built dist/RightHandQuestMacOverlay-macOS.zip"
