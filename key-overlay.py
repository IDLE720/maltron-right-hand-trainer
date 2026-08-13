"""Always-on-top Maltron right-hand live-key overlays for Windows.

One synchronized overlay is created on every connected display. Uses only Python's
standard library and observes keys system-wide without blocking or changing them.
"""
from __future__ import annotations

import ctypes
import json
import os
import queue
import sys
import tkinter as tk
from ctypes import wintypes
from pathlib import Path

APP_DIR = Path(os.getenv("LOCALAPPDATA", Path.home())) / "RightHandQuest"
SETTINGS = APP_DIR / "overlay.json"
HOME = set("ATEH")
COLORS = {
    "bg": "#102f27", "panel": "#173a31", "key": "#294c43", "edge": "#41675c",
    "text": "#f7f8f1", "muted": "#91aaa2", "lime": "#c9f43f", "ink": "#14231f",
    "index": "#55b8d5", "middle": "#62c85d", "ring": "#efd44b",
    "little": "#ef654e", "thumb": "#d84cac",
}
FINGERS = ["index", "index", "middle", "ring", "little", "little"]


def resource_path(name):
    """Find bundled assets both from source and inside a PyInstaller EXE."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "assets" / name


user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
WH_KEYBOARD_LL, WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 13, 0x100, 0x101, 0x104, 0x105
VK_NAMES = {8:"BACKSPACE", 9:"TAB", 13:"ENTER", 16:"SHIFT", 17:"CTRL", 18:"ALT", 20:"CAPS", 27:"ESC", 32:"SPACE",
            33:"PG UP", 34:"PG DN", 35:"END", 36:"HOME", 37:"←", 38:"↑", 39:"→", 40:"↓", 45:"INSERT", 46:"DELETE",
            188:",", 190:"."}
for n in range(1, 13): VK_NAMES[111+n] = f"F{n}"

GWL_EXSTYLE, WS_EX_TOOLWINDOW, WS_EX_APPWINDOW = -20, 0x00000080, 0x00040000

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

class GUITHREADINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("hwndActive", wintypes.HWND), ("hwndFocus", wintypes.HWND),
                ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
                ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND),
                ("rcCaret", wintypes.RECT)]

LRESULT, HHOOK = ctypes.c_ssize_t, wintypes.HANDLE
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
MONITORENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                    ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
user32.SetWindowsHookExW.argtypes = (ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD)
user32.SetWindowsHookExW.restype = HHOOK
user32.CallNextHookEx.argtypes = (HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = (HHOOK,); user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.GetMonitorInfoW.argtypes = (wintypes.HMONITOR, ctypes.POINTER(MONITORINFO))
user32.GetGUIThreadInfo.argtypes = (wintypes.DWORD, ctypes.POINTER(GUITHREADINFO))
user32.GetGUIThreadInfo.restype = wintypes.BOOL
user32.ClientToScreen.argtypes = (wintypes.HWND, ctypes.POINTER(POINT))
user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetParent.argtypes = (wintypes.HWND,); user32.GetParent.restype = wintypes.HWND
user32.SetWindowPos.argtypes = (wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wintypes.UINT)
user32.SetWindowPos.restype = wintypes.BOOL
kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,); kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.GetLastError.restype = wintypes.DWORD
kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
ERROR_ALREADY_EXISTS, SW_RESTORE, HWND_TOPMOST = 183, 9, -1
SWP_NOMOVE, SWP_NOSIZE, SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x0002, 0x0001, 0x0010, 0x0040
ENUMWINDOWSPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def displays():
    """Return each monitor's work area as (left, top, right, bottom)."""
    found = []
    @MONITORENUMPROC
    def collect(handle, _dc, _rect, _data):
        info = MONITORINFO(); info.cbSize = ctypes.sizeof(info)
        if user32.GetMonitorInfoW(handle, ctypes.byref(info)):
            r = info.rcWork; found.append((r.left, r.top, r.right, r.bottom))
        return True
    user32.EnumDisplayMonitors(None, None, collect, 0)
    return sorted(found, key=lambda r: (r[0], r[1])) or [(0, 0, 1280, 720)]


