"""Mount/unmount through ImDisk's command-line tool.

Windows' built-in PowerShell cmdlet (Mount-DiskImage) only handles ISO/VHD/VHDX and
cannot attach a raw floppy image or choose a drive letter, so raw floppy images
are attached with ImDisk. Every call runs as a separate, hidden child process and
is meant to be invoked from a worker thread, never the GUI thread.
"""

import logging
import os
import shutil
import subprocess

from drive_utils import is_admin
from elevation import ElevationDeclined, ElevationFailed, run_elevated

log = logging.getLogger("floppymounter.imdisk")

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

NOT_FOUND_MSG = (
    "ImDisk was not found.\n\n"
    "Windows cannot mount raw floppy images natively, so this program uses the "
    "ImDisk Toolkit. Install it, or set the path to imdisk.exe in Settings.")


class BackendError(Exception):
    """kind: error | elevation | in_use | not_found"""

    def __init__(self, message, kind="error", detail=""):
        super().__init__(message)
        self.kind = kind
        self.detail = detail


def _classify(text):
    t = text.lower()
    if any(s in t for s in ("access is denied", "privilege", "administrator", "elevat")):
        return "elevation"
    if any(s in t for s in ("in use", "being used", "locked", "busy", "sharing violation")):
        return "in_use"
    return "error"


class ImDiskBackend:
    def __init__(self, config):
        self.config = config
        self.last_privileged = False

    def locate(self):
        candidates = []
        configured = (self.config.get("imdisk_path") or "").strip().strip('"')
        if configured:
            candidates.append(configured)
        found = shutil.which("imdisk")
        if found:
            candidates.append(found)
        candidates.append(os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                                       "System32", "imdisk.exe"))
        for cand in candidates:
            if os.path.isfile(cand):
                return cand
        return None

    def _run(self, args, timeout=60, elevate=False):
        exe = self.locate()
        if not exe:
            raise BackendError(NOT_FOUND_MSG, "not_found")
        cmd = [exe] + args
        self.last_privileged = is_admin()
        log.info("Running: %s", subprocess.list2cmdline(cmd))
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, errors="replace", timeout=timeout,
                creationflags=CREATE_NO_WINDOW, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            raise BackendError(f"ImDisk did not finish within {timeout} seconds.")
        except OSError as exc:
            raise BackendError(f"Could not start ImDisk: {exc}")
        output = ((proc.stdout or "") + (proc.stderr or "")).strip()
        log.info("ImDisk exit code %s: %s", proc.returncode, output or "(no output)")
        if (elevate and proc.returncode != 0 and _classify(output) == "elevation"
                and self.config.get("auto_elevate") and not is_admin()):
            return self._run_elevated(cmd, timeout)
        return proc.returncode, output

    def _run_elevated(self, cmd, timeout):
        """Retry a denied command through a UAC prompt."""
        try:
            rc, output = run_elevated(cmd, max(timeout, 90))
        except ElevationDeclined:
            raise BackendError("Administrator approval was declined, so the operation was not performed.",
                               "elevation")
        except ElevationFailed as exc:
            raise BackendError(str(exc), "elevation")
        self.last_privileged = True
        log.info("Elevated ImDisk exit code %s: %s", rc, output or "(no output)")
        return rc, output

    def _error(self, action, rc, output):
        kind = _classify(output)
        if kind == "elevation" and self.last_privileged:
            # Already running with administrator rights, so 'access denied' means the
            # volume is locked by an open handle (Explorer, indexer, antivirus, ...).
            kind = "in_use"
        if kind == "elevation":
            msg = (f"Windows denied the {action} request. This needs administrator "
                   "rights: enable automatic elevation in Settings, or restart the program as administrator.")
        elif kind == "in_use":
            msg = (f"Windows refused to {action} the drive because it is in use by another "
                   "program or an Explorer window.")
        else:
            msg = f"ImDisk failed to {action} (exit code {rc})."
        if output and kind != "elevation":
            msg += f"\n\n{output}"
        return BackendError(msg, kind, output)

    def mount(self, image, letter, read_only, removable, floppy):
        opts = []
        if floppy:
            opts.append("fd")
        opts.append("ro" if read_only else "rw")
        opts.append("rem" if removable else "fix")
        rc, out = self._run(["-a", "-t", "file", "-f", image, "-m", f"{letter}:",
                             "-o", ",".join(opts)], elevate=True)
        if rc != 0:
            raise self._error("mount", rc, out)

    def unmount(self, letter, force=False):
        rc, out = self._run(["-D" if force else "-d", "-m", f"{letter}:"], elevate=True)
        if rc != 0:
            raise self._error("unmount", rc, out)

    def is_device(self, letter):
        """True if the letter is an ImDisk virtual disk (checked via `imdisk -l`)."""
        rc, _ = self._run(["-l", "-m", f"{letter}:"], timeout=15)
        return rc == 0
