"""Drive-letter discovery and small Windows shell helpers."""

import ctypes
import logging
import string
import sys
import time

log = logging.getLogger("floppymounter.drives")

SHCNE_DRIVEREMOVED = 0x00000080
SHCNE_DRIVEADD = 0x00000100
SHCNF_PATHW = 0x0005


def used_letters():
    """Letters of all logical drives currently present (fixed, removable, network...)."""
    if sys.platform != "win32":
        return set()
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    return {c for i, c in enumerate(string.ascii_uppercase) if mask & (1 << i)}


def available_letters():
    """Free drive letters in alphabetical order."""
    used = used_letters()
    return [c for c in string.ascii_uppercase if c not in used]


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def wait_for_drive(letter, present, timeout=8.0, interval=0.25):
    """Poll until the drive letter appears (present=True) or disappears (False)."""
    deadline = time.monotonic() + timeout
    while True:
        if (letter in used_letters()) == present:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(interval)


def notify_shell(letter, added):
    """Tell Explorer a drive appeared/vanished so it refreshes without us touching it."""
    try:
        event = SHCNE_DRIVEADD if added else SHCNE_DRIVEREMOVED
        ctypes.windll.shell32.SHChangeNotify(
            event, SHCNF_PATHW, ctypes.c_wchar_p(f"{letter}:\\"), None)
    except Exception as exc:
        log.debug("SHChangeNotify failed: %s", exc)
