"""UAC elevation helpers.

run_elevated(): runs one command through the "runas" verb (shows the UAC prompt),
waits for it, and returns (exit_code, captured_output). Elevated processes cannot
be piped, so output is redirected to a temp file by a short-lived cmd.exe wrapper.

restart_elevated(): relaunches this program as administrator.
"""

import ctypes
import logging
import os
import subprocess
import sys
import tempfile
from ctypes import wintypes

from paths import app_dir

log = logging.getLogger("floppymounter.elevation")

SEE_MASK_NOCLOSEPROCESS = 0x00000040
SW_HIDE = 0
SW_SHOWNORMAL = 1
WAIT_TIMEOUT = 0x00000102
ERROR_CANCELLED = 1223


class ElevationDeclined(Exception):
    """The user cancelled the UAC prompt."""


class ElevationFailed(Exception):
    """The elevated process could not be started or did not finish."""


class SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD), ("fMask", wintypes.ULONG), ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR), ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p), ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY), ("dwHotKey", wintypes.DWORD),
        ("hIcon", wintypes.HANDLE), ("hProcess", wintypes.HANDLE),
    ]


def run_elevated(cmd, timeout=90):
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(SHELLEXECUTEINFOW)]
    shell32.ShellExecuteExW.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    fd, out_path = tempfile.mkstemp(prefix="floppymounter_", suffix=".txt")
    os.close(fd)
    inner = f'"{cmd[0]}" {subprocess.list2cmdline(cmd[1:])} > "{out_path}" 2>&1'
    info = SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = SEE_MASK_NOCLOSEPROCESS
    info.lpVerb = "runas"
    info.lpFile = os.environ.get("ComSpec", "cmd.exe")
    info.lpParameters = f'/c "{inner}"'
    info.nShow = SW_HIDE
    log.info("Requesting elevation for: %s", subprocess.list2cmdline(cmd))
    try:
        if not shell32.ShellExecuteExW(ctypes.byref(info)):
            err = ctypes.get_last_error()
            if err == ERROR_CANCELLED:
                raise ElevationDeclined()
            raise ElevationFailed(f"Could not start the elevated process (Windows error {err}).")
        try:
            if kernel32.WaitForSingleObject(info.hProcess, int(timeout * 1000)) == WAIT_TIMEOUT:
                raise ElevationFailed(f"The elevated command did not finish within {timeout} seconds.")
            code = wintypes.DWORD(1)
            kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(code))
        finally:
            kernel32.CloseHandle(info.hProcess)
        try:
            with open(out_path, "r", encoding="oem", errors="replace") as fh:
                output = fh.read().strip()
        except OSError:
            output = ""
        return code.value, output
    finally:
        try:
            os.remove(out_path)
        except OSError:
            pass


def restart_elevated():
    """Launch a new elevated copy of this program. True if Windows accepted the request."""
    extra = ["--wait-for-previous"] + [a for a in sys.argv[1:] if a != "--wait-for-previous"]
    if getattr(sys, "frozen", False):
        exe, params = sys.executable, subprocess.list2cmdline(extra)
    else:
        exe = sys.executable
        pythonw = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.isfile(pythonw):
            exe = pythonw
        params = subprocess.list2cmdline([os.path.join(app_dir(), "main.py")] + extra)
    log.info("Restarting elevated: %s %s", exe, params)
    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, app_dir(), SW_SHOWNORMAL)
    return result > 32