class LiveWindow:
    """A visual overlay on one monitor; keyboard state comes from OverlayApp."""
    def __init__(self, app, window, monitor, index, saved=None):
        self.app, self.root, self.monitor, self.index = app, window, monitor, index
        self.keys, self.fade_jobs, self.drag_xy, self.minimized = {}, {}, None, False
        self.root.title(f"Right Hand Quest — Live Keys {index + 1}")
        self.root.configure(bg=COLORS["bg"]); self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", self.app.opacity)
        self.app.apply_icon(self.root)
        self.root.overrideredirect(True); self.root.resizable(False, False)
        self.build(); self.place(saved or {})
        # Only the first overlay owns a taskbar button. Clicking it restores
        # and raises every display's overlay.
        self.root.after(150, self.configure_taskbar_style)
        if self.index == 0:
            self.root.bind("<FocusIn>", lambda _event: self.app.restore_all())

    def build(self):
        self.header = tk.Frame(self.root, bg=COLORS["bg"], height=42, cursor="fleur",
                               highlightbackground=COLORS["edge"], highlightthickness=1)
        self.header.pack(fill="x"); self.header.pack_propagate(False)
        live = tk.Label(self.header, text="●", fg=COLORS["lime"], bg=COLORS["bg"], font=("Segoe UI", 9))
        live.pack(side="left", padx=(12, 5))
        tk.Label(self.header, text="LIVE KEYS", fg=COLORS["text"], bg=COLORS["bg"],
                 font=("Consolas", 9, "bold")).pack(side="left")
        tk.Label(self.header, text=f"  display {self.index + 1}", fg=COLORS["muted"],
                 bg=COLORS["bg"], font=("Consolas", 7)).pack(side="left")
        self.header_button("×", self.app.close)
        self.min_btn = self.header_button("−", self.toggle_minimize)
        self.opacity_btn = self.header_button(f"{round(self.app.opacity * 100)}%", self.app.cycle_opacity)
        self.opacity_btn.config(width=5)
        self.follow_btn = self.header_button("⌖", self.app.toggle_follow)
        self.update_follow_button()
        for widget in (self.header, live):
            widget.bind("<ButtonPress-1>", self.drag_start)
            widget.bind("<B1-Motion>", self.drag_move)
            widget.bind("<ButtonRelease-1>", self.drag_end)

        self.body = tk.Frame(self.root, bg=COLORS["panel"], padx=12, pady=10,
                             highlightbackground=COLORS["edge"], highlightthickness=1)
        self.body.pack(fill="both")
        readout = tk.Frame(self.body, bg=COLORS["panel"]); readout.pack(fill="x", pady=(0, 8))
        left = tk.Frame(readout, bg=COLORS["panel"]); left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text="YOU PRESSED", fg=COLORS["muted"], bg=COLORS["panel"],
                 font=("Consolas", 7)).pack(anchor="w")
        self.history_label = tk.Label(left, text="Waiting for a key…", fg=COLORS["text"],
                                      bg=COLORS["panel"], font=("Consolas", 8), anchor="w", width=30)
        self.history_label.pack(anchor="w")
        self.current = tk.Label(readout, text="—", fg=COLORS["lime"], bg=COLORS["panel"],
                                font=("Segoe UI", 19, "bold"), width=10, anchor="e")
        self.current.pack(side="right")

        typed_panel = tk.Frame(self.body, bg=COLORS["bg"], padx=9, pady=7,
                               highlightbackground=COLORS["edge"], highlightthickness=1)
        typed_panel.pack(fill="x", pady=(0, 10))
        tk.Label(typed_panel, text="TYPED TEXT", fg=COLORS["muted"], bg=COLORS["bg"],
                 font=("Consolas", 7)).pack(anchor="w")
        self.typed_preview = tk.Text(typed_panel, fg=COLORS["text"], bg=COLORS["bg"],
                                     insertbackground=COLORS["lime"], font=("Consolas", 10),
                                     width=62, height=3, wrap="word", bd=0, padx=0, pady=0,
                                     takefocus=False, cursor="arrow")
        self.typed_preview.insert("1.0", "Your typing will appear here…")
        self.typed_preview.config(state="disabled")
        self.typed_preview.pack(fill="x", anchor="w")

        board = tk.Frame(self.body, bg=COLORS["panel"]); board.pack()
        thumb_board = tk.Frame(board, bg=COLORS["panel"]); thumb_board.grid(row=0, column=0, sticky="se", padx=(0, 4))
        letter_board = tk.Frame(board, bg=COLORS["panel"]); letter_board.grid(row=0, column=1, sticky="n")
        for r, row in enumerate(["XGMPBQ", "JFDOLR", "SATEHN", "ZYCKWV"]):
            for c, char in enumerate(row): self.make_key(letter_board, char, r, c, FINGERS[c], char in HOME)
        self.make_key(thumb_board, "BACKSPACE", 2, 3, "thumb", width=8)
        self.make_key(thumb_board, "ENTER", 3, 2, "thumb", width=7)
        self.make_key(thumb_board, "I", 3, 3, "thumb")
        self.make_key(thumb_board, "SHIFT", 4, 1, "thumb", width=7)
        self.make_key(thumb_board, "U", 4, 2, "thumb")
        space = self.make_key(thumb_board, "SPACE", 4, 3, "thumb", True, width=8)
        space.grid(row=4, column=3, rowspan=2, sticky="nsew", padx=2, pady=2)
        self.make_key(thumb_board, ",", 5, 1, "thumb"); self.make_key(thumb_board, ".", 5, 2, "thumb")
        tk.Label(self.body, text="One synchronized overlay on every display",
                 fg=COLORS["muted"], bg=COLORS["panel"], font=("Consolas", 7)).pack(pady=(8, 0))

    def update_follow_button(self):
        active = self.app.auto_follow
        self.follow_btn.config(fg=COLORS["lime"] if active else COLORS["muted"],
                               text="⌖" if active else "○")

    def snap_near(self, x, y):
        """Restore and place this overlay near, but not over, the active caret."""
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        l, t, r, b = self.monitor
        margin, gap = 12, 24
        target_x = x + gap
        if target_x + w > r - margin: target_x = x - w - gap
        target_x = max(l + margin, min(target_x, r - w - margin))
        target_y = y + gap
        if target_y + h > b - margin: target_y = y - h - gap
        target_y = max(t + margin, min(target_y, b - h - margin))
        self.root.geometry(f"{target_x:+d}{target_y:+d}")
        self.root.update_idletasks()
        # Reposition without taking keyboard focus away from the text field.
        hwnd = self.root.winfo_id()
        parent = user32.GetParent(hwnd)
        if parent: hwnd = parent
        user32.SetWindowPos(hwnd, HWND_TOPMOST, target_x, target_y, w, h,
                            SWP_NOACTIVATE | SWP_SHOWWINDOW)

    def configure_taskbar_style(self):
        try:
            hwnd = self.root.winfo_id()
            parent = user32.GetParent(hwnd)
            if parent: hwnd = parent
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if self.index == 0:
                style = (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
            else:
                style = (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            self.root.withdraw(); self.root.after(20, self.root.deiconify)
        except Exception:
            pass

    def header_button(self, text, command):
        b = tk.Button(self.header, text=text, command=command, fg=COLORS["text"], bg=COLORS["bg"],
                      activebackground=COLORS["edge"], activeforeground="white", bd=0, width=3,
                      font=("Segoe UI", 12), cursor="hand2")
        b.pack(side="right", fill="y"); return b

    def make_key(self, parent, char, row, col, finger, home=False, width=5):
        outer = tk.Frame(parent, bg=COLORS[finger], padx=1, pady=1)
        outer.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
        label = tk.Label(outer, text=char, width=width, height=1,
                         bg="#365746" if home else COLORS["key"], fg=COLORS["text"],
                         font=("Consolas", 10, "bold"), padx=1, pady=5)
        label.pack(fill="both", expand=True); self.keys[char] = label
        return outer

    def place(self, saved):
        self.root.update_idletasks(); w, h = self.root.winfo_reqwidth(), self.root.winfo_reqheight()
        l, t, r, b = self.monitor
        if "x" in saved and "y" in saved:
            x, y = int(saved["x"]), int(saved["y"])
            if not (l <= x < r and t <= y < b): x, y = r-w-18, b-h-18
        else: x, y = r-w-18, b-h-18
        self.root.geometry(f"{x:+d}{y:+d}")
        # Always start visible. Minimized state is intentionally not restored,
        # so relaunching can never appear to do nothing.

    @staticmethod
    def blend_color(start, end, amount):
        """Blend two #RRGGBB colors by an amount from zero to one."""
        a = tuple(int(start[i:i+2], 16) for i in (1, 3, 5))
        b = tuple(int(end[i:i+2], 16) for i in (1, 3, 5))
        mixed = tuple(round(x + (y - x) * amount) for x, y in zip(a, b))
        return "#" + "".join(f"{value:02x}" for value in mixed)

    def fade_key(self, label):
        key = self.keys.get(label)
        if not key: return
        resting = "#365746" if label in HOME or label == "SPACE" else COLORS["key"]
        old_job = self.fade_jobs.pop(label, None)
        if old_job:
            try: self.root.after_cancel(old_job)
            except Exception: pass
        steps, duration = 12, 1100
        def step(number=1):
            amount = number / steps
            key.config(bg=self.blend_color(COLORS["lime"], resting, amount),
                       fg=self.blend_color(COLORS["ink"], COLORS["text"], amount))
            if number < steps:
                self.fade_jobs[label] = self.root.after(duration // steps, step, number + 1)
            else:
                self.fade_jobs.pop(label, None)
        # Hold the highlight briefly, then fade it smoothly.
        self.fade_jobs[label] = self.root.after(260, step)

    def show_key(self, label, down, history, typed_text):
        if down:
            self.current.config(text=label); self.history_label.config(text=" · ".join(history))
            self.typed_preview.config(state="normal")
            self.typed_preview.delete("1.0", "end")
            self.typed_preview.insert("1.0", typed_text or "Your typing will appear here…")
            self.typed_preview.see("end")
            self.typed_preview.config(state="disabled")
        key = self.keys.get(label)
        if key:
            if down:
                old_job = self.fade_jobs.pop(label, None)
                if old_job:
                    try: self.root.after_cancel(old_job)
                    except Exception: pass
                key.config(bg=COLORS["lime"], fg=COLORS["ink"])
            else:
                self.fade_key(label)

    def toggle_minimize(self, save=True):
        self.minimized = not self.minimized
        if self.minimized: self.body.pack_forget(); self.min_btn.config(text="+")
        else: self.body.pack(fill="both"); self.min_btn.config(text="−")
        if save: self.app.save_settings()

    def drag_start(self, event): self.drag_xy = (event.x_root-self.root.winfo_x(), event.y_root-self.root.winfo_y())
    def drag_move(self, event):
        if self.drag_xy: self.root.geometry(f"{event.x_root-self.drag_xy[0]:+d}{event.y_root-self.drag_xy[1]:+d}")
    def drag_end(self, _event):
        self.drag_xy = None
        # A manual move pins the overlays until the target button is re-enabled.
        if self.app.auto_follow: self.app.set_follow(False)
        self.app.save_settings()
    def state(self): return {"x": self.root.winfo_x(), "y": self.root.winfo_y()}


class OverlayApp:
    def __init__(self, mutex=None):
        self.mutex = mutex
        try: user32.SetProcessDPIAware()
        except Exception: pass
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("RightHandQuest.LiveKeys")
        except Exception: pass
        self.root = tk.Tk(); self.root.withdraw()
        self.icon_image = None
        self.apply_icon(self.root)
        self.events: queue.Queue[tuple[str, bool]] = queue.Queue()
        self.history, self.typed_text, self.held = [], "", set()
        self.clear_text_job = None
        self.caps_lock = bool(user32.GetKeyState(20) & 1)
        self.hook, self.windows = None, []
        settings = self.load_settings(); saved_windows = settings.get("windows", [])
        self.auto_follow = settings.get("auto_follow", True)
        self.opacity = float(settings.get("opacity", 0.82))
        self.opacity = max(0.55, min(1.0, self.opacity))
        self.mouse_was_down, self.last_caret = False, None
        self.monitor_areas = displays()
        for i, monitor in enumerate(self.monitor_areas):
            window = tk.Toplevel(self.root)
            saved = saved_windows[i] if i < len(saved_windows) else {}
            self.windows.append(LiveWindow(self, window, monitor, i, saved))
        self.install_hook(); self.root.after(15, self.drain_events)
        self.root.after(100, self.watch_typing_focus)

    def apply_icon(self, window):
        try:
            if self.icon_image is None:
                self.icon_image = tk.PhotoImage(file=str(resource_path("right-hand-quest.png")))
            window.iconphoto(True, self.icon_image)
        except Exception:
            pass

    def restore_all(self):
        """Bring every overlay back when the taskbar button is selected."""
        for window in self.windows:
            window.root.deiconify()
            window.root.attributes("-topmost", True)
            window.root.lift()
        if self.windows:
            self.windows[0].root.after(250, lambda: self.windows[0].root.attributes("-topmost", True))

    @staticmethod
    def load_settings():
        try: return json.loads(SETTINGS.read_text(encoding="utf-8"))
        except Exception: return {}

    def save_settings(self):
        APP_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS.write_text(json.dumps({"windows": [w.state() for w in self.windows],
                                        "auto_follow": self.auto_follow,
                                        "opacity": self.opacity}), encoding="utf-8")

    def cycle_opacity(self):
        """Cycle through translucent, lighter, and fully opaque modes."""
        levels = (0.82, 0.65, 1.0)
        current = min(range(len(levels)), key=lambda i: abs(levels[i] - self.opacity))
        self.opacity = levels[(current + 1) % len(levels)]
        for window in self.windows:
            window.root.attributes("-alpha", self.opacity)
            window.opacity_btn.config(text=f"{round(self.opacity * 100)}%", width=5)
        self.save_settings()

    def set_follow(self, enabled):
        self.auto_follow = enabled
        for window in self.windows: window.update_follow_button()
        self.save_settings()
        if enabled: self.snap_to_caret(force=True)

    def toggle_follow(self): self.set_follow(not self.auto_follow)

    def caret_position(self):
        """Return the focused application's caret in screen coordinates."""
        hwnd = user32.GetForegroundWindow()
        if not hwnd: return None
        pid = wintypes.DWORD()
        thread = user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == os.getpid(): return None
        info = GUITHREADINFO(); info.cbSize = ctypes.sizeof(info)
        if not user32.GetGUIThreadInfo(thread, ctypes.byref(info)) or not info.hwndCaret:
            return None
        point = POINT(info.rcCaret.left, info.rcCaret.bottom)
        if not user32.ClientToScreen(info.hwndCaret, ctypes.byref(point)): return None
        return point.x, point.y, int(info.hwndFocus or info.hwndCaret)

    def snap_to_caret(self, force=False):
        if not self.auto_follow: return
        caret = self.caret_position()
        if not caret: return
        x, y, hwnd = caret
        signature = (hwnd, y)
        if not force and signature == self.last_caret: return
        self.last_caret = signature
        for window in self.windows:
            l, t, r, b = window.monitor
            if l <= x < r and t <= y < b:
                window.snap_near(x, y); self.save_settings(); break

    def watch_typing_focus(self):
        """Snap after a text-field click or a meaningful caret/focus change."""
        down = bool(user32.GetAsyncKeyState(0x01) & 0x8000)
        if self.mouse_was_down and not down:
            self.root.after(120, lambda: self.snap_to_caret(force=True))
        self.mouse_was_down = down
        self.snap_to_caret()
        self.root.after(100, self.watch_typing_focus)

    def install_hook(self):
        @HOOKPROC
        def callback(code, msg, data):
            if code >= 0 and msg in (WM_KEYDOWN, WM_SYSKEYDOWN, WM_KEYUP, WM_SYSKEYUP):
                vk = ctypes.cast(data, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents.vkCode
                self.events.put((self.vk_label(vk), msg in (WM_KEYDOWN, WM_SYSKEYDOWN)))
            return user32.CallNextHookEx(self.hook, code, msg, data)
        self.callback = callback
        self.hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, callback, kernel32.GetModuleHandleW(None), 0)
        if not self.hook: raise ctypes.WinError()

    @staticmethod
    def vk_label(vk):
        if 65 <= vk <= 90 or 48 <= vk <= 57: return chr(vk)
        return VK_NAMES.get(vk, f"VK {vk}")

    def clear_typed_text(self):
        self.typed_text = ""
        self.clear_text_job = None
        for window in self.windows:
            window.typed_preview.config(state="normal")
            window.typed_preview.delete("1.0", "end")
            window.typed_preview.config(state="disabled")

    def schedule_text_clear(self):
        if self.clear_text_job is not None:
            self.root.after_cancel(self.clear_text_job)
        self.clear_text_job = self.root.after(60_000, self.clear_typed_text)

    def update_typed_text(self, label):
        """Build a short, in-memory typing preview; nothing is written to disk."""
        if label == "BACKSPACE": self.typed_text = self.typed_text[:-1]
        elif label == "ENTER": self.typed_text += "\n"
        elif label == "SPACE": self.typed_text += " "
        elif label == "TAB": self.typed_text += "    "
        elif label in (",", "."): self.typed_text += label
        elif len(label) == 1 and label.isalnum() and not ({"CTRL", "ALT"} & self.held):
            if label.isalpha():
                upper = ("SHIFT" in self.held) ^ self.caps_lock
                self.typed_text += label.upper() if upper else label.lower()
            else: self.typed_text += label
        # Keep enough context while ensuring the newest text remains visible.
        self.typed_text = self.typed_text[-2000:]

    def drain_events(self):
        try:
            while True:
                label, down = self.events.get_nowait()
                if down:
                    if label == "CAPS" and label not in self.held: self.caps_lock = not self.caps_lock
                    if label in ("SHIFT", "CTRL", "ALT", "CAPS"): self.held.add(label)
                    self.update_typed_text(label)
                    self.schedule_text_clear()
                    if not self.history or self.history[-1] != label:
                        self.history.append(label); self.history = self.history[-6:]
                elif label in ("SHIFT", "CTRL", "ALT", "CAPS"):
                    self.held.discard(label)
                for window in self.windows:
                    window.show_key(label, down, self.history, self.typed_text)
        except queue.Empty: pass
        self.root.after(15, self.drain_events)

    def close(self):
        self.save_settings()
        if self.hook: user32.UnhookWindowsHookEx(self.hook)
        if self.mutex: kernel32.CloseHandle(self.mutex); self.mutex = None
        self.root.destroy()

    def run(self): self.root.mainloop()


def restore_running_copy():
    """Raise all windows from the existing instance when the EXE is opened again."""
    found = []
    @ENUMWINDOWSPROC
    def visit(hwnd, _data):
        length = user32.GetWindowTextLengthW(hwnd)
        if length:
            title = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, title, length + 1)
            if title.value.startswith("Right Hand Quest — Live Keys") or title.value.startswith("Right Hand Quest - Live Keys"):
                user32.ShowWindow(hwnd, SW_RESTORE)
                user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                     SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                found.append(hwnd)
        return True
    user32.EnumWindows(visit, 0)
    if not found:
        user32.MessageBoxW(None, "Right Hand Quest is already running. Check its taskbar icon.",
                           "Right Hand Quest", 0x40)


if __name__ == "__main__":
    mutex = kernel32.CreateMutexW(None, False, "Local\\RightHandQuestLiveKeys")
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        restore_running_copy()
        if mutex: kernel32.CloseHandle(mutex)
    else:
        try: OverlayApp(mutex).run()
        except Exception as exc:
            if mutex: kernel32.CloseHandle(mutex)
            try: user32.MessageBoxW(None, f"The key overlay could not start.\n\n{exc}", "Right Hand Quest", 0x10)
            finally: raise
