"""Floppy Image Mounter - entry point.

Command-line flags:
  --hidden        start minimised to the system tray
  --no-elevate    (source runs only) do not relaunch via UAC
"""

import ctypes
import sys
import time

MUTEX_NAME = "Local\\FloppyImageMounter_SingleInstance"
TITLE = "Floppy Image Mounter"


def _message(text, flags=0x40):
    ctypes.windll.user32.MessageBoxW(0, text, TITLE, flags)


def ensure_elevated():
    """Packaged builds are elevated by their manifest (requireAdministrator).
    When running from source, relaunch through UAC. Returns False if this
    process should exit because an elevated copy is taking over."""
    from drive_utils import is_admin
    if is_admin() or getattr(sys, "frozen", False) or "--no-elevate" in sys.argv:
        return True
    from elevation import restart_elevated
    if restart_elevated():
        return False
    _message("Administrator approval was declined. Mounting will probably be refused "
             "until the program is run as administrator.", 0x30)
    return True


def acquire_single_instance():
    wait = 15 if "--wait-for-previous" in sys.argv else 0     # elevated restart
    deadline = time.monotonic() + wait
    while True:
        handle = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
        already = ctypes.windll.kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS
        if not already:
            return handle                                       # keep referenced for process lifetime
        ctypes.windll.kernel32.CloseHandle(handle)
        if time.monotonic() >= deadline:
            return None
        time.sleep(0.5)


def main():
    if sys.platform != "win32":
        print("Floppy Image Mounter only runs on Windows.")
        return 1
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)         # crisp text on high-DPI screens
    except Exception:
        pass
    if not ensure_elevated():
        return 0
    mutex = acquire_single_instance()
    if mutex is None:
        _message("Floppy Image Mounter is already running. Look for its icon in the system tray.")
        return 0

    from app import App
    App().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
