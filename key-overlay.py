"""Standalone, always-on-top Maltron right-hand keyboard overlay for Windows.

Uses only Python's standard library. A low-level Windows keyboard hook observes keys
system-wide without blocking or changing them.
"""
from __future__ import annotations

import ctypes
import json
import os
import queue
import string
import tkinter as tk
from ctypes import wintypes
from pathlib import Path

APP_DIR = Path(os.getenv("LOCALAPPDATA", Path.home())) / "RightHandQuest"
SETTINGS = APP_DIR / "overlay.json"
ROWS = ["XGMPBQ", "JFDOLR"]
HOME = set("ATEH")
COLORS = {
    "bg": "#102f27", "panel": "#173a31", "key": "#294c43", "edge": "#41675c",
    "text": "#f7f8f1", "muted": "#91aaa2", "lime": "#c9f43f", "ink": "#14231f",
    "index": "#55b8d5", "middle": "#62c85d", "ring": "#efd44b",
    "little": "#ef654e", "thumb": "#d84cac",
}
FINGERS = ["index", "index", "middle", "ring", "little", "little"]

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
WH_KEYBOARD_LL, WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 13, 0x100, 0x101, 0x104, 0x105
VK_NAMES = {8:"BACKSPACE", 9:"TAB", 13:"ENTER", 16:"SHIFT", 17:"CTRL", 18:"ALT", 20:"CAPS", 27:"ESC", 32:"SPACE",
            33:"PG UP", 34:"PG DN", 35:"END", 36:"HOME", 37:"←", 38:"↑", 39:"→", 40:"↓", 45:"INSERT", 46:"DELETE",
            188:",", 190:"."}
for n in range(1, 13): VK_NAMES[111+n] = f"F{n}"

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD),
                ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

