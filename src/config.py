"""JSON-backed settings, image history and persisted mount records."""

import copy
import json
import logging
import os
import threading

log = logging.getLogger("floppymounter.config")

DEFAULTS = {
    "imdisk_path": "",                  # blank = auto-detect
    "read_only": False,
    "removable_media": True,
    "open_explorer_after_mount": False,
    "auto_elevate": True,               # retry denied commands via a UAC prompt
    "start_hidden": False,
    "close_button_hides": True,         # X hides to tray instead of quitting
    "refresh_seconds": 5,
    "allowed_extensions": [".img", ".ima", ".flp", ".vfd", ".dsk", ".xdf",
                           ".dmf", ".bin", ".st", ".raw", ".im"],
    "log_level": "INFO",
    "last_dir": "",
    "history": [],                      # last 10 mounted images, newest first
    "mounted": [],                      # records of images we mounted
}


class Config:
    HISTORY_MAX = 10

    def __init__(self, path):
        self.path = path
        self._lock = threading.RLock()
        self._data = copy.deepcopy(DEFAULTS)
        self.load()

    # ---- persistence -------------------------------------------------
    def load(self):
        with self._lock:
            try:
                with open(self.path, "r", encoding="utf-8") as fh:
                    loaded = json.load(fh)
            except FileNotFoundError:
                return
            except (OSError, ValueError) as exc:
                log.error("Could not read %s (%s); using defaults", self.path, exc)
                try:
                    os.replace(self.path, self.path + ".corrupt")
                except OSError:
                    pass
                return
            if isinstance(loaded, dict):
                for key, default in DEFAULTS.items():
                    if key in loaded and type(loaded[key]) is type(default):
                        self._data[key] = loaded[key]

    def save(self):
        with self._lock:
            tmp = self.path + ".tmp"
            try:
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(self._data, fh, indent=2)
                os.replace(tmp, self.path)
            except OSError as exc:
                log.error("Could not save settings: %s", exc)

    # ---- access ------------------------------------------------------
    def get(self, key):
        with self._lock:
            return copy.deepcopy(self._data[key])

    def set(self, key, value):
        with self._lock:
            self._data[key] = value
            self.save()

    def update(self, values):
        with self._lock:
            self._data.update(values)
            self.save()

    # ---- history -----------------------------------------------------
    def add_history(self, image):
        with self._lock:
            full = os.path.abspath(image)
            norm = os.path.normcase(full)
            hist = [h for h in self._data["history"]
                    if os.path.normcase(os.path.abspath(h)) != norm]
            hist.insert(0, full)
            self._data["history"] = hist[:self.HISTORY_MAX]
            self.save()

    def clear_history(self):
        self.set("history", [])
