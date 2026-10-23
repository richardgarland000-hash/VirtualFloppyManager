"""Main GUI window. All work is delegated to the App controller (which uses worker threads)."""

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog

from PIL import Image, ImageTk

import dropfiles
import theme
from constants import APP_TITLE
from drive_utils import available_letters
from image_inspector import inspect_image

STATUS_STYLES = {"info": "Status.TLabel", "success": "StatusSuccess.TLabel",
                 "warn": "StatusWarn.TLabel", "error": "StatusError.TLabel"}
INFO_BORDERS = {"none": theme.BORDER, "busy": theme.BORDER, "ok": theme.SUCCESS_BORDER,
                "warn": theme.WARNING_BORDER, "error": theme.DANGER_BORDER}


class MainWindow:
    def __init__(self, root, app):
        self.root = root
        self.app = app
        self._image_ok = False
        self._token = 0
        self._after_id = None

        root.title(APP_TITLE)
        root.geometry("840x690")
        root.minsize(800, 650)
        root.protocol("WM_DELETE_WINDOW", app.on_close_button)

        self.image_var = tk.StringVar()
        self.letter_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self.startup_var = tk.BooleanVar(value=False)
        self._menu_startup = tk.BooleanVar(value=False)
        self._build()
        self.image_var.trace_add("write", lambda *a: self._schedule_inspect())

    # ---- layout ------------------------------------------------------
    def _build(self):
        self._build_header()
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        bottom = ttk.Frame(main)
        bottom.pack(side="bottom", fill="x", pady=(12, 0))
        # buttons first so a long status message can never squeeze them
        ttk.Button(bottom, text="Quit", style="Slate.TButton", command=self.app.request_quit).pack(side="right")
        ttk.Button(bottom, text="Hide", command=self.app.hide_window).pack(side="right", padx=8)
        ttk.Button(bottom, text="Settings...", command=self.app.open_settings).pack(side="right")
        self.status_label = ttk.Label(bottom, textvariable=self.status_var, style="Status.TLabel",
                                      wraplength=360, justify="left")
        self.status_label.pack(side="left", fill="x", expand=True)

        img = ttk.LabelFrame(main, text="Disk image", padding=10)
        img.pack(fill="x")
        row = ttk.Frame(img)
        row.pack(fill="x")
        self.image_combo = ttk.Combobox(row, textvariable=self.image_var,
                                        values=self.app.config.get("history"))
        self.image_combo.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Browse...", style="Accent.TButton",
                   command=self.browse).pack(side="left", padx=(8, 0))

        self.info = tk.Text(img, height=7, wrap="word", bg=theme.SURFACE, fg=theme.TEXT,
                            font=theme.FONT, relief="flat", bd=0, padx=10, pady=6,
                            highlightthickness=2, cursor="arrow", state="disabled")
        self.info.tag_configure("head", foreground=theme.ACCENT_DARK, font=theme.FONT_BOLD)
        self.info.tag_configure("warn", foreground=theme.WARNING, font=theme.FONT_BOLD)
        self.info.tag_configure("error", foreground=theme.DANGER)
        self.info.tag_configure("muted", foreground=theme.MUTED)
        self.info.pack(fill="x", pady=(10, 0))
        self._set_info("No image selected. Browse for a file, or drag one here.", "none")

        drv = ttk.LabelFrame(main, text="Mount", padding=10)
        drv.pack(fill="x", pady=10)
        top = ttk.Frame(drv)
        top.pack(fill="x")
        ttk.Label(top, text="Drive letter:").pack(side="left")
        self.letter_combo = ttk.Combobox(top, textvariable=self.letter_var, state="disabled", width=5)
        self.letter_combo.pack(side="left", padx=8)
        self.letter_combo.bind("<<ComboboxSelected>>", lambda e: self.update_states())
        self.mount_btn = ttk.Button(top, text="Mount", style="Success.TButton", command=self._mount)
        self.mount_btn.pack(side="left", padx=(4, 0))
        self.replace_btn = ttk.Button(top, text="Replace selected mounted image with this one",
                                      style="Warning.TButton", command=self._replace)
        self.replace_btn.pack(side="left", padx=8)
        self.startup_check = ttk.Checkbutton(
            drv, text="Mount at startup (mount this image automatically whenever the program starts)",
            variable=self.startup_var, state="disabled")
        self.startup_check.pack(anchor="w", pady=(10, 0))

        lst = ttk.LabelFrame(main, text="Mounted images", padding=10)
        lst.pack(fill="both", expand=True)
        cols = ("drive", "image", "format", "startup")
        self.tree = ttk.Treeview(lst, columns=cols, show="headings", height=6, selectmode="browse")
        for col, text, width in (("drive", "Drive", 56), ("image", "Image", 205), ("format", "Format", 275), ("startup", "At startup", 88)):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, minwidth=50,
                             anchor="center" if col == "startup" else "w",
                             stretch=col in ("image", "format"))
        self.tree.tag_configure("odd", background=theme.SURFACE)
        self.tree.tag_configure("even", background=theme.SURFACE_ALT)
        self.tree.tag_configure("ro", foreground=theme.READ_ONLY_TEXT)
        side = ttk.Frame(lst)
        side.pack(side="right", fill="y", padx=(10, 0))
        self.unmount_btn = ttk.Button(side, text="Unmount", style="Danger.TButton", command=self._unmount)
        self.unmount_btn.pack(anchor="n")
        sb = ttk.Scrollbar(lst, orient="vertical", command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.update_states())

        # right-click menu on a mounted image
        self.menu = tk.Menu(self.root, tearoff=0)
        theme.style_menu(self.menu)
        self.menu.add_command(label="Unmount", command=self._unmount)
        self.menu.add_command(label="Replace with the selected image", command=self._replace)
        self.menu.add_separator()
        self.menu.add_checkbutton(label="Mount at startup", variable=self._menu_startup,
                                  command=self._toggle_startup)
        self.tree.bind("<Button-3>", self._on_right_click)


        self.update_states()
        for widget in (self.image_combo, self.info):
            dropfiles.hook(widget, self._on_drop)

    def _on_drop(self, paths):
        if self.app.busy:
            self.status("Busy - drop the file again when the current operation finishes.", "warn")
            return
        path, message, kind = dropfiles.pick_image(paths)
        if path is None:
            self.status(message, kind)
            return
        self.image_var.set(os.path.normpath(path))
        self.status(message or f"Selected {os.path.basename(path)}.", kind)

    def _build_header(self):
        header = tk.Frame(self.root, bg=theme.HEADER)
        header.pack(fill="x")
        inner = tk.Frame(header, bg=theme.HEADER)
        inner.pack(fill="x", padx=14, pady=10)
        self._logo = ImageTk.PhotoImage(self.app.icons.base.resize((38, 38), Image.LANCZOS))
        tk.Label(inner, image=self._logo, bg=theme.HEADER).pack(side="left")
        titles = tk.Frame(inner, bg=theme.HEADER)
        titles.pack(side="left", padx=12)
        tk.Label(titles, text=APP_TITLE, bg=theme.HEADER, fg=theme.HEADER_TEXT,
                 font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(titles, text="Mount raw floppy disk images as drives", bg=theme.HEADER,
                 fg=theme.HEADER_SUB, font=theme.FONT).pack(anchor="w")
        self.count_label = tk.Label(inner, text="", bg=theme.SLATE, fg="#ffffff",
                                    font=theme.FONT_BOLD, padx=12, pady=4)
        self.count_label.pack(side="right")

    # ---- helpers -----------------------------------------------------
    def status(self, text, kind="info"):
        self.status_var.set(text)
        self.status_label.configure(style=STATUS_STYLES.get(kind, STATUS_STYLES["info"]))

    def _set_info(self, text, kind):
        """kind: none | busy | ok | warn | error  (sets text colours and the border colour)."""
        border = INFO_BORDERS[kind]
        self.info.configure(state="normal", highlightbackground=border, highlightcolor=border)
        self.info.delete("1.0", "end")
        for line in text.split("\n"):
            if kind == "error":
                tag = "error"
            elif line.startswith("Warning:"):
                tag = "warn"
            elif line.startswith("Structure:"):
                tag = "head"
            elif kind in ("none", "busy"):
                tag = "muted"
            else:
                tag = ""
            self.info.insert("end", line + "\n", (tag,) if tag else ())
        self.info.configure(state="disabled")

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
            self._set_info("No image selected. Browse for a file, or drag one here.", "none")
            return
        self._set_info("Reading image...", "busy")

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

        threading.Thread(target=work, daemon=True).start()

    def _inspect_done(self, token, result):
        if token != self._token:
            return                      # a newer selection superseded this one
        self._image_ok, text = result
        if not self._image_ok:
            kind = "error"
        elif any(line.startswith("Warning:") for line in text.split("\n")):
            kind = "warn"
        else:
            kind = "ok"
        self._set_info(text, kind)
        if self._image_ok:
            self.startup_var.set(self.app.manager.is_startup_image(self.current_image()))
        self.update_states()

    # ---- actions -----------------------------------------------------
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
        rec = self.app.manager.get(letter)
        self._menu_startup.set(bool(rec and self.app.manager.is_startup_image(rec.image)))
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def _toggle_startup(self):
        letter = self.selected_letter()
        if letter:
            self.app.set_startup_for_drive(letter, self._menu_startup.get())

    def _mount(self):
        letter = self.letter_var.get().rstrip(":")
        if self._image_ok and letter:
            self.app.mount_image(self.current_image(), letter, startup=self.startup_var.get())

    def _unmount(self):
        letter = self.selected_letter()
        if letter:
            self.app.unmount_drive(letter)

    def _replace(self):
        letter = self.selected_letter()
        if letter and self._image_ok:
            self.app.replace_drive(letter, self.current_image(), startup=self.startup_var.get())

    # ---- state refresh -----------------------------------------------
    def refresh(self, records):
        keep = self.selected_letter()
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(records):
            tags = ["even" if i % 2 else "odd"] + (["ro"] if r.read_only else [])
            fmt = r.fmt + ("  [read-only]" if r.read_only else "")
            at_startup = "Yes" if self.app.manager.is_startup_image(r.image) else ""
            item = self.tree.insert("", "end", values=(f"{r.letter}:", r.image, fmt, at_startup), tags=tags)
            if r.letter == keep:
                self.tree.selection_set(item)
        avail = [f"{c}:" for c in available_letters()]
        self.letter_combo["values"] = avail
        if self.letter_var.get() not in avail:
            self.letter_var.set(avail[0] if avail else "")
        self.refresh_history()
        n = len(records)
        self.count_label.configure(
            text=f"{n} mounted" if n else "none mounted",
            bg=theme.SUCCESS_BORDER if n else theme.SLATE)
        self.update_states()

    def update_states(self):
        busy = self.app.busy
        ok = self._image_ok and not busy
        has_letter = bool(self.letter_var.get())
        sel = self.selected_letter()
        self.letter_combo.config(state="readonly" if ok and self.letter_combo["values"] else "disabled")
        self.mount_btn.config(state="normal" if ok and has_letter else "disabled")
        self.startup_check.config(state="normal" if ok else "disabled")
        self.unmount_btn.config(state="normal" if sel and not busy else "disabled")
        self.replace_btn.config(
            state="normal" if sel and ok and not self._same_as_mounted(sel) else "disabled")
