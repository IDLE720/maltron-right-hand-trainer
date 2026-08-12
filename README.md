# Right Hand Quest

## Browser game

From this folder, run:

```text
python -m http.server 8765
```

Then visit `http://localhost:8765`.

## Standalone live-key overlay (Windows)

### Ready-to-run EXE

Download **RightHandQuestOverlay.exe** from the repository's latest GitHub release and double-click it. It is a portable application and does not require Python or installation. Windows may show a SmartScreen warning because the file is not code-signed; use **More info → Run anyway** if you trust the download.

### Run from source

Double-click **Start Key Overlay.bat**. The overlay:

- creates a synchronized, always-on-top overlay on every connected display;
- observes keys system-wide without blocking them;
- highlights Maltron letter and Space keys;
- shows a recent, in-memory preview above the layout and clears it after one minute without typing;
- displays other keys in the live readout;
- lets each display's overlay be dragged or minimized independently;
- closes all overlays with **×**; and
- remembers each overlay's position.

No installation or third-party Python packages are required when running from source. Windows may prevent global key monitoring over elevated/administrator applications unless the overlay is also started with equivalent privileges.

### Build the EXE

Double-click **build-exe.bat**. The resulting portable executable will be written to `dist/RightHandQuestOverlay.exe`. The script installs PyInstaller if it is unavailable.
