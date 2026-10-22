"""Small reusable dialogs: progress and quit confirmation."""

import tkinter as tk
from tkinter import ttk

import theme
from constants import APP_TITLE


def center_window(win, parent=None):
    win.update_idletasks()
    w, h = win.winfo_reqwidth(), win.winfo_reqheight()
    if parent is not None and parent.winfo_viewable():
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
    else:
        x = (win.winfo_screenwidth() - w) // 2
        y = (win.winfo_screenheight() - h) // 3
    win.geometry(f"+{max(x, 0)}+{max(y, 0)}")


def make_dialog(root, title):
    """Toplevel that works even while the main window is hidden in the tray.

    A transient child of a withdrawn window is invisible on Windows, so only
    attach it to the main window when that is visible.
    """
    win = tk.Toplevel(root)
    win.title(title)
    win.configure(background=theme.BG)
    win.resizable(False, False)
    if root.winfo_viewable():
        win.transient(root)
    return win


def _grab(win):
    try:
        win.wait_visibility()
        win.grab_set()
    except tk.TclError:
        pass
    win.focus_force()


class ProgressDialog:
    """Non-closable 'working' dialog with an indeterminate progress bar."""

    def __init__(self, root, title, message="Working..."):
        self.win = make_dialog(root, title)
        self.win.protocol("WM_DELETE_WINDOW", lambda: None)
        frame = ttk.Frame(self.win, padding=18)
        frame.pack()
        self.label = ttk.Label(frame, text=message, width=48, anchor="w")
        self.label.pack(anchor="w")
        self.bar = ttk.Progressbar(frame, mode="indeterminate", length=360)
        self.bar.pack(pady=(10, 0))
        self.bar.start(12)
        center_window(self.win, root)
        self.win.attributes("-topmost", True)

    def set_message(self, text):
        if self.win.winfo_exists():
            self.label.config(text=text)

    def close(self):
        try:
            self.bar.stop()
            self.win.destroy()
        except tk.TclError:
            pass


class QuitDialog:
    """Asks what to do with mounted images on exit. show() -> unmount | exit | cancel."""

    def __init__(self, root, records):
        self.result = "cancel"
        self.win = make_dialog(root, f"Quit {APP_TITLE}")
        self.win.protocol("WM_DELETE_WINDOW", self._cancel)
        self.win.bind("<Escape>", lambda e: self._cancel())
        frame = ttk.Frame(self.win, padding=16)
        frame.pack()
        ttk.Label(frame, text="Images are still mounted:", font=("Segoe UI", 10, "bold"),
                  foreground=theme.WARNING).pack(anchor="w")
        listing = "\n".join(f"  {r.letter}:  {r.name}" for r in records)
        ttk.Label(frame, text=listing, justify="left").pack(anchor="w", pady=(4, 10))
        ttk.Label(frame, text="Unmount them before exiting, or leave them mounted?").pack(anchor="w")
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=(14, 0))
        b = ttk.Button(row, text="Unmount all and exit", style="Accent.TButton",
                       command=lambda: self._done("unmount"))
        b.pack(side="left")
        ttk.Button(row, text="Exit immediately", style="Danger.TButton",
                   command=lambda: self._done("exit")).pack(side="left", padx=6)
        ttk.Button(row, text="Cancel", command=self._cancel).pack(side="right")
        b.focus_set()
        center_window(self.win, root)
        self.win.attributes("-topmost", True)
        self.root = root

    def _done(self, value):
        self.result = value
        self.win.destroy()

    def _cancel(self):
        self._done("cancel")

    def show(self):
        _grab(self.win)
        self.root.wait_window(self.win)
        return self.result
