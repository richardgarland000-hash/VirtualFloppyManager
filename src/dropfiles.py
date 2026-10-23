"""Drag-and-drop of files from Explorer onto Tk widgets (Windows, pure ctypes).

Tk has no built-in file drop. This uses the classic WM_DROPFILES mechanism: the
widget's window procedure is subclassed and DragAcceptFiles() is enabled on it.

The program normally runs elevated, and Windows (UIPI) blocks drops from a normal,
non-elevated Explorer window onto an elevated window. To allow them, the window
message filter is opened for the three messages the shell uses for a drop.
"""

import ctypes
import logging
import os
import sys
import tkinter as tk
from ctypes import wintypes

log = logging.getLogger("floppymounter.drop")

WM_DROPFILES = 0x0233
WM_COPYDATA = 0x004A
WM_COPYGLOBALDATA = 0x0049
MSGFLT_ALLOW = 1
GWL_WNDPROC = -4

_hooks = []          # keeps callbacks and the original window procedures alive


def pick_image(paths):
    """Decide what to do with dropped paths -> (path or None, message or None, status kind)."""
    files = [p for p in paths if os.path.isfile(p)]
    if not files:
        if any(os.path.isdir(p) for p in paths):
            return None, "That is a folder. Drop a disk image file instead.", "warn"
        return None, "Nothing usable was dropped. Drop a disk image file.", "warn"
    first = files[0]
    if len(files) > 1:
        return first, f"Several files dropped - using {os.path.basename(first)}.", "warn"
    return first, None, "info"


def _dropped_paths(shell32, hdrop):
    try:
        count = shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
        paths = []
        for i in range(count):
            length = shell32.DragQueryFileW(hdrop, i, None, 0)
            buf = ctypes.create_unicode_buffer(length + 1)
            shell32.DragQueryFileW(hdrop, i, buf, length + 1)
            paths.append(buf.value)
        return paths
    finally:
        shell32.DragFinish(hdrop)


def hook(widget, callback):
    """Make `widget` accept dropped files. callback(list_of_paths) runs on the Tk thread.
    Returns True if the hook was installed (always False off Windows)."""
    if sys.platform != "win32":
        return False
    try:
        hwnd = widget.winfo_id()
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)

        lresult = ctypes.c_ssize_t
        wndproc_type = ctypes.WINFUNCTYPE(lresult, wintypes.HWND, wintypes.UINT,
                                          wintypes.WPARAM, wintypes.LPARAM)
        set_proc = getattr(user32, "SetWindowLongPtrW", None) or user32.SetWindowLongW
        set_proc.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
        set_proc.restype = ctypes.c_void_p
        user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT,
                                           wintypes.WPARAM, wintypes.LPARAM]
        user32.CallWindowProcW.restype = lresult
        shell32.DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
        shell32.DragQueryFileW.restype = wintypes.UINT
        shell32.DragFinish.argtypes = [wintypes.HANDLE]
        shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]

        previous = {}

        def proc(h, msg, wparam, lparam):
            if msg == WM_DROPFILES:
                try:
                    paths = _dropped_paths(shell32, wparam)
                    # defer: never run dialogs inside the shell's drop call
                    widget.after(30, lambda: _safe_call(callback, paths))
                except Exception:
                    log.exception("Processing dropped files failed")
                return 0
            return user32.CallWindowProcW(previous["proc"], h, msg, wparam, lparam)

        wndproc = wndproc_type(proc)
        previous["proc"] = set_proc(hwnd, GWL_WNDPROC, ctypes.cast(wndproc, ctypes.c_void_p))
        if not previous["proc"]:
            log.warning("Could not subclass the widget window (error %s)", ctypes.get_last_error())
            return False

        # Let drops through even though we run elevated (UIPI).
        try:
            user32.ChangeWindowMessageFilterEx.argtypes = [wintypes.HWND, wintypes.UINT,
                                                           wintypes.DWORD, ctypes.c_void_p]
            for message in (WM_DROPFILES, WM_COPYDATA, WM_COPYGLOBALDATA):
                user32.ChangeWindowMessageFilterEx(hwnd, message, MSGFLT_ALLOW, None)
        except AttributeError:
            log.debug("ChangeWindowMessageFilterEx not available")

        shell32.DragAcceptFiles(hwnd, True)
        _hooks.append((wndproc, previous))
        log.info("Drag and drop enabled on %s", widget)
        return True
    except (tk.TclError, OSError, AttributeError) as exc:
        log.warning("Drag and drop could not be enabled: %s", exc)
        return False


def _safe_call(callback, paths):
    try:
        callback(paths)
    except Exception:
        log.exception("Drop callback failed")
