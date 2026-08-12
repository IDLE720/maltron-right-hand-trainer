# Right Hand Quest

## Browser game

From this folder, run:

```text
python -m http.server 8765
```

Then visit `http://localhost:8765`.

## Standalone live-key overlay (Windows)

Double-click **Start Key Overlay.bat**. The overlay:

- creates a synchronized, always-on-top overlay on every connected display;
- observes keys system-wide without blocking them;
- highlights Maltron letter and Space keys;
- displays other keys in the live readout;
- lets each display's overlay be dragged or minimized independently;
- closes all overlays with **×**; and
- remembers each overlay's position.

No installation or third-party Python packages are required. Windows may prevent global key monitoring over elevated/administrator applications unless the overlay is also started with equivalent privileges.
