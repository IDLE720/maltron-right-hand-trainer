# Right Hand Quest

## Browser game

The trainer procedurally generates a fresh exercise for every round. Later rounds adapt by weighting words containing keys missed earlier in the mission. Use **New sequence** at any time to generate another exercise.

From this folder, run:

```text
python -m http.server 8765
```

Then visit `http://localhost:8765`.

## Standalone live-key overlay

### macOS

Download `RightHandQuestMacOverlay-macOS.zip` from the latest release, unzip it, and move the app to **Applications**. On first launch:

1. Control-click the app and choose **Open** (the community build is not Apple-notarized).
2. Allow the app in **System Settings → Privacy & Security → Accessibility**.
3. Allow it in **Privacy & Security → Input Monitoring**.
4. Quit and reopen the app after granting permissions.

The macOS version provides the same live layout, Shift highlighting, click-following overlay, typed preview, transparency control, and **▶** training-game launcher. To run from source, make `Start Key Overlay macOS.command` executable (`chmod +x`) and open it. Build a `.app` locally with `./build-macos.sh`.

### Windows

#### Ready-to-run EXE

Download **RightHandQuestOverlay.exe** from the repository's latest GitHub release and double-click it. It is a portable application and does not require Python or installation. Windows may show a SmartScreen warning because the file is not code-signed; use **More info → Run anyway** if you trust the download.

#### Run from source

Double-click **Start Key Overlay.bat**. The overlay:

- uses one always-on-top overlay that follows where typing actually begins;
- remembers clicks without moving, then snaps beside the active caret—or clicked text field—when a typing key confirms text entry;
- opens the browser training game from the **▶** button;
- uses a semi-transparent window so work beneath the keyboard remains visible;
- provides an opacity button to cycle between **82%**, **65%**, and **100%**;
- provides a target button to turn automatic following on or off (dragging an overlay pins it in place);
- provides a taskbar icon that restores and raises the overlays if one disappears behind another window;
- prevents duplicate background copies—opening the EXE again restores the running overlays;
- observes keys system-wide without blocking them;
- includes the Shift key beside U and highlights pressed Maltron keys before gradually fading the glow;
- shows a recent, in-memory preview above the layout and clears it after one minute without typing;
- displays other keys in the live readout;
- can be dragged to pin it in place or minimized;
- closes with **×**; and
- remembers its position.

No installation or third-party Python packages are required when running from source. Windows may prevent global key monitoring over elevated/administrator applications unless the overlay is also started with equivalent privileges.

#### Build the EXE

Double-click **build-exe.bat**. The resulting portable executable will be written to `dist/RightHandQuestOverlay.exe`. The script installs PyInstaller if it is unavailable.