LRESULT = ctypes.c_ssize_t
HHOOK = wintypes.HANDLE
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
user32.SetWindowsHookExW.argtypes = (ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD)
user32.SetWindowsHookExW.restype = HHOOK
user32.CallNextHookEx.argtypes = (HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = (HHOOK,)
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
kernel32.GetModuleHandleW.restype = wintypes.HMODULE

class Overlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Right Hand Quest — Live Keys")
        self.root.configure(bg=COLORS["bg"])
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)
        self.root.resizable(False, False)
        self.events: queue.Queue[tuple[str, bool]] = queue.Queue()
        self.keys: dict[str, tk.Label] = {}
        self.history: list[str] = []
        self.minimized = False
        self.hook = None
        self.drag_xy = None
        self.settings = self.load_settings()
        self.build()
        self.place_window()
        self.install_hook()
        self.root.after(15, self.drain_events)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def load_settings(self):
        try: return json.loads(SETTINGS.read_text(encoding="utf-8"))
        except Exception: return {}

    def save_settings(self):
        APP_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS.write_text(json.dumps({"x": self.root.winfo_x(), "y": self.root.winfo_y(), "minimized": self.minimized}), encoding="utf-8")

    def build(self):
        self.header = tk.Frame(self.root, bg=COLORS["bg"], height=42, cursor="fleur", highlightbackground=COLORS["edge"], highlightthickness=1)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)
        live = tk.Label(self.header, text="●", fg=COLORS["lime"], bg=COLORS["bg"], font=("Segoe UI", 9))
        live.pack(side="left", padx=(12, 5))
        tk.Label(self.header, text="LIVE KEYS", fg=COLORS["text"], bg=COLORS["bg"], font=("Consolas", 9, "bold")).pack(side="left")
        tk.Label(self.header, text="  system-wide", fg=COLORS["muted"], bg=COLORS["bg"], font=("Consolas", 7)).pack(side="left")
        self.close_btn = self.header_button("×", self.close)
        self.min_btn = self.header_button("−", self.toggle_minimize)
        for widget in (self.header, live):
            widget.bind("<ButtonPress-1>", self.drag_start); widget.bind("<B1-Motion>", self.drag_move); widget.bind("<ButtonRelease-1>", self.drag_end)

        self.body = tk.Frame(self.root, bg=COLORS["panel"], padx=12, pady=10, highlightbackground=COLORS["edge"], highlightthickness=1)
        self.body.pack(fill="both")
        readout = tk.Frame(self.body, bg=COLORS["panel"]); readout.pack(fill="x", pady=(0, 8))
        left = tk.Frame(readout, bg=COLORS["panel"]); left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text="YOU PRESSED", fg=COLORS["muted"], bg=COLORS["panel"], font=("Consolas", 7)).pack(anchor="w")
        self.history_label = tk.Label(left, text="Waiting for a key…", fg=COLORS["text"], bg=COLORS["panel"], font=("Consolas", 8), anchor="w", width=30)
        self.history_label.pack(anchor="w")
        self.current = tk.Label(readout, text="—", fg=COLORS["lime"], bg=COLORS["panel"], font=("Segoe UI", 19, "bold"), width=10, anchor="e")
        self.current.pack(side="right")
        board = tk.Frame(self.body, bg=COLORS["panel"]); board.pack()
        thumb_board = tk.Frame(board, bg=COLORS["panel"])
        thumb_board.grid(row=0, column=0, sticky="se", padx=(0, 4))
        letter_board = tk.Frame(board, bg=COLORS["panel"])
        letter_board.grid(row=0, column=1, sticky="n")

        # Keep the six letter columns independent from the thumb cluster so
        # the first blue column is always X, J, S, Z.
        letter_rows = ["XGMPBQ", "JFDOLR", "SATEHN", "ZYCKWV"]
        for r, row in enumerate(letter_rows):
            for c, char in enumerate(row):
                self.make_key(letter_board, char, r, c, FINGERS[c], char in HOME)

        # Move the complete purple thumb cluster one column to the right.
        # Space is two rows tall under I; U is under Enter and left of Space.
        self.make_key(thumb_board, "BACKSPACE", 2, 3, "thumb", width=8)
        self.make_key(thumb_board, "ENTER", 3, 2, "thumb", width=7)
        self.make_key(thumb_board, "I", 3, 3, "thumb")
        self.make_key(thumb_board, "U", 4, 2, "thumb")
        space = self.make_key(thumb_board, "SPACE", 4, 3, "thumb", True, width=8)
        space.grid(row=4, column=3, rowspan=2, sticky="nsew", padx=2, pady=2)
        self.make_key(thumb_board, ",", 5, 1, "thumb")
        self.make_key(thumb_board, ".", 5, 2, "thumb")
        tk.Label(self.body, text="Drag the title bar • − minimizes • × closes", fg=COLORS["muted"], bg=COLORS["panel"], font=("Consolas", 7)).pack(pady=(8, 0))

    def header_button(self, text, command):
        b = tk.Button(self.header, text=text, command=command, fg=COLORS["text"], bg=COLORS["bg"], activebackground=COLORS["edge"], activeforeground="white", bd=0, width=3, font=("Segoe UI", 12), cursor="hand2")
        b.pack(side="right", fill="y"); return b

    def make_key(self, parent, char, row, col, finger, home=False, width=5):
        outer = tk.Frame(parent, bg=COLORS[finger], padx=1, pady=1)
        outer.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
        label = tk.Label(outer, text=char, width=width, height=1, bg="#365746" if home else COLORS["key"], fg=COLORS["text"], font=("Consolas", 10, "bold"), padx=1, pady=5)
        label.pack(fill="both", expand=True)
        self.keys[char] = label
        return outer

    def place_window(self):
        self.root.update_idletasks(); w, h = self.root.winfo_reqwidth(), self.root.winfo_reqheight()
        x = int(self.settings.get("x", self.root.winfo_screenwidth()-w-25)); y = int(self.settings.get("y", self.root.winfo_screenheight()-h-75))
        x=max(0,min(x,self.root.winfo_screenwidth()-w)); y=max(0,min(y,self.root.winfo_screenheight()-h))
        self.root.geometry(f"+{x}+{y}")
        if self.settings.get("minimized"): self.toggle_minimize()

    def install_hook(self):
        @HOOKPROC
        def callback(code, msg, data):
            if code >= 0 and msg in (WM_KEYDOWN, WM_SYSKEYDOWN, WM_KEYUP, WM_SYSKEYUP):
                vk = ctypes.cast(data, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents.vkCode
                label = self.vk_label(vk)
                self.events.put((label, msg in (WM_KEYDOWN, WM_SYSKEYDOWN)))
            return user32.CallNextHookEx(self.hook, code, msg, data)
        self.callback = callback
        self.hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, callback, kernel32.GetModuleHandleW(None), 0)
        if not self.hook: raise ctypes.WinError()

    @staticmethod
    def vk_label(vk):
        if 65 <= vk <= 90: return chr(vk)
        if 48 <= vk <= 57: return chr(vk)
        return VK_NAMES.get(vk, f"VK {vk}")

    def drain_events(self):
        try:
            while True:
                label, down = self.events.get_nowait()
                if down:
                    self.current.config(text=label)
                    if not self.history or self.history[-1] != label:
                        self.history.append(label); self.history = self.history[-6:]
                    self.history_label.config(text=" · ".join(self.history))
                key = self.keys.get(label)
                if key: key.config(bg=COLORS["lime"] if down else ("#365746" if label in HOME or label == "SPACE" else COLORS["key"]), fg=COLORS["ink"] if down else COLORS["text"])
        except queue.Empty: pass
        self.root.after(15, self.drain_events)

    def toggle_minimize(self):
        self.minimized = not self.minimized
        if self.minimized: self.body.pack_forget(); self.min_btn.config(text="+")
        else: self.body.pack(fill="both"); self.min_btn.config(text="−")
        self.save_settings()

    def drag_start(self, event): self.drag_xy = (event.x_root-self.root.winfo_x(), event.y_root-self.root.winfo_y())
    def drag_move(self, event):
        if self.drag_xy: self.root.geometry(f"+{event.x_root-self.drag_xy[0]}+{event.y_root-self.drag_xy[1]}")
    def drag_end(self, _event): self.drag_xy=None; self.save_settings()

    def close(self):
        self.save_settings()
        if self.hook: user32.UnhookWindowsHookEx(self.hook)
        self.root.destroy()

    def run(self): self.root.mainloop()

if __name__ == "__main__":
    try:
        Overlay().run()
    except Exception as exc:
        # pythonw has no console, so make startup failures visible to the user.
        try:
            ctypes.windll.user32.MessageBoxW(None, f"The key overlay could not start.\n\n{exc}", "Right Hand Quest", 0x10)
        finally:
            raise
