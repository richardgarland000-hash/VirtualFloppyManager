"""Configuration dialog; values persist in the JSON settings file."""

import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import theme
from dialogs import center_window, make_dialog


class SettingsDialog:
    def __init__(self, root, app):
        self.app = app
        cfg = app.config
        self.win = make_dialog(root, "Settings")
        frm = ttk.Frame(self.win, padding=14)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)

        self.v_imdisk = tk.StringVar(value=cfg.get("imdisk_path"))
        self.v_exts = tk.StringVar(value=" ".join(cfg.get("allowed_extensions")))
        self.v_refresh = tk.StringVar(value=str(cfg.get("refresh_seconds")))
        self.v_log = tk.StringVar(value=cfg.get("log_level"))
        self.v_ro = tk.BooleanVar(value=cfg.get("read_only"))
        self.v_rem = tk.BooleanVar(value=cfg.get("removable_media"))
        self.v_explorer = tk.BooleanVar(value=cfg.get("open_explorer_after_mount"))
        self.v_elevate = tk.BooleanVar(value=cfg.get("auto_elevate"))
        self.v_hidden = tk.BooleanVar(value=cfg.get("start_hidden"))
        self.v_close = tk.BooleanVar(value=cfg.get("close_button_hides"))

        ttk.Label(frm, text="ImDisk executable:").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Entry(frm, textvariable=self.v_imdisk, width=46).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(frm, text="Browse...", style="Accent.TButton", command=self._browse).grid(row=0, column=2)
        found = app.backend.locate()
        ttk.Label(frm, text=f"Detected: {found}" if found else "Detected: not found (blank = auto-detect)",
                  foreground=theme.MUTED).grid(row=1, column=1, columnspan=2, sticky="w", padx=6)

        ttk.Label(frm, text="Allowed extensions:").grid(row=2, column=0, sticky="w", pady=3)
        ttk.Entry(frm, textvariable=self.v_exts).grid(row=2, column=1, columnspan=2, sticky="ew", padx=6)
        ttk.Label(frm, text="Refresh interval (s):").grid(row=3, column=0, sticky="w", pady=3)
        ttk.Spinbox(frm, from_=1, to=300, width=6, textvariable=self.v_refresh).grid(row=3, column=1, sticky="w", padx=6)
        ttk.Label(frm, text="Log level:").grid(row=4, column=0, sticky="w", pady=3)
        ttk.Combobox(frm, textvariable=self.v_log, state="readonly", width=10,
                     values=["DEBUG", "INFO", "WARNING", "ERROR"]).grid(row=4, column=1, sticky="w", padx=6)

        opts = [("Prompt for administrator approval when an operation is denied", self.v_elevate),
                ("Mount read-only", self.v_ro), ("Present as removable media", self.v_rem),
                ("Open the drive in Explorer after mounting", self.v_explorer),
                ("Start hidden in the system tray", self.v_hidden),
                ("Close button hides the window instead of quitting", self.v_close)]
        for i, (text, var) in enumerate(opts):
            ttk.Checkbutton(frm, text=text, variable=var).grid(row=5 + i, column=0, columnspan=3, sticky="w")

        row = ttk.Frame(frm)
        row.grid(row=12, column=0, columnspan=3, sticky="ew", pady=(14, 0))
        ttk.Button(row, text="Clear image history", command=self._clear_history).pack(side="left")
        ttk.Button(row, text="Restart as administrator", style="Warning.TButton",
                   command=self._restart_admin).pack(side="left", padx=6)
        ttk.Button(row, text="Cancel", command=self.win.destroy).pack(side="right")
        ttk.Button(row, text="Save", style="Accent.TButton", command=self._save).pack(side="right", padx=6)

        self.win.bind("<Escape>", lambda e: self.win.destroy())
        center_window(self.win, root)

    def alive(self):
        try:
            return bool(self.win.winfo_exists())
        except tk.TclError:
            return False

    def lift(self):
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()

    def _browse(self):
        path = filedialog.askopenfilename(parent=self.win, title="Select imdisk.exe",
                                          filetypes=[("imdisk.exe", "imdisk.exe"), ("Programs", "*.exe")])
        if path:
            self.v_imdisk.set(path)

    def _clear_history(self):
        self.app.config.clear_history()
        self.app.window.refresh_history()
        messagebox.showinfo("Settings", "Image history cleared.", parent=self.win)

    def _restart_admin(self):
        self.win.destroy()
        self.app.restart_as_admin()

    def _save(self):
        try:
            secs = int(self.v_refresh.get())
            if not 1 <= secs <= 300:
                raise ValueError
        except ValueError:
            messagebox.showerror("Settings", "Refresh interval must be 1-300 seconds.", parent=self.win)
            return
        exts = []
        for tok in re.split(r"[,\s;]+", self.v_exts.get()):
            tok = tok.lower().lstrip("*")
            if tok:
                exts.append(tok if tok.startswith(".") else "." + tok)
        if not exts:
            messagebox.showerror("Settings", "Enter at least one file extension.", parent=self.win)
            return
        self.app.config.update({
            "imdisk_path": self.v_imdisk.get().strip(),
            "allowed_extensions": exts,
            "refresh_seconds": secs,
            "log_level": self.v_log.get(),
            "read_only": self.v_ro.get(),
            "removable_media": self.v_rem.get(),
            "open_explorer_after_mount": self.v_explorer.get(),
            "auto_elevate": self.v_elevate.get(),
            "start_hidden": self.v_hidden.get(),
            "close_button_hides": self.v_close.get(),
        })
        self.win.destroy()
        self.app.apply_settings()
