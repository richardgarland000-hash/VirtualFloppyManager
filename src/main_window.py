"""Main GUI window. All work is delegated to the App controller (which uses worker threads)."""

import os
import tkinter as tk
from tkinter import ttk, filedialog

from constants import APP_TITLE
from drive_utils import available_letters
from image_inspector import inspect_image


class MainWindow:
    def __init__(self, root, app):
        self.root = root
        self.app = app
        self._image_ok = False
        self._token = 0
        self._after_id = None

        root.title(APP_TITLE)
        root.geometry("720x540")
        root.minsize(620, 500)
        root.protocol("WM_DELETE_WINDOW", app.on_close_button)

        self.image_var = tk.StringVar()
        self.letter_var = tk.StringVar()
        self.info_var = tk.StringVar(value="No image selected.")
        self.status_var = tk.StringVar()
        self._build()
        self.image_var.trace_add("write", lambda *a: self._schedule_inspect())

    # ---- layout ------------------------------------------------------
    def _build(self):
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)

        img = ttk.LabelFrame(main, text="Disk image", padding=8)
        img.pack(fill="x")
        row = ttk.Frame(img)
        row.pack(fill="x")
        self.image_combo = ttk.Combobox(row, textvariable=self.image_var,
                                        values=self.app.config.get("history"))
        self.image_combo.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Browse...", command=self.browse).pack(side="left", padx=(6, 0))
        ttk.Label(img, textvariable=self.info_var, justify="left", wraplength=600,
                  anchor="nw").pack(fill="x", pady=(8, 0))

        drv = ttk.LabelFrame(main, text="Mount", padding=8)
        drv.pack(fill="x", pady=8)
        ttk.Label(drv, text="Drive letter:").pack(side="left")
        self.letter_combo = ttk.Combobox(drv, textvariable=self.letter_var, state="disabled", width=5)
        self.letter_combo.pack(side="left", padx=6)
        self.letter_combo.bind("<<ComboboxSelected>>", lambda e: self.update_states())
        self.mount_btn = ttk.Button(drv, text="Mount", command=self._mount)
        self.mount_btn.pack(side="left", padx=(6, 0))
        self.replace_btn = ttk.Button(drv, text="Replace selected mounted image with this one",
                                      command=self._replace)
        self.replace_btn.pack(side="left", padx=6)

        lst = ttk.LabelFrame(main, text="Mounted images", padding=8)
        lst.pack(fill="both", expand=True)
        cols = ("drive", "image", "format")
        self.tree = ttk.Treeview(lst, columns=cols, show="headings", height=6, selectmode="browse")
        for col, text, width in (("drive", "Drive", 55), ("image", "Image", 330), ("format", "Format", 200)):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="w")
        sb = ttk.Scrollbar(lst, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.update_states())

        # right-click menu on a mounted image
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Unmount", command=self._unmount)
        self.menu.add_command(label="Replace with the selected image", command=self._replace)
        self.tree.bind("<Button-3>", self._on_right_click)
        side = ttk.Frame(lst)
        side.pack(side="left", fill="y", padx=(8, 0))
        self.unmount_btn = ttk.Button(side, text="Unmount", command=self._unmount)
        self.unmount_btn.pack(anchor="n")

        bottom = ttk.Frame(main)
        bottom.pack(fill="x", pady=(10, 0))
        ttk.Label(bottom, textvariable=self.status_var, foreground="#555").pack(side="left")
        ttk.Button(bottom, text="Quit", command=self.app.request_quit).pack(side="right")
        ttk.Button(bottom, text="Hide", command=self.app.hide_window).pack(side="right", padx=6)
        ttk.Button(bottom, text="Settings...", command=self.app.open_settings).pack(side="right")
        self.update_states()

    # ---- helpers -----------------------------------------------------
    def status(self, text):
        self.status_var.set(text)

    def current_image(self):
        return self.image_var.get().strip().strip('"')

    def selected_letter(self):
        sel = self.tree.selection()
        return self.tree.item(sel[0], "values")[0].rstrip(":") if sel else None

    def _same_as_mounted(self, letter):
        return bool(letter) and self.app.manager.is_same_image(letter, self.current_image())

    def refresh_history(self):
        self.image_combo["values"] = self.app.config.get("history")

    # ---- image selection --------------------------------------------
    def browse(self):
        cfg = self.app.config
        exts = " ".join("*" + e for e in cfg.get("allowed_extensions"))
        current = self.current_image()
        start = cfg.get("last_dir") or (os.path.dirname(current) if current else "")
        path = filedialog.askopenfilename(
            parent=self.root, title="Select disk image",
            initialdir=start if start and os.path.isdir(start) else None,
            filetypes=[("Floppy disk images", exts), ("All files", "*.*")])
        if path:
            cfg.set("last_dir", os.path.dirname(path))
            self.image_var.set(os.path.normpath(path))

    def _schedule_inspect(self):
        self._image_ok = False
        self.update_states()
        if self._after_id:
            self.root.after_cancel(self._after_id)
        self._after_id = self.root.after(300, self._start_inspect)

    def _start_inspect(self):
        self._after_id = None
        path = self.current_image()
        self._token += 1
        token = self._token
        if not path:
            self.info_var.set("No image selected.")
            return
        self.info_var.set("Reading image...")

        def work():
            try:
                if not os.path.isfile(path):
                    result = (False, "File not found.")
                else:
                    info = inspect_image(path)
                    result = (info.mountable, info.summary())
            except OSError as exc:
                result = (False, f"Cannot read file: {exc}")
            self.app.ui_call(lambda: self._inspect_done(token, result))

        import threading
        threading.Thread(target=work, daemon=True).start()

    def _inspect_done(self, token, result):
        if token != self._token:
            return                      # a newer selection superseded this one
        self._image_ok, text = result
        self.info_var.set(text)
        self.update_states()

    def _on_right_click(self, event):
        row = self.tree.identify_row(event.y)
        if not row:
            return                                   # clicked empty space
        self.tree.selection_set(row)                 # right-click also selects the row
        self.tree.focus(row)
        self.update_states()
        letter = self.selected_letter()
        busy = self.app.busy
        self.menu.entryconfigure(0, label=f"Unmount {letter}:", state="disabled" if busy else "normal")
        self.menu.entryconfigure(
            1, state="normal" if self._image_ok and not busy and not self._same_as_mounted(letter)
            else "disabled")
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    # ---- actions -----------------------------------------------------
    def _mount(self):
        letter = self.letter_var.get().rstrip(":")
        if self._image_ok and letter:
            self.app.mount_image(self.current_image(), letter)

    def _unmount(self):
        letter = self.selected_letter()
        if letter:
            self.app.unmount_drive(letter)

    def _replace(self):
        letter = self.selected_letter()
        if letter and self._image_ok:
            self.app.replace_drive(letter, self.current_image())

    # ---- state refresh -----------------------------------------------
    def refresh(self, records):
        keep = self.selected_letter()
        self.tree.delete(*self.tree.get_children())
        for r in records:
            item = self.tree.insert("", "end", values=(f"{r.letter}:", r.image, r.fmt))
            if r.letter == keep:
                self.tree.selection_set(item)
        avail = [f"{c}:" for c in available_letters()]
        self.letter_combo["values"] = avail
        if self.letter_var.get() not in avail:
            self.letter_var.set(avail[0] if avail else "")
        self.refresh_history()
        self.update_states()

    def update_states(self):
        busy = self.app.busy
        ok = self._image_ok and not busy
        has_letter = bool(self.letter_var.get())
        sel = self.selected_letter()
        self.letter_combo.config(state="readonly" if ok and self.letter_combo["values"] else "disabled")
        self.mount_btn.config(state="normal" if ok and has_letter else "disabled")
        self.unmount_btn.config(state="normal" if sel and not busy else "disabled")
        self.replace_btn.config(state="normal" if sel and ok and not self._same_as_mounted(sel) else "disabled")
