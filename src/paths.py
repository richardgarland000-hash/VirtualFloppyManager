"""Where the application keeps its files.

Config, log and generated icon live next to the program. If that folder is not
writable (e.g. installed under Program Files) we fall back to
%LOCALAPPDATA%\\FloppyMounter so logging and settings always work.
"""

import os
import sys

from constants import APP_NAME

_data_dir = None


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _writable(directory):
    try:
        os.makedirs(directory, exist_ok=True)
        probe = os.path.join(directory, ".write_test")
        with open(probe, "w") as fh:
            fh.write("x")
        os.remove(probe)
        return True
    except OSError:
        return False


def data_dir():
    global _data_dir
    if _data_dir is None:
        directory = app_dir()
        if not _writable(directory):
            base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
            directory = os.path.join(base, APP_NAME)
            os.makedirs(directory, exist_ok=True)
        _data_dir = directory
    return _data_dir


def config_path():
    return os.path.join(data_dir(), "floppy_mounter.json")


def log_path():
    return os.path.join(data_dir(), "floppy_mounter.log")


def icon_override_path():
    """Drop your own .ico here to replace the generated icon."""
    return os.path.join(app_dir(), "assets", "floppy.ico")
