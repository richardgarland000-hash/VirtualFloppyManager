"""Floppy-disk icons for the tray, main window and dialogs.

Icons are drawn with Pillow so no binary assets are needed. To use your own
icon, place a multi-size .ico at assets/floppy.ico next to the program.
"""

import logging
import os
import tkinter as tk

from PIL import Image, ImageTk

from icon_art import make_floppy
from paths import data_dir, icon_override_path

log = logging.getLogger("floppymounter.icons")


class Icons:
    def __init__(self):
        self.base = make_floppy(256)
        self._tray = {False: make_floppy(64), True: make_floppy(64, badge=True)}
        self.ico_path = self._ensure_ico()
        self._photo = None

    def tray(self, active):
        return self._tray[bool(active)]

    def _ensure_ico(self):
        override = icon_override_path()
        if os.path.isfile(override):
            return override
        path = os.path.join(data_dir(), "floppy_mounter.ico")
        try:
            self.base.save(path, format="ICO",
                           sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)])
            return path
        except OSError as exc:
            log.warning("Could not write icon file: %s", exc)
            return None

    def apply(self, root):
        """Set the default icon for the root window and every dialog created later."""
        if self.ico_path:
            try:
                root.iconbitmap(default=self.ico_path)
                return
            except tk.TclError as exc:
                log.warning("iconbitmap failed: %s", exc)
        self._photo = ImageTk.PhotoImage(self.base.resize((64, 64), Image.LANCZOS))
        root.iconphoto(True, self._photo)
