#!/bin/bash
cd "$(dirname "$0")"
if ! python3 -c "import pynput" >/dev/null 2>&1; then
  python3 -m pip install --user pynput || { echo "Could not install pynput."; read -r; exit 1; }
fi
python3 key-overlay-macos.py
